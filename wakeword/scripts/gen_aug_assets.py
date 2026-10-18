#!/usr/bin/env python3
"""Generate synthetic room impulse responses and background noise.

Stands in for the notebook's MIT impulse responses, AudioSet and FMA (whose
rights are unclear): nothing here is recorded audio. Each split gets its own
set (its own seed), and the babble uses only that split's own synthetic
hard-negative clips, so augmentation never crosses a split.

  python -I gen_aug_assets.py --out /data/aug --split train --seed 11 \
      --babble-dir /data/neg_w0/train --babble-dir /data/neg_w1/train
"""

import argparse
import glob
import os
import wave

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 16000


def write_wav(path, x):
    x = np.asarray(x, dtype=np.float64)
    peak = np.max(np.abs(x)) + 1e-9
    x = x / peak * 0.9
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768


def band(x, lo, hi, order=4):
    nyq = SR / 2
    if lo <= 0:
        sos = butter(order, hi / nyq, btype="low", output="sos")
    elif hi >= nyq:
        sos = butter(order, lo / nyq, btype="high", output="sos")
    else:
        sos = butter(order, [lo / nyq, hi / nyq], btype="band", output="sos")
    return sosfilt(sos, x)


def colored(rng, n, exponent):
    """1/f^exponent noise (0 white, 1 pink, 2 brown, -1 blue)."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    spec = spec / f ** (exponent / 2)
    x = np.fft.irfft(spec, n)
    return x / (np.std(x) + 1e-9)


def synth_rir(rng):
    """Exponentially decaying, band-dependent noise tail plus early reflections."""
    rt60 = rng.uniform(0.12, 0.9)
    length = int(min(1.0, 1.2 * rt60 + 0.05) * SR)
    t = np.arange(length) / SR
    rir = np.zeros(length)
    predelay = int(rng.uniform(0, 0.004) * SR)
    rir[predelay] = 1.0
    # Early reflections (walls, table, ceiling)
    for _ in range(rng.integers(4, 14)):
        d = predelay + int(rng.uniform(0.002, 0.05) * SR)
        if d < length:
            rir[d] += rng.choice([-1, 1]) * rng.uniform(0.15, 0.7) * np.exp(-d / SR / rt60 * 3)
    # Late tail: higher bands decay faster (absorption)
    tail = np.zeros(length)
    edges = [(0, 500), (500, 1500), (1500, 4000), (4000, 8000)]
    for k, (lo, hi) in enumerate(edges):
        band_rt = rt60 * (1.0 - 0.15 * k) * rng.uniform(0.85, 1.15)
        decay = np.exp(-6.9 * t / max(band_rt, 0.05))
        tail += band(rng.standard_normal(length), lo, hi, 2) * decay
    onset = predelay + int(rng.uniform(0.005, 0.02) * SR)
    tail[:onset] = 0
    drr = 10 ** (rng.uniform(-6, 8) / 20)  # direct-to-reverberant ratio
    tail = tail / (np.sqrt(np.sum(tail ** 2)) + 1e-9) / drr
    rir = rir + tail
    return rir / (np.max(np.abs(rir)) + 1e-9)


def hum(rng, n, mains=50.0):
    t = np.arange(n) / SR
    f0 = mains * rng.choice([1, 2]) * rng.uniform(0.995, 1.005)
    x = sum(rng.uniform(0.1, 1.0) / k * np.sin(2 * np.pi * f0 * k * t + rng.uniform(0, 6.3))
            for k in range(1, 8))
    return x / (np.std(x) + 1e-9)


def fan(rng, n):
    x = colored(rng, n, rng.uniform(1.0, 2.0))
    x = band(x, 20, rng.uniform(800, 3000))
    t = np.arange(n) / SR
    am = 1 + rng.uniform(0, 0.3) * np.sin(2 * np.pi * rng.uniform(0.2, 8) * t)
    x = x * am + rng.uniform(0, 0.5) * hum(rng, n)
    return x


def rain(rng, n):
    x = band(colored(rng, n, rng.uniform(-0.5, 0.8)), rng.uniform(300, 1500), 7900)
    drops = np.zeros(n)
    idx = rng.integers(0, n, size=int(rng.uniform(5, 60) * n / SR))
    drops[idx] = rng.uniform(-1, 1, size=idx.size) * rng.uniform(2, 8)
    drops = band(drops, 1000, 7900)
    return x + drops


def clatter(rng, n):
    """Kitchen clinks, taps and knocks: damped sinusoids and filtered clicks."""
    x = 0.05 * colored(rng, n, 1.0)
    for _ in range(int(rng.uniform(3, 25) * n / SR / 10 * 10)):
        start = rng.integers(0, n - SR // 4)
        dur = int(rng.uniform(0.02, 0.25) * SR)
        tt = np.arange(dur) / SR
        f = rng.uniform(300, 6000)
        ev = np.sin(2 * np.pi * f * tt) * np.exp(-tt * rng.uniform(15, 120))
        if rng.random() < 0.5:
            ev += band(rng.standard_normal(dur), 200, 7000) * np.exp(-tt * rng.uniform(30, 200))
        x[start:start + dur] += ev * rng.uniform(0.3, 3)
    return x


def tones(rng, n):
    """Music-like: random notes with harmonics, envelopes and simple chords."""
    x = np.zeros(n)
    t_note = 0
    while t_note < n:
        dur = int(rng.uniform(0.1, 0.8) * SR)
        tt = np.arange(dur) / SR
        env = np.minimum(1, tt / 0.01) * np.exp(-tt * rng.uniform(1, 8))
        for _ in range(rng.integers(1, 4)):
            midi = rng.integers(40, 84)
            f0 = 440 * 2 ** ((midi - 69) / 12)
            note = sum(rng.uniform(0.2, 1) / k * np.sin(2 * np.pi * f0 * k * tt)
                       for k in range(1, 6) if f0 * k < 7900)
            seg = x[t_note:t_note + dur]
            seg += (note * env)[:len(seg)]
        t_note += int(dur * rng.uniform(0.5, 1.0))
    if rng.random() < 0.5:  # a beat
        beat = np.zeros(n)
        period = int(SR * 60 / rng.uniform(70, 140))
        for s in range(0, n - 800, period):
            beat[s:s + 800] += band(rng.standard_normal(800), 40, 200) * np.exp(-np.arange(800) / 150)
        x += beat * rng.uniform(0.5, 2)
    return x


def babble(rng, n, clips):
    """2-6 overlapping synthetic talkers (this split's hard negatives only)."""
    x = np.zeros(n)
    for _ in range(rng.integers(2, 7)):
        pos = rng.integers(0, SR)
        gain = rng.uniform(0.3, 1.0)
        while pos < n:
            c = clips[rng.integers(len(clips))]
            seg = c[: n - pos]
            x[pos:pos + len(seg)] += seg * gain
            pos += len(c) + rng.integers(0, SR // 2)
    x = band(x, 80, rng.uniform(3000, 7500))
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-rir", type=int, default=300)
    ap.add_argument("--n-noise", type=int, default=420)
    ap.add_argument("--noise-seconds", type=float, default=8.0)
    ap.add_argument("--babble-dir", action="append", default=[])
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    rir_dir = os.path.join(args.out, args.split, "rir")
    noise_dir = os.path.join(args.out, args.split, "noise")
    os.makedirs(rir_dir, exist_ok=True)
    os.makedirs(noise_dir, exist_ok=True)

    for i in range(args.n_rir):
        write_wav(os.path.join(rir_dir, f"rir_{i:04d}.wav"), synth_rir(rng))

    babble_clips = []
    for d in args.babble_dir:
        for p in sorted(glob.glob(os.path.join(d, "*.wav")))[:3000]:
            babble_clips.append(read_wav(p))

    kinds = ["white", "pink", "brown", "fan", "hum", "rain", "clatter", "tones"]
    if babble_clips:
        kinds.append("babble")
    n = int(args.noise_seconds * SR)
    for i in range(args.n_noise):
        kind = kinds[i % len(kinds)]
        if kind == "white":
            x = colored(rng, n, 0)
        elif kind == "pink":
            x = colored(rng, n, 1)
        elif kind == "brown":
            x = band(colored(rng, n, 2), 20, 7900)
        elif kind == "fan":
            x = fan(rng, n)
        elif kind == "hum":
            x = hum(rng, n) + 0.1 * colored(rng, n, 1)
        elif kind == "rain":
            x = rain(rng, n)
        elif kind == "clatter":
            x = clatter(rng, n)
        elif kind == "tones":
            x = tones(rng, n)
        else:
            x = babble(rng, n, babble_clips)
        if rng.random() < 0.4:  # put some noise "in the room" too
            x = fftconvolve(x, synth_rir(rng))[:n]
        write_wav(os.path.join(noise_dir, f"{kind}_{i:04d}.wav"), x)
    print(f"{args.split}: {args.n_rir} RIRs, {args.n_noise} noise clips ({len(babble_clips)} babble sources)")


if __name__ == "__main__":
    main()
