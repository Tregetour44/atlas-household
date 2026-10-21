"""Render the test set with open synthetic voices, then make room-noise and far-field versions.

Voices (all open, all synthetic; no real recordings are used anywhere):
  AU  Piper en_GB-vctk-medium speakers p326 and p374 (VCTK lists both as Australian men), VCTK p225 and Piper
      en_GB-jenny_dioco-medium (women). All four get an approximate General Australian vowel shift at the phoneme level
      (FACE eI -> 6I, PRICE aI -> QI, GOAT @U -> 6U, FLEECE i: -> @i, final happY I -> i). Piper's phoneme set is RP-based,
      so this is an approximation of an Australian accent, not a recording of one.
  GB  Kokoro v1.0 bm_george, bf_emma, bm_lewis, bf_isabella; Piper en_GB-northern_english_male, en_GB-cori, en_GB-alan.
espeak-ng mis-stresses "pergola" and says "ensuite" as "insoot"; both are fixed at the phoneme level for every voice.

Conditions (16 kHz mono FLAC):
  clean  every command twice: one AU and one GB speaker (302 clips)
  noise  one rendering per command (AU for odd ids, GB for even) + room noise at 5-15 dB SNR:
         aircon/fan, mains hum + fridge, TV babble (other Atlas lines from other voices), kitchen range hood + clatter
  far    the other rendering, through a simulated room (pyroomacoustics image method, 3.5-7 m rooms, RT60 0.35-0.8 s,
         talker 2.5-5 m from the mic), + fan/hum noise at 10-20 dB SNR, + a 120 Hz-7 kHz small-speaker-mic band-pass
  au0    control set: the same AU-speaker clean renderings WITHOUT the vowel shift (151 clips, manifest_au0.jsonl), to
         separate the effect of the approximate accent from the effect of the voices
Usage: python -I render_audio.py OUT_DIR [--au0-only]   (needs piper-tts, kokoro-onnx, pyroomacoustics, soundfile, scipy; ~10 min on 4 vCPU)
Model files are looked up in $STT_MODELS (default /home/user/models): piper/*.onnx, kokoro/kokoro-v1.0.int8.onnx, voices-v1.0.bin.
"""
import json
import os
import re
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("STT_MODELS", "/home/user/models")
SR = 16000
FIX = [("pɜːɡˈəʊlɐ", "pˈɜːɡələ"), ("pɜːɡˈəʊlə", "pˈɜːɡələ"), ("ɪnsˈuːt", "ɒnswˈiːt"), ("ɛnsˈuːt", "ɒnswˈiːt")]

AU = [("au_m_p326", "piper", "en_GB-vctk-medium", "p326"), ("au_f_p225", "piper", "en_GB-vctk-medium", "p225"),
      ("au_m_p374", "piper", "en_GB-vctk-medium", "p374"), ("au_f_jenny", "piper", "en_GB-jenny_dioco-medium", None)]
GB = [("gb_m_george", "kokoro", "bm_george", None), ("gb_f_emma", "kokoro", "bf_emma", None),
      ("gb_m_northern", "piper", "en_GB-northern_english_male-medium", None), ("gb_f_cori", "piper", "en_GB-cori-medium", None),
      ("gb_m_lewis", "kokoro", "bm_lewis", None), ("gb_f_isabella", "kokoro", "bf_isabella", None),
      ("gb_m_alan", "piper", "en_GB-alan-medium", None)]


def au_shift(p: str) -> str:
    p = p.replace("eɪ", "ɐɪ").replace("aɪ", "ɒɪ").replace("əʊ", "ɐʊ").replace("iː", "əi")
    return re.sub(r"(?<![ɐɒaeɔʊəɪ])ɪ(?=[ ,.?!;:]|$)", "i", p)


def fix(p: str) -> str:
    for a, b in FIX:
        p = p.replace(a, b)
    return p


_piper, _kokoro = {}, None


