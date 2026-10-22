#!/usr/bin/env python3
"""v2: augment synthetic clips (near-field as v1, or far-field in a simulated
living room) and write microWakeWord Ragged MMap features.

Per clip, with probability --far-prob (else v1's augmentation, unchanged):
  1. pad / position the clip in the window exactly as v1 (jitter);
  2. "soft voice" with probability --soft-prob: a 3-9 dB high-shelf cut above
     ~1 kHz (less vocal effort means less high-frequency energy);
  3. convolve with a room's talker RIR (2-5 m, gen_farfield_assets.py);
  4. add that room's own noise scenes through their own RIRs, at a realistic
     speech-to-noise ratio for the category:
        tv 0-15 dB, music 0-15 dB, kitchen 3-20 dB, babble 3-15 dB,
        quiet room (pink noise) 25-35 dB;
     and a second scene 3-10 dB lower in a quarter of clips;
  5. the trainer's own Augmentation with its RIR and background noise off
     (EQ, distortion, pitch, band-stop, colour noise, gain -30..0 dB, gain
     transitions), as v1.
The SNR is measured on the reverberant speech's active samples. Positives and
hard negatives get the same treatment, so "far-field" never means "positive".

--kind scene turns 8 s noise scenes (or long TV streams) into features
without a phrase: negatives for training, or ambient streams for evaluation.
"""
import argparse
import csv
import glob
import os
import sys
import wave

import numpy as np
from mmap_ninja.ragged import RaggedMmap
from scipy.signal import fftconvolve, lfilter

from microwakeword.audio.audio_utils import generate_features_for_clip
from microwakeword.audio.augmentation import Augmentation

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import make_features as MF  # noqa: E402  (v1)

SPLITS = MF.SPLITS
SNR = {"tv": (0, 15), "music": (0, 15), "kitchen": (3, 20), "babble": (3, 15)}
CAT_P = {"tv": 0.40, "music": 0.12, "kitchen": 0.20, "babble": 0.13, "quiet": 0.15}


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def far_augmenter(duration, jitter):
    return Augmentation(
        augmentation_duration_s=duration,
        augmentation_probabilities={
            "SevenBandParametricEQ": 0.25, "TanhDistortion": 0.05, "PitchShift": 0.25,
            "BandStopFilter": 0.1, "AddColorNoise": 0.1, "AddBackgroundNoise": 0.0,
            "Gain": 1.0, "GainTransition": 0.2, "RIR": 0.0},
        impulse_paths=[], background_paths=[],
        min_gain_db=-30, max_gain_db=0, min_jitter_s=jitter[0], max_jitter_s=jitter[1])


class Room:
    def __init__(self, ff_split_dir):
        self.rirs = sorted(glob.glob(os.path.join(ff_split_dir, "rir", "room_*_speech.wav")))
        self.scenes = {}
        for p in sorted(glob.glob(os.path.join(ff_split_dir, "scenes", "room_*.wav"))):
            room, cat = os.path.basename(p).split("_")[1:3]
            self.scenes.setdefault(cat, {}).setdefault(room, []).append(p)
        self.cache = {}
        assert self.rirs, ff_split_dir

    def load(self, p):
        if p not in self.cache:
            self.cache[p] = read_wav(p).astype(np.float64)
        return self.cache[p]

    def scene(self, rng, cat, room, n):
        rooms = self.scenes.get(cat, {})
        paths = rooms.get(room) or [p for v in rooms.values() for p in v]
        x = self.load(paths[rng.integers(len(paths))])
        if len(x) < n:
            x = np.tile(x, n // len(x) + 1)
        s = rng.integers(0, len(x) - n + 1)
        return x[s:s + n]


def soft_voice(rng, x):
    """High-shelf cut: subtract a share of the high-passed signal."""
    a = np.exp(-2 * np.pi * rng.uniform(800, 1500) / 16000)
    high = x - lfilter([1 - a], [1, -a], x)
    cut = 10 ** (-rng.uniform(3, 9) / 20)
    return x - (1 - cut) * high


def far_field(rng, x, room, soft_prob):
    """x: the positioned, fixed-length clip (float). Returns the reverberant noisy mix."""
    n = len(x)
    if rng.random() < soft_prob:
        x = soft_voice(rng, x)
    rir_path = room.rirs[rng.integers(len(room.rirs))]
    rid = os.path.basename(rir_path).split("_")[1]
    y = fftconvolve(x, room.load(rir_path))[:n]
    env = np.abs(y)
    active = env > 0.05 * (env.max() + 1e-12)
    ps = np.mean(y[active] ** 2) if active.any() else np.mean(y ** 2)
    cats, p = zip(*CAT_P.items())
    cat = cats[rng.choice(len(cats), p=np.array(p) / sum(p))]
    if cat == "quiet":
        noise = MF_colored(rng, n)
        snr = rng.uniform(25, 35)
        noise *= np.sqrt(ps / (np.mean(noise ** 2) + 1e-12) / 10 ** (snr / 10))
    else:
        noise = room.scene(rng, cat, rid, n)
        snr = rng.uniform(*SNR[cat])
        noise = noise * np.sqrt(ps / (np.mean(noise ** 2) + 1e-12) / 10 ** (snr / 10))
        if rng.random() < 0.25:
            cat2 = ["tv", "music", "kitchen", "babble"][rng.integers(4)]
            n2 = room.scene(rng, cat2, rid, n)
            snr2 = snr + rng.uniform(3, 10)
            noise = noise + n2 * np.sqrt(ps / (np.mean(n2 ** 2) + 1e-12) / 10 ** (snr2 / 10))
    out = y + noise
    peak = np.max(np.abs(out))
    if peak > 0.99:
        out = out / peak * 0.99
    return out.astype(np.float32)


def MF_colored(rng, n):
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / 16000)
    f[0] = f[1]
    x = np.fft.irfft(spec / f ** 0.5, n)
    return x / (np.std(x) + 1e-9)


