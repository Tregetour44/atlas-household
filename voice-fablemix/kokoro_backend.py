"""Kokoro-82M "Fable-mix" voice for Atlas's Wyoming TTS server: ONNX Runtime on CPU, misaki British G2P.

Drop-in for the server's ``piper_synth`` factory::

    synth, sample_rate = kokoro_synth(model_dir)          # sample_rate == 24000
    for pcm in synth("Done. Kitchen lights off."):        # 16-bit little-endian mono PCM bytes
        ...

What this module does, and nothing more:

* Loads only from ``model_dir``. Each file in ``BUNDLE`` is read into memory once, its SHA-256 checked against the
  constant below, and only those verified bytes are used, so nothing can be swapped between the check and the use.
  A missing or altered file raises ``BundleError`` before any model is built.
* Never touches the network. It sets the Hugging Face offline flags, turns off ONNX Runtime's telemetry events,
  refuses to start if the spaCy English model is not installed (misaki would otherwise download it), and has no
  download code of its own.
* Never logs or prints text. Errors raised from ``synth`` name only the exception type.
* Splits a reply into sentences (very long ones at clause marks) and yields each piece's PCM as soon as it is
  rendered, so the first audio arrives after the first sentence rather than the whole reply.
* Deterministic: the ONNX graph has no random operators and ONNX Runtime runs with deterministic compute.

The server keeps everything else: admission, size and time caps, one synthesis at a time, the watchdog and text
normalisation. The few Kokoro-specific text fixes below (``REWRITES``, ``LEXICON``) are applied here because they
are written in misaki's phoneme alphabet, which the normaliser should not have to know.
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
SynthFn = Callable[[str], Iterator[bytes]]

MODEL_FILE, CONFIG_FILE = "kokoro-v1.0.onnx", "config.json"
VOICE_FILE, SHORT_VOICE_FILE = "en_GB-fablemix.npy", "en_GB-fablemix-short.npy"
# File name in model_dir -> SHA-256 of its exact bytes. bundle/manifest.json gives each one's source and licence.
BUNDLE: Mapping[str, str] = {
    MODEL_FILE: "8fbea51ea711f2af382e88c833d9e288c6dc82ce5e98421ea61c058ce21a34cb",
    CONFIG_FILE: "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f",
    VOICE_FILE: "5de2db9de4510efd4b3dd9f64bf0cf03530089b2220aec95f43f3b27636fbf80",
    SHORT_VOICE_FILE: "86faab493d94047df677164f5743b9cf62084168bd83cbc1551bf48e39eb1ed5",
}

MAX_PHONEMES = 510  # Kokoro's limit per inference; the voice pack holds one style row per phoneme length
CLAUSE_SPLIT = 200  # a sentence longer than this (in phonemes) is rendered clause by clause, for faster first audio
MERGE_BELOW = 30  # a sentence shorter than this is rendered together with its neighbour (short pieces sound sing-song)
OUTPUT_GAIN = 0.678  # this ONNX export is 3.4 dB louder than Kokoro's PyTorch reference; restores level and headroom
# Short pieces sound sing-song. Up to SHORT_FULL phonemes the style comes from the short-reply pack (same timbre,
# flatter prosody) at row SHORT_FULL; from there it fades linearly to the Fable-mix pack itself at SHORT_NONE.
SHORT_FULL, SHORT_NONE = 40, 60
# Kokoro pads every piece with ~0.27 s of silence before and ~0.3 s after. Each piece is trimmed to EDGE_KEEP_S of
# that and given a pause chosen by its closing punctuation; the last piece of a reply gets FINAL_PAUSE_S.
EDGE_KEEP_S, FINAL_PAUSE_S, CLAUSE_PAUSE_S = 0.03, 0.1, 0.15
PAUSE_S: Mapping[str, float] = {".": 0.3, "!": 0.3, "?": 0.35, "…": 0.35, ":": 0.25, ";": 0.2, "—": 0.2}


def _am_pm(m: re.Match[str]) -> str:
    """ "a m", "p.m." etc. -> "AM" / "PM", keeping a full stop only where it also ends the sentence."""
    ends_sentence = m.group(2) and re.match(r"\s*$|\s+[A-Z\"']", m.string[m.end():])
    return m.group(1).upper() + "M" + ("." if ends_sentence else "")


# Text fixes applied before G2P, in order. Square brackets in the reply are neutralised first, so misaki's inline
# phoneme syntax "[word](/phonemes/)" can only come from this reviewed table, never from the reply.
REWRITES: tuple[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]], ...] = (
    # "seven a m" was read "seven uh em", and "p.m." swallowed a sentence's full stop; "AM" / "PM" read cleanly.
    (re.compile(r"\b([aApP])(?: |\. ?)[mM](\.?)(?=[\s,;:!?\"')]|$)"), _am_pm),
    (re.compile(r"\bwind down\b", re.IGNORECASE), "[Wind](/wˈInd/) Down"),  # the scene; as a name misaki says "wɪnd"
    (re.compile(r"(?:^|(?<=[.!?] ))Timer set\b"), "Timer's set"),  # "Timer set:" was heard as "Time a set" (4 of 8)
)
# Word pronunciations (misaki British phonemes), merged into misaki's gold lexicon at load.
LEXICON: Mapping[str, str] = {
    "ensuite": "ɒnswˈiːt",  # misaki: "ɛnsˈuːt" (Whisper heard "N-suit")
}

_SENTENCE = re.compile(r"(?<=[.!?…])[\"')\]]*\s+")
_CLAUSE = re.compile(r"(?<=[,;:—])\s+")
_OFFLINE_FLAGS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY")


class BundleError(RuntimeError):
    """The model bundle is missing, altered or unusable. Raised at load; the server must not start the voice."""


class SynthesisError(RuntimeError):
    """A reply could not be rendered. Carries no text."""


def verify_bundle(model_dir: str | os.PathLike[str]) -> dict[str, bytes]:
    """Read every bundle file once and return its bytes, or raise ``BundleError`` on any missing or altered file."""
    root, verified = Path(model_dir), {}
    for name, expected in BUNDLE.items():
        try:
            data = (root / name).read_bytes()
        except OSError as exc:
            raise BundleError(f"cannot read bundle file {name}: {type(exc).__name__}") from None
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            raise BundleError(f"sha256 mismatch for {name}: expected {expected}, got {digest}")
        verified[name] = data
    return verified


def build_g2p() -> Any:
    """misaki's British G2P with the espeak-ng fallback (bundled DLL) for unknown words and the house lexicon."""
    import spacy.util

    if not spacy.util.is_package("en_core_web_sm"):
        raise BundleError("spaCy model en_core_web_sm is not installed (install it from requirements.lock)")
    from misaki import en, espeak

    logging.getLogger("phonemizer").disabled = True
    g2p = en.G2P(british=True, fallback=espeak.EspeakFallback(british=True), unk="")
    g2p.lexicon.golds.update(LEXICON)
    return g2p


