#!/usr/bin/env python3
"""Synthesise "Hey Atlas" positives, hard negatives or probe phrases.

Uses the pinned rhasspy piper-sample-generator (its generate_audio() and
get_phonemes()) with the LibriTTS-R generator checkpoint. Unlike the
generator's CLI, it picks voices per split so that the 80/10/10 split is by
voice and by template, decided here, before any augmentation.

Output: 16 kHz mono 16-bit WAVs in <out>/<split>/ and <out>/meta.csv.

Run in the synthesis venv, with PSG_ROOT set to the generator checkout:
  PSG_ROOT=/path/to/piper-sample-generator python -I synth.py --kind positive --n 1000 --out /data/pos --seed 1
"""

import argparse
import csv
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import torch
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import templates as T  # noqa: E402

# piper_train (needed to unpickle the generator) lives at the generator repo root
sys.path.insert(0, os.environ["PSG_ROOT"])

from piper.phonemize_espeak import EspeakPhonemizer  # noqa: E402
from piper_sample_generator.__main__ import (  # noqa: E402
    audio_float_to_int16,
    generate_audio,
    get_phonemes,
)

SPLITS = ("train", "validation", "test")
NUM_SPEAKERS = 800  # of 904; the generator's README advises against the rarest speakers


def split_ids(ids, seed, fractions=(0.8, 0.1, 0.1)):
    """Deterministic 80/10/10 assignment of ids."""
    rng = np.random.default_rng(seed)
    ids = list(ids)
    order = rng.permutation(len(ids))
    n_train = int(round(fractions[0] * len(ids)))
    n_val = int(round(fractions[1] * len(ids)))
    out = {}
    for rank, idx in enumerate(order):
        out[ids[idx]] = (
            "train" if rank < n_train else "validation" if rank < n_train + n_val else "test"
        )
    return out


def stratified_split(items, seed):
    """items: list of (template_id, group). Split each group 80/10/10, at least
    one template per split when the group has three or more."""
    by_group = {}
    for tid, group in items:
        by_group.setdefault(group, []).append(tid)
    out = {}
    for gi, (group, tids) in enumerate(sorted(by_group.items())):
        rng = np.random.default_rng(seed + 1000 * gi)
        tids = [tids[i] for i in rng.permutation(len(tids))]
        n = len(tids)
        n_val = max(1, int(round(0.1 * n))) if n >= 3 else 0
        n_test = max(1, int(round(0.1 * n))) if n >= 3 else 0
        for i, tid in enumerate(tids):
            out[tid] = "validation" if i < n_val else "test" if i < n_val + n_test else "train"
    return out


def build_templates(kind):
    """Returns list of dicts: template_id, group, phonemes (string)."""
    phonemizer = EspeakPhonemizer()
    rows = []
    if kind == "positive":
        seen = set()
        for voice in T.POSITIVE_ESPEAK_VOICES:
            for text in T.POSITIVE_TEXTS:
                ph = " ".join("".join(s) for s in phonemizer.phonemize(voice, text))
                if ph in seen:
                    continue
                seen.add(ph)
                rows.append({"group": f"espeak_{voice}", "text": text, "phonemes": ph})
        for group, ph in T.POSITIVE_IPA:
            if ph in seen:
                continue
            seen.add(ph)
            rows.append({"group": group, "text": "Hey Atlas", "phonemes": ph})
        # Families for stratification: au, us, gb, other
        for r in rows:
            g = r["group"]
            r["family"] = (
                "au" if g == "au"
                else "us" if g == "espeak_en-us"
                else "gb" if g in ("espeak_en", "espeak_en-gb-x-rp", "espeak_en-gb-scotland")
                else "other"
            )
    else:
        # Probes: every hard-negative text plus the probe-only confusables,
        # spoken by one split's voices, for per-phrase false-accept reports.
        source = T.HARD_NEGATIVES if kind == "negative" else T.HARD_NEGATIVES + T.PROBE_ONLY
        for group, text in source:
            assert kind == "probe" or not T.is_wake_phrase(text)
            for voice in T.HARD_NEGATIVE_VOICES:
                ph = " ".join("".join(s) for s in phonemizer.phonemize(voice, text))
                rows.append({"group": group, "family": group, "text": text,
                             "voice": voice, "phonemes": ph})
    for i, r in enumerate(rows):
        r["template_id"] = f"{kind[:3]}{i:03d}"
    return rows


