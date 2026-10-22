#!/usr/bin/env python3
"""v2 selection, on VALIDATION only (fixed before any v2 checkpoint was scored).

Same detector emulation, windows and cutoff grid as v1's choose.py. Over all
candidates x W x cutoff, require
  * 0 false accepts on the full 9.67 h CHiME-6 validation ambient (as v1) and
    0 on the 2 h simulated-TV validation stream (val_tv_ambient);
  * at most 3% accepts on v1's validation hard negatives (val_neg, v1's cap) and
    at most 5% on the v2 far-field validation hard negatives (val_ffneg:
    "Atlas" mid-sentence, hi/pay Atlas, hey Alice/Alex, at last, and v1's
    confusables, new voices, 2-5 m);
then take the highest mean validation recall over v1's validation positives
(val_pos) and the far-field accented validation positives (val_ffpos).
Ties: fewer pooled validation hard-negative accepts, then the higher cutoff.

  python -I choose_v2.py --eval-dir EVAL --out choice.json [--candidates ...]
"""
import argparse
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import choose as C  # noqa: E402  (v1)

MAX_VAL_NEG, MAX_VAL_FFNEG = 0.03, 0.05


def rows_for(eval_dir, name):
    info = json.load(open(os.path.join(eval_dir, name, "info.json")))
    res = C.evaluate_candidate(os.path.join(eval_dir, name, "streams.npz"), info["sets"])
    rows = []
    for w, r in res.items():
        for i, c in enumerate(C.CUTOFFS):
            row = {"candidate": name, "window": w, "cutoff": c}
            for set_name, v in r.items():
                if "fa" in v:
                    row[f"{set_name}_fa"] = v["fa"][i]
                    row[f"{set_name}_fa_per_h"] = round(v["fa_per_hour"][i], 3)
                else:
                    row[f"{set_name}_accept"] = round(v["accept_rate"][i], 4)
                    row[f"{set_name}_n"] = v["n"]
            rows.append(row)
    return rows


def key(r):
    rec = (r["val_pos_accept"] + r["val_ffpos_accept"]) / 2
    neg = ((r["val_neg_accept"] * r["val_neg_n"] + r["val_ffneg_accept"] * r["val_ffneg_n"])
           / (r["val_neg_n"] + r["val_ffneg_n"]))
    return (round(rec, 6), -round(neg, 6), r["cutoff"])


def viable(r):
    return (r["val_ambient_fa"] == 0 and r["val_tv_ambient_fa"] == 0
            and r["val_neg_accept"] <= MAX_VAL_NEG and r["val_ffneg_accept"] <= MAX_VAL_FFNEG)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates", nargs="*", default=None)
    args = ap.parse_args()
    names = args.candidates or sorted(os.path.basename(os.path.dirname(p)) for p in
                                      glob.glob(os.path.join(args.eval_dir, "*", "streams.npz")))
    rows = [r for n in names for r in rows_for(args.eval_dir, n)]
    with open(os.path.splitext(args.out)[0] + "_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if viable(r)]
    best = max(ok, key=key) if ok else None
    per = {n: max([r for r in ok if r["candidate"] == n], key=key, default=None) for n in names}
    json.dump({"rule": __doc__.split("\n\n")[1], "chosen": best, "per_candidate": per},
              open(args.out, "w"), indent=1)
    print(json.dumps(best, indent=1))


if __name__ == "__main__":
    main()