def synth(spk, text, rng, shift=True):
    name, engine, model, sub = spk
    au = name.startswith("au_") and shift
    if engine == "piper":
        from piper import PiperVoice, SynthesisConfig
        if model not in _piper:
            _piper[model] = PiperVoice.load(os.path.join(MODELS, "piper", model + ".onnx"))
        v = _piper[model]
        cfg = SynthesisConfig(speaker_id=v.config.speaker_id_map[sub] if sub else None, length_scale=float(rng.uniform(0.92, 1.12)))
        parts = []
        for sent in v.phonemize(text):
            p = fix("".join(sent))
            if au:
                p = au_shift(p)
            ids = v.phonemes_to_ids([c for c in p if c in v.config.phoneme_id_map])
            parts += [v.phoneme_ids_to_audio(ids, cfg), np.zeros(int(0.12 * v.config.sample_rate), np.float32)]
        a, sr = np.concatenate(parts).astype(np.float32), v.config.sample_rate
    else:
        global _kokoro
        from kokoro_onnx import Kokoro
        if _kokoro is None:
            _kokoro = Kokoro(os.path.join(MODELS, "kokoro", "kokoro-v1.0.int8.onnx"), os.path.join(MODELS, "kokoro", "voices-v1.0.bin"))
        p = fix(_kokoro.tokenizer.phonemize(text, "en-gb"))
        a, sr = _kokoro.create(p, voice=model, speed=float(rng.uniform(0.92, 1.1)), lang="en-gb", is_phonemes=True)
    a = resample_poly(a, 160, sr // 100) if sr != SR else a
    a = a / (np.max(np.abs(a)) + 1e-9) * 0.5
    return np.concatenate([np.zeros(int(0.25 * SR)), a, np.zeros(int(0.35 * SR))]).astype(np.float32)


def colored(n, rng, beta):  # 1/f^beta noise
    f = np.fft.rfftfreq(n, 1 / SR)
    spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) / np.maximum(f, 20) ** (beta / 2)
    x = np.fft.irfft(spec, n)
    return x / (np.std(x) + 1e-9)


