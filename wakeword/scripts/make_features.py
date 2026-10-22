#!/usr/bin/env python3
"""Augment synthetic clips and write microWakeWord Ragged MMap features.

Follows the trainer notebook's feature step (Augmentation ->
generate_features_for_clip -> RaggedMmap), with deliberate changes:
  * the split comes from synth.py's meta.csv (by voice and template), not
    from Clips' random split, and each split is augmented only with its own
    synthetic RIRs and noise (gen_aug_assets.py);
  * the augmentation window is sized from the measured clip durations;
  * features are 10 ms (pymicro-features, the trainer's frontend), stored
    once per augmented clip as uint16 (see below).

  python -I make_features.py --synth /data/pos/w0 --synth /data/pos/w1 \
     --aug /data/aug --out /data/features/pos --kind positive --duration 3.2
"""

import argparse
import csv
import os
import sys
import wave

import numpy as np
from mmap_ninja.ragged import RaggedMmap

from microwakeword.audio.audio_utils import generate_features_for_clip
from microwakeword.audio.augmentation import Augmentation

SPLITS = {"train": "training", "validation": "validation", "test": "testing"}


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def make_augmenter(kind, split, aug_root, duration, stream_eval=False):
    rir = os.path.join(aug_root, split, "rir")
    noise = os.path.join(aug_root, split, "noise")
    if stream_eval:
        jitter = (0.6, 1.0)  # streaming evaluation: room for the detector after the phrase
    elif kind == "positive":
        jitter = (0.195, 0.205)  # as the notebook: the word ends ~0.2 s before the window end
    else:
        jitter = (0.0, 0.6)  # hard negatives end anywhere in the last 0.6 s
    return Augmentation(
        augmentation_duration_s=duration,
        augmentation_probabilities={
            "SevenBandParametricEQ": 0.25,
            "TanhDistortion": 0.1,
            "PitchShift": 0.25,
            "BandStopFilter": 0.1,
            "AddColorNoise": 0.25,
            "AddBackgroundNoise": 0.75,
            "Gain": 1.0,
            "GainTransition": 0.2,
            "RIR": 0.6,
        },
        impulse_paths=[rir],
        background_paths=[noise],
        background_min_snr_db=-2,
        background_max_snr_db=15,
        min_gain_db=-30,
        max_gain_db=0,
        min_jitter_s=jitter[0],
        max_jitter_s=jitter[1],
    )


def generator(rows, root_of, augmenter, repeat, slide_frames, seed):
    np.random.seed(seed)
    import random
    random.seed(seed)
    for _ in range(repeat):
        for r in rows:
            audio = read_wav(os.path.join(root_of[id(r)], r["file"]))
            augmented = augmenter.augment_clip(audio)
            spec = generate_features_for_clip(augmented, step_ms=10)
            # Stored as the frontend's raw uint16 values (lossless: the floats are
            # exact multiples of 0.0390625); the trainer rescales uint16 on load.
            spec = np.round(spec / 0.0390625).astype(np.uint16)
            if slide_frames and slide_frames > 1:
                length = spec.shape[0] - slide_frames + 1
                views = np.lib.stride_tricks.sliding_window_view(spec, (length, spec.shape[1]))
                for i in range(slide_frames):
                    yield np.squeeze(views[i])
            else:
                yield spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synth", action="append", required=True, help="synth.py output dir(s)")
    ap.add_argument("--aug", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--kind", choices=["positive", "negative"], required=True)
    ap.add_argument("--duration", type=float, required=True, help="augmented clip seconds")
    ap.add_argument("--train-repeat", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--splits", default="train,validation,test")
    ap.add_argument("--shard", default="0/1", help="i/N: this process handles rows[i::N]")
    ap.add_argument("--stream-eval", action="store_true",
                    help="evaluation-only features: 0.6-1.0 s of audio after the phrase")
    ap.add_argument("--kind-name", default=None, help="mmap name prefix (default: --kind)")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="use only the first N clips of each split (a fixed sample)")
    args = ap.parse_args()

    rows, root_of = [], {}
    for d in args.synth:
        with open(os.path.join(d, "meta.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                root_of[id(r)] = d
    max_dur = max(float(r["duration_s"]) for r in rows)
    jitter_max = 0.205 if args.kind == "positive" else 0.6
    if args.stream_eval:
        jitter_max = 1.0
    if max_dur + jitter_max > args.duration and (args.kind == "positive" or args.stream_eval):
        sys.exit(f"--duration {args.duration} would truncate a {max_dur:.2f} s clip")

    shard_i, shard_n = (int(v) for v in args.shard.split("/"))
    split_seed = {"train": 0, "validation": 1, "test": 2}
    for split in args.splits.split(","):
        split_rows = [r for r in rows if r["split"] == split]
        if args.max_rows:
            split_rows = split_rows[: args.max_rows]
        split_rows = split_rows[shard_i::shard_n]
        if not split_rows:
            continue
        augmenter = make_augmenter(args.kind, split, args.aug, args.duration, args.stream_eval)
        # The notebook stores 10 frame-shifted copies (slide_frames=10) of each
        # train/validation spectrogram. Here each is stored once and the trainer's
        # "fixed_right_cutoff" truncation (cutoffs 0-9) does the same shifting,
        # at a tenth of the disk.
        repeat = args.train_repeat if split == "train" and not args.stream_eval else 1
        slide = 1
        name = args.kind_name or args.kind
        out_dir = os.path.join(args.out, SPLITS[split], f"{name}_{shard_i}_mmap")
        os.makedirs(os.path.dirname(out_dir), exist_ok=True)
        print(f"{args.kind} {split}: {len(split_rows)} clips x{repeat} (slide {slide}) -> {out_dir}",
              flush=True)
        RaggedMmap.from_generator(
            out_dir=out_dir,
            sample_generator=generator(split_rows, root_of, augmenter, repeat, slide,
                                       args.seed + 1000 * split_seed[split] + shard_i),
            batch_size=200,
            verbose=False,
        )
        # Record which clips (in order) went into the testing features, for per-phrase reports
        if split != "train":
            idx_path = os.path.join(args.out, f"{SPLITS[split]}_index_{name}_{shard_i}.csv")
            with open(idx_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "file", "template_id", "text"])
                for i, r in enumerate(split_rows):
                    w.writerow([i, r["file"], r["template_id"], r["text"]])


if __name__ == "__main__":
    main()
