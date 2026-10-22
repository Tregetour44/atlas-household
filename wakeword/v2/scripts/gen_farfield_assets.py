#!/usr/bin/env python3
"""v2: simulated living rooms for far-field augmentation (pyroomacoustics).

Each room is a shoebox (3.5-7.5 x 3-6 x 2.4-3.0 m, RT60 0.25-0.8 s, image
source method). The device sits on a shelf or table (0.7-1.2 m high, often
near a wall). Per room:
  * rir_speech: a talker 2-5 m from the device (1.1-1.75 m high: seated or standing);
  * rir_tv: a TV 1-4.5 m from the device, against a wall;
  * rir_side: another source 2-6 m away (kitchen, a second talker, a speaker).
Noise scenes (8 s each) are rendered through that room's TV or side RIR:
  tv       broadcast-style talk (MUSAN us-gov / LibriVox speech, or this split's
           own synthetic sentences), loudspeaker band-limit and compression,
           sometimes with a music bed; sometimes music or a film score alone;
  music    MUSAN music;
  kitchen  synthetic clatter, running water, extractor fan, or MUSAN noise;
  babble   2-5 synthetic talkers (this split's own hard negatives).
Sources are split by file (MUSAN) and by split (synthetic clips), so nothing
crosses train / validation / test. Output: <out>/<split>/rooms.json,
rir/room_XXXX_{speech,tv,side}.wav and scenes/room_XXXX_{cat}_K.wav.

  python -I gen_farfield_assets.py --out /data/ff --split train --seed 111 --rooms 300 \
     --musan /data/musan --speech-clips /data/v2/neg_*/train
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import wave

import numpy as np
import pyroomacoustics as pra
from scipy.signal import fftconvolve

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import gen_aug_assets as A  # noqa: E402  (v1: synthetic noises, band filters)

SR = 16000
SCENE_S = 8.0


def write_wav(path, x, peak=0.9):
    x = np.asarray(x, dtype=np.float64)
    x = x / (np.max(np.abs(x)) + 1e-9) * peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768


def file_split(path, seed=20261022):
    """Deterministic 80/10/10 split of a source file by name."""
    h = hashlib.sha256(f"{seed}:{os.path.relpath(path, os.path.dirname(os.path.dirname(path)))}".encode())
    r = int.from_bytes(h.digest()[:8], "little") / 2 ** 64
    return "train" if r < 0.8 else "validation" if r < 0.9 else "test"


def inside(rng, dims, margin, z_lo, z_hi, wall=False):
    x = rng.uniform(margin, dims[0] - margin)
    y = rng.uniform(margin, dims[1] - margin)
    if wall:  # against a random wall
        side = rng.integers(4)
        if side == 0:
            x = margin
        elif side == 1:
            x = dims[0] - margin
        elif side == 2:
            y = margin
        else:
            y = dims[1] - margin
    return np.array([x, y, rng.uniform(z_lo, z_hi)])


def make_room(rng):
    for _ in range(1000):
        dims = np.array([rng.uniform(3.5, 7.5), rng.uniform(3.0, 6.0), rng.uniform(2.4, 3.0)])
        rt60 = rng.uniform(0.25, 0.8)
        try:
            e_abs, max_order = pra.inverse_sabine(rt60, dims)
        except ValueError:
            continue
        mic = inside(rng, dims, 0.25, 0.7, 1.2, wall=rng.random() < 0.6)
        pos = {}
        for name, (dlo, dhi, zlo, zhi, wall) in {
                "speech": (2.0, 5.0, 1.1, 1.75, False),
                "tv": (1.0, 4.5, 0.6, 1.4, True),
                "side": (2.0, 6.0, 0.9, 1.7, False)}.items():
            for _ in range(300):
                p = inside(rng, dims, 0.3, zlo, zhi, wall)
                if dlo <= np.linalg.norm(p - mic) <= dhi:
                    pos[name] = p
                    break
        if len(pos) < 3:
            continue
        room = pra.ShoeBox(dims, fs=SR, materials=pra.Material(e_abs),
                           max_order=int(min(max_order, 17)), air_absorption=True)
        room.add_microphone(mic)
        for name in ("speech", "tv", "side"):
            room.add_source(pos[name])
        room.compute_rir()
        rirs = {name: np.asarray(room.rir[0][i]) for i, name in enumerate(("speech", "tv", "side"))}
        info = {"dims": dims.round(2).tolist(), "rt60_target": round(rt60, 3),
                "max_order": int(min(max_order, 17)), "mic": mic.round(2).tolist(),
                "dist": {k: round(float(np.linalg.norm(v - mic)), 2) for k, v in pos.items()}}
        return rirs, info
    raise RuntimeError("no room")


def segment(rng, sources, n):
    """A random n-sample stretch, concatenating files from the pool."""
    out = np.zeros(0)
    while len(out) < n:
        x = sources[rng.integers(len(sources))]
        if len(x) > n:
            s = rng.integers(0, len(x) - n)
            x = x[s:s + n]
        out = np.concatenate([out, x])
    return out[:n]


def compress(x, ratio=4.0, win=800):
    """Broadcast-style level compression on a 50 ms RMS envelope."""
    env = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, mode="same") + 1e-8)
    ref = np.percentile(env, 90)
    gain = (env / ref) ** (1.0 / ratio - 1.0)
    gain = np.convolve(gain, np.ones(win) / win, mode="same")
    return x * np.minimum(gain, 8.0)


def tv_chain(rng, x):
    x = A.band(x, rng.uniform(80, 180), rng.uniform(5500, 7800))
    return compress(x, rng.uniform(2.5, 6.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--rooms", type=int, required=True)
    ap.add_argument("--scenes-per-room", type=int, default=3)
    ap.add_argument("--musan", required=True)
    ap.add_argument("--speech-clips", nargs="*", default=[], help="this split's synthetic clip dirs")
    ap.add_argument("--part", default="0/1", help="i/N: rooms i::N (parallel runs)")
    ap.add_argument("--long-tv", type=int, default=0,
                    help="also render this many continuous 10-minute TV streams (MUSAN talk and "
                         "music only, TV chain, in a room of this split) as an ambient test set")
    args = ap.parse_args()
    part_i, part_n = (int(v) for v in args.part.split("/"))
    rng = np.random.default_rng([args.seed, part_i])
    out = os.path.join(args.out, args.split)
    os.makedirs(os.path.join(out, "rir"), exist_ok=True)
    os.makedirs(os.path.join(out, "scenes"), exist_ok=True)

    def pool(pattern, cap=None):
        files = [p for p in sorted(glob.glob(os.path.join(args.musan, pattern), recursive=True))
                 if file_split(p) == args.split]
        return [read_wav(p) for p in files[:cap]], files[:cap]

    talk, talk_f = pool("speech/**/*.wav")
    music, music_f = pool("music/**/*.wav")
    noise, noise_f = pool("noise/**/*.wav")
    synth = []
    for d in args.speech_clips:
        for p in sorted(glob.glob(os.path.join(d, "*.wav")))[:4000]:
            synth.append(read_wav(p))
    n = int(SCENE_S * SR)
    print(f"{args.split} part {part_i}: musan talk {len(talk)} music {len(music)} noise {len(noise)}, "
          f"synthetic clips {len(synth)}", flush=True)

    def scene(cat):
        if cat == "tv":
            r = rng.random()
            if r < 0.5 and talk:
                x = segment(rng, talk, n)
            elif r < 0.8 and synth:
                x = A.babble(rng, n, synth) if rng.random() < 0.2 else segment(rng, synth, n)
            else:
                x = segment(rng, music, n) if music else A.tones(rng, n)
            if music and rng.random() < 0.4:  # music bed under speech
                m = segment(rng, music, n)
                x = x / (np.std(x) + 1e-9) + m / (np.std(m) + 1e-9) * 10 ** (-rng.uniform(8, 20) / 20)
            return tv_chain(rng, x)
        if cat == "music":
            return segment(rng, music, n) if music else A.tones(rng, n)
        if cat == "kitchen":
            r = rng.random()
            if r < 0.3:
                return A.clatter(rng, n)
            if r < 0.5:  # running water: band-limited noise bursts
                x = A.band(A.colored(rng, n, rng.uniform(-0.5, 0.5)), rng.uniform(300, 900), 7900)
                return x * (0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(0.1, 0.5) * np.arange(n) / SR))
            if r < 0.65:
                return A.fan(rng, n)
            return segment(rng, noise, n) if noise else A.clatter(rng, n)
        return A.babble(rng, n, synth) if synth else A.colored(rng, n, 1)

    rooms = {}
    for r in range(part_i, args.rooms, part_n):
        rirs, info = make_room(rng)
        for k, h in rirs.items():
            write_wav(os.path.join(out, "rir", f"room_{r:04d}_{k}.wav"), h)
        info["scenes"] = []
        for k in range(args.scenes_per_room):
            cat = "tv" if k == 0 else rng.choice(["music", "kitchen", "babble", "tv", "kitchen"])
            src = "tv" if cat in ("tv", "music") else "side"
            x = fftconvolve(scene(cat), rirs[src])[:n]
            name = f"room_{r:04d}_{cat}_{k}.wav"
            write_wav(os.path.join(out, "scenes", name), x)
            info["scenes"].append(name)
        rooms[f"{r:04d}"] = info
    if args.long_tv:
        os.makedirs(os.path.join(out, "long_tv"), exist_ok=True)
        m = int(600 * SR)
        for k in range(part_i, args.long_tv, part_n):
            rirs, info = make_room(rng)
            parts, pos = [], 0
            while pos < m:  # alternate programmes: talk, talk over music, music
                seg_n = int(rng.uniform(20, 90) * SR)
                r = rng.random()
                if r < 0.6 and talk:
                    x = segment(rng, talk, seg_n)
                    if music and rng.random() < 0.3:
                        mm = segment(rng, music, seg_n)
                        x = x / (np.std(x) + 1e-9) + mm / (np.std(mm) + 1e-9) * 10 ** (-rng.uniform(8, 20) / 20)
                else:
                    x = segment(rng, music, seg_n)
                x = tv_chain(rng, x)
                parts.append(x / (np.std(x) + 1e-9) * 10 ** (rng.uniform(-4, 4) / 20))
                pos += seg_n
            x = fftconvolve(np.concatenate(parts)[:m], rirs["tv"])[:m]
            write_wav(os.path.join(out, "long_tv", f"tv_{k:02d}.wav"), x, peak=0.5)
            rooms[f"long_tv_{k:02d}"] = info
    json.dump({"split": args.split, "seed": args.seed, "rooms": rooms,
               "musan_files": {"speech": [os.path.relpath(p, args.musan) for p in talk_f],
                               "music": [os.path.relpath(p, args.musan) for p in music_f],
                               "noise": [os.path.relpath(p, args.musan) for p in noise_f]}},
              open(os.path.join(out, f"rooms_{part_i}.json"), "w"), indent=0)
    print(f"{args.split} part {part_i}: {len(rooms)} rooms", flush=True)


if __name__ == "__main__":
    main()