def prepare(text: str) -> str:
    """Kokoro-specific text fixes; see REWRITES."""
    text = text.replace("[", "(").replace("]", ")")
    for pattern, repl in REWRITES:
        text = pattern.sub(repl, text)
    return text


def _phonemes(g2p: Any, prepared: str, vocab: Mapping[str, int] | None) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        phonemes: str = g2p(prepared)[0].strip()
    end = prepared.rstrip(" \"')")[-1:]  # misaki sometimes drops a closing full stop (after "PM.", for one)
    if end in ".!?" and phonemes and phonemes[-1] not in ".!?…":
        phonemes += end
    return "".join(p for p in phonemes if vocab is None or p in vocab)


def phonemize(g2p: Any, text: str, vocab: Mapping[str, int] | None = None) -> str:
    """misaki phonemes for a piece of text, after ``prepare``. For checking pronunciations; ``synth`` uses
    ``plan_chunks``."""
    return _phonemes(g2p, prepare(text), vocab)


def plan_chunks(g2p: Any, text: str, vocab: Mapping[str, int] | None = None) -> list[str]:
    """The phoneme strings ``synth`` renders, in order: one per sentence, short sentences merged with a neighbour,
    long ones split at clause marks and then at word gaps so that none exceeds ``MAX_PHONEMES``."""
    pieces: list[str] = []
    for sentence in _SENTENCE.split(prepare(text).strip()):
        if not sentence.strip():
            continue
        phonemes = _phonemes(g2p, sentence, vocab)
        if len(phonemes) > CLAUSE_SPLIT:
            parts = [_phonemes(g2p, c, vocab) for c in _CLAUSE.split(sentence) if c.strip()]
        else:
            parts = [phonemes]
        for part in parts:
            while len(part) > MAX_PHONEMES:
                cut = part.rfind(" ", 0, MAX_PHONEMES)
                cut = cut if cut > 0 else MAX_PHONEMES
                pieces.append(part[:cut].strip())
                part = part[cut:].strip()
            if any(p.isalpha() for p in part):  # punctuation alone renders as a breath or a click; skip it
                pieces.append(part)
    merged: list[str] = []
    for piece in pieces:
        if merged and (len(merged[-1]) < MERGE_BELOW or len(piece) < MERGE_BELOW) and \
                len(merged[-1]) + 1 + len(piece) <= CLAUSE_SPLIT:
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return merged


