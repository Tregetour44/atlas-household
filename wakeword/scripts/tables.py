#!/usr/bin/env python3
"""Prints the TRAINING.md result tables (markdown) from report.py outputs,
so the numbers in the write-up are never copied by hand.

  python3 tables.py results/final/results.json [label=results.json ...]
"""
import json
import sys


def pct(m):
    return f"{100 * m['rate']:.1f}% ({m['accepted']}/{m['n']})"


def fa(m):
    return f"{m['fa_per_hour']:.2f} /h ({m['false_accepts']} in {m['hours']:.2f} h)"


def split_table(res):
    m = res["metrics"]
    out = ["| Split | Recall (\"Hey Atlas\") | Hard-negative accepts | False accepts per hour (ambient) |",
           "| --- | --- | --- | --- |"]
    for split, amb in (("train", "train_ambient"), ("val", "val_ambient"), ("test", "test_ambient")):
        name = {"train": "train (sample)", "val": "validation", "test": "test"}[split]
        out.append(f"| {name} | {pct(m[split + '_pos'])} | {pct(m[split + '_neg'])} | {fa(m[amb])} |")
    return "\n".join(out)


def main():
    final = json.load(open(sys.argv[1]))
    print(split_table(final))
    print()
    m = final["metrics"]
    print(f"Probes on test voices: {pct(m['test_probe'])} of the hard-negative and probe-only texts"
          + (f"; rhyme probes {pct(m['test_probe_rhyme'])}" if "test_probe_rhyme" in m else "") + ".")
    print()
    if len(sys.argv) > 2:
        print("| Candidate | Choice | Val recall | Val hard-neg | Val FA (9.67 h) | Test recall | Test hard-neg | Test FA (5.33 h) | Rhyme probes |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for spec in sys.argv[2:]:
            label, path = spec.split("=", 1)
            r = json.load(open(path))
            c, m = r["chosen"], r["metrics"]
            rh = pct(m["test_probe_rhyme"]) if "test_probe_rhyme" in m else "NO DATA"
            print(f"| {label} | {c['candidate']}, W={c['window']}, cutoff {c['cutoff']} | "
                  f"{pct(m['val_pos'])} | {pct(m['val_neg'])} | {m['val_ambient']['false_accepts']} | "
                  f"{pct(m['test_pos'])} | {pct(m['test_neg'])} | {m['test_ambient']['false_accepts']} | {rh} |")


if __name__ == "__main__":
    main()