def to_u16(audio):
    spec = generate_features_for_clip(audio, step_ms=10)
    return np.round(spec / 0.0390625).astype(np.uint16)


def generator(rows, root_of, near, far, room, far_prob, soft_prob, repeat, seed):
    np.random.seed(seed)
    import random
    random.seed(seed)
    rng = np.random.default_rng(seed)
    for _ in range(repeat):
        for r in rows:
            audio = read_wav(os.path.join(root_of[id(r)], r["file"]))
            if rng.random() < far_prob:
                x = far.create_fixed_size_clip(far.add_jitter(audio)).astype(np.float64)
                x = far_field(rng, x, room, soft_prob)
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    out = far.augment(x, sample_rate=16000)
            else:
                out = near.augment_clip(audio)
            yield to_u16(out)


def scene_generator(paths, seed, crop_s=None):
    rng = np.random.default_rng(seed)
    for p in paths:
        x = read_wav(p)
        if crop_s:
            g = 10 ** (rng.uniform(-30, 0) / 20)
            x = x * g / (np.max(np.abs(x)) + 1e-9) * 0.9
        yield to_u16(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synth", action="append", default=[], help="synth output dir(s)")
    ap.add_argument("--aug", help="v1 augmentation assets (near-field branch)")
    ap.add_argument("--ff", required=True, help="gen_farfield_assets.py output root")
    ap.add_argument("--out", required=True)
    ap.add_argument("--kind", choices=["positive", "negative", "scene"], required=True)
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--train-repeat", type=int, default=2)
    ap.add_argument("--far-prob", type=float, default=0.65)
    ap.add_argument("--soft-prob", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--splits", default="train,validation,test")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--stream-eval", action="store_true")
    ap.add_argument("--kind-name", default=None)
    ap.add_argument("--scene-glob", default="scenes/*.wav", help="--kind scene: files under ff/<split>/")
    args = ap.parse_args()
    shard_i, shard_n = (int(v) for v in args.shard.split("/"))
    split_seed = {"train": 0, "validation": 1, "test": 2}
    name = args.kind_name or args.kind

    if args.kind == "scene":
        for split in args.splits.split(","):
            paths = sorted(glob.glob(os.path.join(args.ff, split, args.scene_glob)))[shard_i::shard_n]
            out_dir = os.path.join(args.out, SPLITS[split], f"{name}_{shard_i}_mmap")
            os.makedirs(os.path.dirname(out_dir), exist_ok=True)
            print(f"scene {split}: {len(paths)} files -> {out_dir}", flush=True)
            RaggedMmap.from_generator(out_dir=out_dir, sample_generator=scene_generator(
                paths, args.seed + 1000 * split_seed[split] + shard_i, crop_s=split == "train"),
                batch_size=50, verbose=False)
        return

    rows, root_of = [], {}
    for d in args.synth:
        with open(os.path.join(d, "meta.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                root_of[id(r)] = d
    if args.stream_eval:
        jitter = (0.6, 1.0)
    elif args.kind == "positive":
        jitter = (0.195, 0.205)
    else:
        jitter = (0.0, 0.6)
    max_dur = max(float(r["duration_s"]) for r in rows)
    if (args.kind == "positive" or args.stream_eval) and max_dur + jitter[1] > args.duration:
        too_long = sum(float(r["duration_s"]) + jitter[1] > args.duration for r in rows)
        print(f"note: {too_long} clips longer than the window lose their start", flush=True)

    for split in args.splits.split(","):
        split_rows = [r for r in rows if r["split"] == split][shard_i::shard_n]
        if not split_rows:
            continue
        near = MF.make_augmenter(args.kind, split, args.aug, args.duration, args.stream_eval) \
            if args.far_prob < 1 else None
        far = far_augmenter(args.duration, jitter)
        room = Room(os.path.join(args.ff, split))
        repeat = args.train_repeat if split == "train" and not args.stream_eval else 1
        out_dir = os.path.join(args.out, SPLITS[split], f"{name}_{shard_i}_mmap")
        os.makedirs(os.path.dirname(out_dir), exist_ok=True)
        print(f"{args.kind} {split}: {len(split_rows)} clips x{repeat}, far {args.far_prob} -> {out_dir}",
              flush=True)
        RaggedMmap.from_generator(
            out_dir=out_dir,
            sample_generator=generator(split_rows, root_of, near, far, room, args.far_prob,
                                       args.soft_prob, repeat,
                                       args.seed + 1000 * split_seed[split] + shard_i),
            batch_size=200, verbose=False)
        if split != "train":
            idx_path = os.path.join(args.out, f"{SPLITS[split]}_index_{name}_{shard_i}.csv")
            with open(idx_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "file", "template_id", "text", "engine", "family"])
                for i, r in enumerate(split_rows):
                    w.writerow([i, r["file"], r["template_id"], r["text"], r.get("engine", "libritts_r"),
                                r["family"]])


if __name__ == "__main__":
    main()
