"""Kokoro-82M "Fable-mix" voice for Atlas's Wyoming TTS server: ONNX Runtime on CPU, misaki British G2P.

Drop-in for the server's ``piper_synth`` factory::

    synth, sample_rate = kokoro_synth(model_dir)          # sample_rate == 24000
    for pcm in synth("Done. Kitchen lights off."):        # 16-bit little-endian mono PCM bytes
        ...

What this module does, and nothing more:

* Loads only from ``model_dir``. Every file in ``BUNDLE`` is read into memory, its SHA-256 checked against the
  constant below, and only those verified bytes are used (no second read, so no swap between check and use).
  Any missing file or mismatch raises ``BundleError`` before a model is built.
* Never touches the network: it sets the Hugging Face offline flags, refuses to start if the spaCy English model
  is not installed (misaki would otherwise try to download it), and has no download code of its own.
* Never logs or prints text. Errors raised from ``synth`` carry no text or phonemes.
* Splits a reply at sentence ends (and very long sentences at clause marks) and yields each piece's PCM as soon
  as it is rendered, so the first audio arrives after the first sentence, not the whole reply.
* Deterministic: the ONNX graph has no random operators, and ONNX Runtime runs with deterministic compute.

The server keeps everything else (admission, caps, one synthesis at a time, watchdog, text normalisation).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import warnings
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

SAMPLE_RATE = 24000
VOICE_NAME = "en_GB-fablemix"

# File name in model_dir -> SHA-256 of its exact bytes. See bundle/manifest.json for sources and licences.
BUNDLE: Mapping[str, str] = {
    "kokoro-v1.0.onnx": "PENDING",
    "config.json": "PENDING",
    "en_GB-fablemix.npy": "5de2db9de4510efd4b3dd9f64bf0cf03530089b2220aec95f43f3b27636fbf80",
}
MODEL_FILE, CONFIG_FILE, VOICE_FILE = "kokoro-v1.0.onnx", "config.json", "en_GB-fablemix.npy"

MAX_PHONEMES = 510  # Kokoro's context limit per inference (the voice pack has one style row per length)
CLAUSE_SPLIT = 120  # a sentence longer than this many phonemes is split at its commas, colons and semicolons
SENTENCE_GAP_S = 0.0  # extra silence after each sentence; Kokoro already ends a sentence with its own pause

# House-word pronunciations (misaki phonemes), merged into misaki's British gold lexicon at load.
LEXICON: Mapping[str, str] = {}

_SENTENCE = re.compile(r"(?<=[.!?…])[\"')\]]*\s+")
_CLAUSE = re.compile(r"(?<=[,;:—])\s+")
_OFFLINE_FLAGS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY")


class BundleError(RuntimeError):
    """The model bundle is missing, altered or unusable. Raised at load; the server must not start the voice."""


class SynthesisError(RuntimeError):
    """A reply could not be rendered. Carries no text."""


def _read_verified(model_dir: Path, name: str) -> bytes:
    path = model_dir / name
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise BundleError(f"cannot read bundle file {name}: {type(exc).__name__}") from None
    digest = hashlib.sha256(data).hexdigest()
    if digest != BUNDLE[name]:
        raise BundleError(f"sha256 mismatch for {name}: got {digest}")
    return data


def split_text(text: str) -> list[str]:
    """Sentences, in order; the caller re-splits any that are too long once their phonemes are known."""
    return [s.strip() for s in _SENTENCE.split(text.strip()) if s.strip()]


def _pcm16(audio: Any) -> bytes:
    import numpy as np

    return (np.clip(audio, -1.0, 1.0) * 32767.0).round().astype("<i2").tobytes()


def kokoro_synth(
    model_dir: str | os.PathLike[str], speed: float = 0.95, threads: int | None = None
) -> tuple[Callable[[str], Iterator[bytes]], int]:
    """Build the Fable-mix synthesiser from a verified bundle.

    Args:
        model_dir: folder holding exactly the files named in ``BUNDLE`` (extra files are ignored).
        speed: Kokoro speed factor; 0.95 is the voice-scout setting.
        threads: ONNX Runtime intra-op threads; ``None`` lets ONNX Runtime use one per physical core.

    Returns:
        ``(synth, 24000)``. ``synth(text)`` yields 16-bit mono PCM bytes, one piece per sentence or clause, and
        yields nothing for empty or whitespace-only text.

    Raises:
        BundleError: a bundle file is missing or altered, or the spaCy English model is not installed.
    """
    if not 0.5 <= speed <= 2.0:
        raise ValueError("speed must be between 0.5 and 2.0")
    if threads is not None and threads < 1:
        raise ValueError("threads must be a positive integer")
    for flag in _OFFLINE_FLAGS:
        os.environ[flag] = "1"

    root = Path(model_dir)
    model_bytes = _read_verified(root, MODEL_FILE)
    config_bytes = _read_verified(root, CONFIG_FILE)
    voice_bytes = _read_verified(root, VOICE_FILE)

    import numpy as np
    import onnxruntime as ort
    import spacy.util

    if not spacy.util.is_package("en_core_web_sm"):
        raise BundleError("spaCy model en_core_web_sm is not installed (install it from requirements.lock)")
    from misaki import en, espeak

    vocab: dict[str, int] = json.loads(config_bytes)["vocab"]
    pack = np.load(io.BytesIO(voice_bytes), allow_pickle=False)
    if pack.shape != (MAX_PHONEMES, 1, 256) or pack.dtype != np.float32:
        raise BundleError("voice pack has the wrong shape or type")

    logging.getLogger("phonemizer").disabled = True
    g2p = en.G2P(british=True, fallback=espeak.EspeakFallback(british=True), unk="")
    g2p.lexicon.golds.update(LEXICON)

    options = ort.SessionOptions()
    options.use_deterministic_compute = True
    options.log_severity_level = 3
    options.inter_op_num_threads = 1
    if threads is not None:
        options.intra_op_num_threads = threads
    session = ort.InferenceSession(model_bytes, options, providers=["CPUExecutionProvider"])
    del model_bytes
    speed_in = np.array([speed], dtype=np.float32)

    def phonemize(text: str) -> str:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            phonemes: str = g2p(text)[0]
        return "".join(p for p in phonemes if p in vocab).strip()

    def pieces(sentence: str) -> Iterator[str]:
        """Phonemes for one sentence, split at clause marks, then at spaces, until each piece fits."""
        phonemes = phonemize(sentence)
        if len(phonemes) <= CLAUSE_SPLIT:
            if phonemes:
                yield phonemes
            return
        clauses = [c for c in _CLAUSE.split(sentence) if c.strip()]
        if len(clauses) > 1:
            for clause in clauses:
                yield from pieces(clause)
            return
        while len(phonemes) > MAX_PHONEMES:
            cut = phonemes.rfind(" ", 0, MAX_PHONEMES)
            cut = cut if cut > 0 else MAX_PHONEMES
            yield phonemes[:cut].strip()
            phonemes = phonemes[cut:].strip()
        if phonemes:
            yield phonemes

    def render(phonemes: str) -> bytes:
        ids = np.array([[0, *(vocab[p] for p in phonemes), 0]], dtype=np.int64)
        style = pack[len(phonemes) - 1]
        audio = session.run(None, {"input_ids": ids, "style": style, "speed": speed_in})[0].reshape(-1)
        if SENTENCE_GAP_S:
            audio = np.concatenate([audio, np.zeros(int(SENTENCE_GAP_S * SAMPLE_RATE), np.float32)])
        return _pcm16(audio)

    def synth(text: str) -> Iterator[bytes]:
        try:
            for sentence in split_text(text):
                for phonemes in pieces(sentence):
                    yield render(phonemes)
        except (BundleError, SynthesisError):
            raise
        except Exception as exc:  # never let text or phonemes reach the server's logs via an exception message
            raise SynthesisError(f"synthesis failed: {type(exc).__name__}") from None

    return synth, SAMPLE_RATE