def write_wav(path, audio_int16, rate=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(audio_int16.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["positive", "negative", "probe"], required=True)
    ap.add_argument("--n", type=int, required=True, help="total clips across splits")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True, help="generator .pt (with .pt.json beside it)")
    ap.add_argument("--seed", type=int, default=1, help="sampling seed")
    ap.add_argument("--split-seed", type=int, default=20261018, help="voice/template split seed")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--start-index", type=int, default=0, help="first clip index (to extend a set)")
    ap.add_argument("--workers", type=int, default=1, help="probe sets: number of parallel workers")
    ap.add_argument("--only-split", choices=SPLITS, default=None,
                    help="probe sets: generate only this split's voices")
    args = ap.parse_args()

    torch.set_num_threads(int(os.environ.get("SYNTH_THREADS", "4")))
    rng = np.random.default_rng(args.seed)
    torch.manual_seed(args.seed)

    import json
    config = json.load(open(f"{args.model}.json", encoding="utf-8"))
    model = torch.load(args.model, weights_only=False)
    model.eval()

    templates = build_templates(args.kind)
    if args.kind == "probe":
        tsplit = {t["template_id"]: args.only_split or "test" for t in templates}
    elif args.kind == "positive":
        tsplit = stratified_split([(t["template_id"], t["family"]) for t in templates],
                                  args.split_seed + 1)
    else:
        # Split by text (all espeak voices of one text stay together), stratified by group
        texts = sorted({(t["text"], t["group"]) for t in templates})
        text_split = stratified_split(texts, args.split_seed + 2)
        tsplit = {t["template_id"]: text_split[t["text"]] for t in templates}
    spk_split = split_ids(range(NUM_SPEAKERS), args.split_seed)
    speakers = {s: [k for k, v in spk_split.items() if v == s] for s in SPLITS}
    by_split = {s: [t for t in templates if tsplit[t["template_id"]] == s] for s in SPLITS}

    out = Path(args.out)
    for s in SPLITS:
        (out / s).mkdir(parents=True, exist_ok=True)
    meta_path = out / "meta.csv"
    new_file = not meta_path.exists()
    meta_f = open(meta_path, "a", newline="", encoding="utf-8")
    fields = ["file", "split", "kind", "template_id", "group", "family", "text", "phonemes",
              "speaker_1", "speaker_2", "slerp_weight", "length_scale", "noise_scale",
              "noise_scale_w", "duration_s"]
    writer = csv.DictWriter(meta_f, fieldnames=fields)
    if new_file:
        writer.writeheader()
        with open(out / "templates.csv", "w", newline="", encoding="utf-8") as tf:
            tw = csv.DictWriter(tf, fieldnames=["template_id", "split", "group", "family", "text",
                                                "phonemes", "voice"])
            tw.writeheader()
            for t in templates:
                tw.writerow({**{k: t.get(k, "") for k in tw.fieldnames},
                             "split": tsplit[t["template_id"]]})

    # 80/10/10 of clips by split (probe: all in one split)
    if args.kind == "probe":
        split_counts = {s: (args.n if s == (args.only_split or "test") else 0) for s in SPLITS}
    else:
        split_counts = {"train": int(round(0.8 * args.n)), "validation": int(round(0.1 * args.n))}
        split_counts["test"] = args.n - split_counts["train"] - split_counts["validation"]

    idx = args.start_index
    t0 = time.time()
    made = 0
    for split in SPLITS:
        remaining = split_counts[split]
        while remaining > 0:
            b = min(args.batch_size, remaining)
            if args.kind == "probe":
                # Even coverage: a fixed shuffle of the templates, each worker
                # starting at its own offset (worker = start_index // 1e6).
                pool = by_split[split]
                order = np.random.default_rng(args.split_seed).permutation(len(pool))
                offset = (args.start_index // 1000000) * (len(pool) // args.workers)
                tmpl = pool[order[(made // args.batch_size + offset) % len(pool)]]
            else:
                tmpl = by_split[split][rng.integers(len(by_split[split]))]
            # Per-batch prosody settings, per-clip voices
            # Slow rates stretch a comma into an unnatural 1-2 s pause, so the
            # comma templates get a narrower range; the others go to 1.5.
            slowest = 1.15 if "," in tmpl["phonemes"] else 1.5
            length_scale = float(rng.uniform(0.75, slowest))
            noise_scale = float(rng.uniform(0.4, 0.9))
            noise_scale_w = float(rng.uniform(0.5, 1.0))
            slerp_weight = float(rng.uniform(0.0, 1.0))
            spk = speakers[split]
            s1 = rng.choice(spk, size=b)
            same = rng.random(b) < 0.4
            s2 = np.where(same, s1, rng.choice(spk, size=b))
            ids = get_phonemes("en-us", config, tmpl["phonemes"], phoneme_input=True)
            with torch.no_grad():
                audio, phoneme_samples = generate_audio(
                    model, torch.LongTensor(s1), torch.LongTensor(s2), [ids] * b,
                    slerp_weight, noise_scale, noise_scale_w, length_scale, None)
                for i in range(audio.shape[0]):
                    last = int(phoneme_samples[i].flatten().sum().item())
                    audio[i, 0, last + 1:] = 0
            audio_int16 = audio_float_to_int16(audio.cpu().numpy())
            for i in range(b):
                a = np.trim_zeros(audio_int16[i].flatten()).astype(np.float32)
                a16 = resample_poly(a, 320, 441)  # 22050 -> 16000 Hz
                a16 = np.clip(np.round(a16), -32768, 32767).astype(np.int16)
                name = f"{args.kind[:3]}_{idx:06d}.wav"
                write_wav(out / split / name, a16)
                writer.writerow({
                    "file": f"{split}/{name}", "split": split, "kind": args.kind,
                    "template_id": tmpl["template_id"], "group": tmpl["group"],
                    "family": tmpl["family"], "text": tmpl["text"], "phonemes": tmpl["phonemes"],
                    "speaker_1": int(s1[i]), "speaker_2": int(s2[i]),
                    "slerp_weight": round(slerp_weight if s1[i] != s2[i] else 0.0, 4),
                    "length_scale": round(length_scale, 4), "noise_scale": round(noise_scale, 4),
                    "noise_scale_w": round(noise_scale_w, 4),
                    "duration_s": round(len(a16) / 16000, 4),
                })
                idx += 1
            remaining -= b
            made += b
            if made % (args.batch_size * 20) == 0:
                meta_f.flush()
                rate = made / (time.time() - t0)
                print(f"{args.kind}: {made}/{args.n} clips, {rate:.1f}/s", flush=True)
    meta_f.close()
    print(f"done: {made} clips in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
