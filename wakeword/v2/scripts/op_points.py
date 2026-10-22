#!/usr/bin/env python3
"""Operating points of one evaluated model at given cutoffs (any cutoff:
the threshold is int(cutoff * 255) * W, exactly as ESPHome 2026.9.1's
micro_wake_word/__init__.py quantises it). Same detector as v1's choose.py.

  python -I op_points.py STREAMS_DIR --window 3 --cutoffs 0.93 0.90 0.85 0.80 --out ops.csv
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import choose as C  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("streams_dir")
ap.add_argument("--window", type=int, default=3)
ap.add_argument("--cutoffs", type=float, nargs="+", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--label", default="")
args = ap.parse_args()
info = json.load(open(os.path.join(args.streams_dir, "info.json")))
import numpy as np  # noqa: E402
npz = np.load(os.path.join(args.streams_dir, "streams.npz"))
thrs = [int(c * 255) * args.window for c in args.cutoffs]
rows = [{"model": args.label, "window": args.window, "cutoff": c, "threshold_u8": int(c * 255)}
        for c in args.cutoffs]
for name, si in info["sets"].items():
    streams = C.split_streams(npz, name)
    if name.endswith("ambient"):
        fa = C.ambient_fa(streams, args.window, thrs)
        for r, v in zip(rows, fa):
            r[f"{name}_fa"] = int(v)
            r[f"{name}_hours"] = round(si["hours"], 2)
            r[f"{name}_fa_per_h"] = round(v / si["hours"], 3)
    else:
        acc, _ = C.clip_accepts(streams, args.window, thrs)
        for r, v in zip(rows, acc):
            r[f"{name}_accept"] = round(float(v), 4)
            r[f"{name}_n"] = len(streams)
with open(args.out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(json.dumps(r))
