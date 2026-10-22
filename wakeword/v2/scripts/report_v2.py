#!/usr/bin/env python3
"""Per-clip breakdowns of one evaluated model at one setting (W, cutoff):
  * far-field accented test positives by engine, by accent family and for the
    held-out Australian VCTK speaker p326 (any clip with p326 in its voice);
  * weak-spot phrases (hi/pay Atlas, hey Alice/Alex, at last) on the far-field
    probe set (new voices) and on v1's near-field probe set (v1's test voices);
  * far-field test hard negatives by group (e.g. "Atlas" mid-sentence).
Clip order is rebuilt exactly as make_features(_v2).py wrote it (meta.csv rows
in --synth order, filtered by split, sharded i::N).

  python -I report_v2.py EVAL_DIR/NAME --window 3 --cutoff 0.93 --v2-synth DATA/v2 \
      --v1-synth DATA/v1eval --out breakdown.json
"""
import argparse
import csv
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import choose as C  # noqa: E402

WEAK = ["hi Atlas", "pay Atlas", "hey Alice", "hey Alex", "at last"]


def ordered_rows(dirs, split, shards):
    rows = []
    for d in dirs:
        rows += list(csv.DictReader(open(os.path.join(d, "meta.csv"), encoding="utf-8")))
    rows = [r for r in rows if r["split"] == split]
    out = []
    for i in range(shards):
        out += rows[i::shards]
    return out


def accepts(npz, name, w, thr):
    return np.array([len(s) and C.window_sums(s, w).max() > thr for s in C.split_streams(npz, name)])


def table(acc, keys):
    t = defaultdict(lambda: [0, 0])
    for a, ks in zip(acc, keys):
        for k in ks:
            t[k][0] += int(a)
            t[k][1] += 1
    return {k: {"accepts": v[0], "n": v[1], "rate": round(v[0] / v[1], 4)} for k, v in sorted(t.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("streams_dir")
    ap.add_argument("--window", type=int, required=True)
    ap.add_argument("--cutoff", type=float, required=True)
    ap.add_argument("--v2-synth", required=True)
    ap.add_argument("--v1-synth", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    npz = np.load(os.path.join(a.streams_dir, "streams.npz"))
    thr = int(a.cutoff * 255) * a.window
    res = {"window": a.window, "cutoff": a.cutoff, "threshold_u8": int(a.cutoff * 255)}

    pos = ordered_rows(sorted(glob.glob(os.path.join(a.v2_synth, "pos_*/"))), "test", 4)
    acc = accepts(npz, "test_ffpos", a.window, thr)
    assert len(acc) == len(pos), (len(acc), len(pos))
    res["test_ffpos_by_engine"] = table(acc, [[r.get("engine") or "libritts_r"] for r in pos])
    res["test_ffpos_by_family"] = table(acc, [[r["family"]] for r in pos])
    res["test_ffpos_au_speaker_p326"] = table(
        acc, [["p326 in voice" if "p326" in (r["speaker_1"], r["speaker_2"]) else "other"] for r in pos])
    neg = ordered_rows(sorted(glob.glob(os.path.join(a.v2_synth, "neg_*/"))), "test", 4)
    acc = accepts(npz, "test_ffneg", a.window, thr)
    assert len(acc) == len(neg)
    res["test_ffneg_by_group"] = table(acc, [[r["group"]] for r in neg])
    weak = ordered_rows(sorted(glob.glob(os.path.join(a.v2_synth, "probe_*/"))), "test", 1)
    acc = accepts(npz, "test_weak", a.window, thr)
    assert len(acc) == len(weak)
    res["weak_far_new_voices"] = table(acc, [[r["text"]] for r in weak])
    acc = accepts(npz, "test_weak_near", a.window, thr)
    assert len(acc) == len(weak)
    res["weak_near_new_voices"] = table(acc, [[r["text"]] for r in weak])
    probe = ordered_rows(sorted(glob.glob(os.path.join(a.v1_synth, "probe_w*/"))), "test", 4)
    acc = accepts(npz, "test_probe", a.window, thr)
    assert len(acc) == len(probe)
    v1p = table(acc, [[r["text"]] for r in probe])
    res["v1_probe_near_v1_test_voices"] = v1p
    res["v1_probe_weak_and_named"] = {k: v1p[k] for k in v1p if k in WEAK + [
        "hey, at last", "the atlas", "an atlas", "say Atlas", "ask Atlas tomorrow", "Atlas"]}
    rh = ordered_rows(sorted(glob.glob(os.path.join(a.v1_synth, "probeB_w*/"))), "test", 2)
    acc = accepts(npz, "test_probe_rhyme", a.window, thr)
    assert len(acc) == len(rh)
    res["v1_probe_rhyme"] = table(acc, [[r["text"]] for r in rh])
    json.dump(res, open(a.out, "w"), indent=1)
    for k in ("test_ffpos_by_engine", "test_ffpos_by_family", "test_ffpos_au_speaker_p326",
              "test_ffneg_by_group", "weak_far_new_voices", "weak_near_new_voices", "v1_probe_weak_and_named"):
        print(k, {kk: f'{v["accepts"]}/{v["n"]}' for kk, v in res[k].items()})


if __name__ == "__main__":
    main()