def noise(kind, n, rng, babble_pool):
    t = np.arange(n) / SR
    if kind == "aircon":
        x = colored(n, rng, 1.6) + 0.3 * sosfilt(butter(4, [300, 1200], "bandpass", fs=SR, output="sos"), colored(n, rng, 0))
    elif kind == "hum":
        x = sum(np.sin(2 * np.pi * 50 * k * t + rng.uniform(0, 6)) / k for k in (1, 2, 3, 5)) + 0.5 * colored(n, rng, 1.0)
    elif kind == "tv":
        x = np.zeros(n)
        for _ in range(3):
            b = babble_pool[rng.integers(len(babble_pool))]
            off = rng.integers(0, max(1, n // 2))
            m = min(n - off, len(b))
            x[off:off + m] += b[:m]
        x = x + 0.05 * colored(n, rng, 1.0)
    else:  # kitchen: range hood + clatter
        x = sosfilt(butter(2, [150, 3000], "bandpass", fs=SR, output="sos"), colored(n, rng, 0.5))
        for _ in range(rng.integers(2, 5)):
            s = rng.integers(0, n - 2000)
            L = rng.integers(400, 2000)
            x[s:s + L] += 6 * rng.standard_normal(L) * np.exp(-np.arange(L) / (L / 5))
    return x / (np.std(x) + 1e-9)


def mix(sig, nz, snr):
    p = np.mean(sig[np.abs(sig) > 1e-4] ** 2) if np.any(np.abs(sig) > 1e-4) else 1e-6
    return sig + nz * np.sqrt(p / (10 ** (snr / 10)))


def far_field(sig, rng):
    import pyroomacoustics as pra
    L, W, H = rng.uniform(3.5, 7), rng.uniform(3.5, 6), rng.uniform(2.4, 3.0)
    rt60 = rng.uniform(0.35, 0.8)
    e_abs, max_order = pra.inverse_sabine(rt60, [L, W, H])
    room = pra.ShoeBox([L, W, H], fs=SR, materials=pra.Material(e_abs), max_order=min(max_order, 25))
    mic = np.array([rng.uniform(0.3, 1.0), rng.uniform(0.3, W - 0.3), 0.9])
    for _ in range(50):
        src = np.array([rng.uniform(0.3, L - 0.3), rng.uniform(0.3, W - 0.3), 1.5])
        d = np.linalg.norm(src - mic)
        if 2.5 <= d <= 5:
            break
    room.add_source(src.tolist(), signal=sig)
    room.add_microphone(mic.tolist())
    room.simulate()
    y = room.mic_array.signals[0][: len(sig) + int(0.3 * SR)]
    return y, rt60, d, (L, W, H)


def main_au0(out):
    rows = [json.loads(l) for l in open(os.path.join(HERE, "..", "testset", "commands.jsonl"))]
    os.makedirs(os.path.join(out, "clean_au0"), exist_ok=True)
    manifest = []
    for i, r in enumerate(rows):
        rng = np.random.default_rng(1000 + i)  # same seed and speed as the shifted rendering
        spk = AU[i % len(AU)]
        a = synth(spk, r["say"], rng, shift=False)
        fn = f"clean_au0/{r['id']}-{spk[0]}.flac"
        sf.write(os.path.join(out, fn), a, SR, subtype="PCM_16")
        manifest.append({"clip": fn, "id": r["id"], "cond": "clean_au0", "speaker": spk[0], "accent": "au0", "dur": round(len(a) / SR, 2)})
    with open(os.path.join(out, "manifest_au0.jsonl"), "w") as f:
        for m in manifest:
            f.write(json.dumps(m) + "\n")
    print(f"{len(manifest)} control clips -> {out}/clean_au0")


def main(out):
    sys.path.insert(0, HERE)
    rows = [json.loads(l) for l in open(os.path.join(HERE, "..", "testset", "commands.jsonl"))]
    for c in ("clean", "noise", "far"):
        os.makedirs(os.path.join(out, c), exist_ok=True)
    manifest, clean = [], {}
    for i, r in enumerate(rows):
        rng = np.random.default_rng(1000 + i)
        for spk in (AU[i % len(AU)], GB[(i * 3) % len(GB)]):
            a = synth(spk, r["say"], rng)
            clean[(r["id"], spk[0])] = a
            fn = f"clean/{r['id']}-{spk[0]}.flac"
            sf.write(os.path.join(out, fn), a, SR, subtype="PCM_16")
            manifest.append({"clip": fn, "id": r["id"], "cond": "clean", "speaker": spk[0], "accent": spk[0][:2],
                             "dur": round(len(a) / SR, 2)})
        print(r["id"], end=" ", flush=True)
    babble = [a for (cid, s), a in clean.items() if s.startswith("gb_")]
    kinds = ["aircon", "hum", "tv", "kitchen"]
    for i, r in enumerate(rows):
        rng = np.random.default_rng(5000 + i)
        au_s, gb_s = AU[i % len(AU)][0], GB[(i * 3) % len(GB)][0]
        nz_s, far_s = (au_s, gb_s) if i % 2 == 0 else (gb_s, au_s)
        a = clean[(r["id"], nz_s)]
        kind, snr = kinds[i % 4], float(rng.uniform(5, 15))
        pool = [b for (cid, s), b in clean.items() if cid != r["id"] and s != nz_s][:: 7]
        y = mix(a, noise(kind, len(a), rng, pool), snr)
        y = y / (np.max(np.abs(y)) + 1e-9) * 0.6
        fn = f"noise/{r['id']}-{nz_s}.flac"
        sf.write(os.path.join(out, fn), y, SR, subtype="PCM_16")
        manifest.append({"clip": fn, "id": r["id"], "cond": "noise", "speaker": nz_s, "accent": nz_s[:2], "noise": kind,
                         "snr_db": round(snr, 1), "dur": round(len(y) / SR, 2)})
        a = clean[(r["id"], far_s)]
        y, rt60, d, dims = far_field(a, rng)
        kind2, snr2 = ["aircon", "hum"][i % 2], float(rng.uniform(10, 20))
        y = mix(y, noise(kind2, len(y), rng, babble), snr2)
        y = sosfilt(butter(2, [120, 7000], "bandpass", fs=SR, output="sos"), y)
        y = y / (np.max(np.abs(y)) + 1e-9) * 0.6
        fn = f"far/{r['id']}-{far_s}.flac"
        sf.write(os.path.join(out, fn), y, SR, subtype="PCM_16")
        manifest.append({"clip": fn, "id": r["id"], "cond": "far", "speaker": far_s, "accent": far_s[:2], "noise": kind2,
                         "snr_db": round(snr2, 1), "rt60_s": round(rt60, 2), "distance_m": round(d, 2), "dur": round(len(y) / SR, 2)})
    with open(os.path.join(out, "manifest.jsonl"), "w") as f:
        for m in manifest:
            f.write(json.dumps(m) + "\n")
    print(f"\n{len(manifest)} clips, {sum(m['dur'] for m in manifest) / 60:.1f} min -> {out}")


if __name__ == "__main__":
    main_au0(sys.argv[1]) if "--au0-only" in sys.argv else main(sys.argv[1])
