#!/usr/bin/env python3
"""Chooses checkpoint, sliding window and cutoff on VALIDATION only, then
reports every split at that choice.

Detector (an emulation of ESPHome micro_wake_word's streaming_model.cpp):
  * the model emits a uint8 probability every 30 ms (3 feature frames);
  * it detects when the sum of the last W probabilities is greater than
    cutoff_u8 * W, where cutoff_u8 = int(cutoff * 255);
  * after a detection, probabilities restart from zero and the next
    REFRACTORY inferences are ignored (100 x 30 ms = 3 s);
  * a clip "accepts" if it detects anywhere in its stream.

Rule: among all candidates x W x cutoff with 0 false accepts on the full
9.7 h dinner_party_eval validation_ambient, take the highest validation
recall; ties go to fewer validation hard-negative accepts, then the higher
cutoff (more margin).

  python -I choose.py --eval-dir EVAL --out report.json [--candidates a b c]
"""

import argparse
import csv
import glob
import json
import os

import numpy as np

REFRACTORY = 100
WINDOWS = (3, 5, 7)
CUTOFFS = [round(c, 2) for c in np.arange(0.50, 1.0, 0.01)]


def split_streams(npz, name):
    probs, lengths = npz[name + "__probs"], npz[name + "__lengths"]
    out, start = [], 0
    for n in lengths:
        out.append(probs[start:start + n])
        start += n
    return out


def window_sums(p, w):
    c = np.concatenate([[0], np.cumsum(p.astype(np.int64))])
    idx = np.arange(1, len(p) + 1)
    return c[idx] - c[np.maximum(idx - w, 0)]


def detections(sums, thr):
    cand = np.flatnonzero(sums > thr)
    n, nxt = 0, -1
    for t in cand:
        if t >= nxt:
            n += 1
            nxt = t + REFRACTORY
    return n


def clip_accepts(streams, w, thrs):
    """Fraction of clips with any detection, for each threshold."""
    peaks = np.array([window_sums(s, w).max() if len(s) else 0 for s in streams])
    return np.array([(peaks > t).mean() for t in thrs]), peaks


def ambient_fa(streams, w, thrs):
    sums = [window_sums(s, w) for s in streams]
    return np.array([sum(detections(x, t) for x in sums) for t in thrs])


def evaluate_candidate(path, sets_info):
    npz = np.load(path)
    res = {}
    for w in WINDOWS:
        thrs = [int(c * 255) * w for c in CUTOFFS]
        r = {}
        for name, info in sets_info.items():
            streams = split_streams(npz, name)
            if name.endswith("ambient"):
                fa = ambient_fa(streams, w, thrs)
                r[name] = {"fa": fa.tolist(), "hours": info["hours"],
                           "fa_per_hour": (fa / info["hours"]).tolist()}
            else:
                acc, _ = clip_accepts(streams, w, thrs)
                r[name] = {"accept_rate": acc.tolist(), "n": len(streams)}
        res[w] = r
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates", nargs="*", default=None)
    args = ap.parse_args()

    names = args.candidates or sorted(os.path.basename(os.path.dirname(p)) for p in
                                      glob.glob(os.path.join(args.eval_dir, "*", "streams.npz")))
    results, rows = {}, []
    for name in names:
        info = json.load(open(os.path.join(args.eval_dir, name, "info.json")))
        res = evaluate_candidate(os.path.join(args.eval_dir, name, "streams.npz"), info["sets"])
        results[name] = res
        for w, r in res.items():
            for i, c in enumerate(CUTOFFS):
                row = {"candidate": name, "window": w, "cutoff": c}
                for set_name, v in r.items():
                    if "fa" in v:
                        row[f"{set_name}_fa"] = v["fa"][i]
                        row[f"{set_name}_fa_per_h"] = round(v["fa_per_hour"][i], 3)
                    else:
                        row[f"{set_name}_accept"] = round(v["accept_rate"][i], 4)
                rows.append(row)

    with open(os.path.splitext(args.out)[0] + "_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    viable = [r for r in rows if r["val_ambient_fa"] == 0]
    if not viable:
        best = None
    else:
        best = max(viable, key=lambda r: (r["val_pos_accept"], -r.get("val_neg_accept", 0),
                                          r["cutoff"]))
    # Per candidate: best validation recall at 0 val-ambient FA (for the curve)
    per_candidate = {}
    for name in names:
        v = [r for r in viable if r["candidate"] == name]
        per_candidate[name] = (max(v, key=lambda r: (r["val_pos_accept"], -r.get("val_neg_accept", 0),
                                                      r["cutoff"])) if v else None)
    json.dump({"rule": "max val recall s.t. 0 FA on validation_ambient; ties: fewer val "
                       "hard-negative accepts, then higher cutoff",
               "refractory_inferences": REFRACTORY, "chosen": best,
               "per_candidate": per_candidate}, open(args.out, "w"), indent=1)
    print(json.dumps(best, indent=1))


if __name__ == "__main__":
    main()