def trim_edges(audio: Any, end: str, last: bool) -> Any:
    """Cut a rendered piece's leading and trailing silence to EDGE_KEEP_S and append the pause it ends with."""
    import numpy as np

    frame = SAMPLE_RATE // 100
    n = len(audio) // frame
    rms = np.sqrt(np.mean(audio[: n * frame].reshape(n, frame) ** 2, axis=1)) if n else np.zeros(0)
    loud = np.flatnonzero(rms > rms.max() * 0.01) if n else rms  # within 40 dB of the piece's loudest 10 ms
    if not len(loud):
        return audio
    keep = round(EDGE_KEEP_S * 100)
    start, stop = max(loud[0] - keep, 0) * frame, min(loud[-1] + 1 + keep, n) * frame
    pause = FINAL_PAUSE_S if last else PAUSE_S.get(end, CLAUSE_PAUSE_S)
    return np.concatenate([audio[start:stop], np.zeros(round(pause * SAMPLE_RATE), audio.dtype)])


def kokoro_synth(
    model_dir: str | os.PathLike[str], speed: float = 0.95, threads: int | None = None
) -> tuple[SynthFn, int]:
    """Build the Fable-mix synthesiser from a verified bundle.

    Args:
        model_dir: folder holding the files named in ``BUNDLE`` (other files are ignored).
        speed: Kokoro speed factor; 0.95 is the voice-scout setting.
        threads: ONNX Runtime intra-op threads; ``None`` lets ONNX Runtime use one per physical core.

    Returns:
        ``(synth, 24000)``. ``synth(text)`` yields 16-bit mono PCM bytes, one piece per sentence (or clause of a
        long sentence), and yields nothing for empty or whitespace-only text.

    Raises:
        BundleError: a bundle file is missing or altered, or the spaCy English model is not installed.
        ValueError: ``speed`` or ``threads`` is out of range.
    """
    if not 0.5 <= speed <= 2.0:
        raise ValueError("speed must be between 0.5 and 2.0")
    if threads is not None and threads < 1:
        raise ValueError("threads must be a positive integer")
    for flag in _OFFLINE_FLAGS:
        os.environ[flag] = "1"

    files = verify_bundle(model_dir)

    import numpy as np
    import onnxruntime as ort

    vocab: dict[str, int] = json.loads(files[CONFIG_FILE])["vocab"]
    pack, short = (np.load(io.BytesIO(files[f]), allow_pickle=False) for f in (VOICE_FILE, SHORT_VOICE_FILE))
    for p in (pack, short):
        if p.shape != (MAX_PHONEMES, 1, 256) or p.dtype != np.float32:
            raise BundleError("voice pack has the wrong shape or type")
    g2p = build_g2p()

    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.use_deterministic_compute = True
    options.log_severity_level = 3
    options.inter_op_num_threads = 1
    if threads is not None:
        options.intra_op_num_threads = threads
    session = ort.InferenceSession(files.pop(MODEL_FILE), options, providers=["CPUExecutionProvider"])
    speed_in = np.array([speed], dtype=np.float32)

    def style(n: int) -> Any:
        w = min(max((SHORT_NONE - n) / (SHORT_NONE - SHORT_FULL), 0.0), 1.0)
        return pack[n - 1] if w == 0 else (1 - w) * pack[n - 1] + w * short[max(n, SHORT_FULL) - 1]

    def render(phonemes: str, last: bool) -> bytes:
        ids = np.array([[0, *(vocab[p] for p in phonemes), 0]], dtype=np.int64)
        audio = session.run(None, {"input_ids": ids, "style": style(len(phonemes)), "speed": speed_in})[0]
        audio = trim_edges(audio.reshape(-1) * OUTPUT_GAIN, phonemes.rstrip("“”\"")[-1:], last)
        if not np.isfinite(audio).all():
            raise SynthesisError("synthesis failed: non-finite audio")
        return (np.clip(audio, -1.0, 1.0) * 32767.0).round().astype("<i2").tobytes()

    def synth(text: str) -> Iterator[bytes]:
        try:
            chunks = plan_chunks(g2p, text, vocab)
            for i, phonemes in enumerate(chunks):
                yield render(phonemes, last=i == len(chunks) - 1)
        except SynthesisError:
            raise
        except Exception as exc:  # never let text or phonemes reach the server's logs through an exception message
            raise SynthesisError(f"synthesis failed: {type(exc).__name__}") from None

    return synth, SAMPLE_RATE
