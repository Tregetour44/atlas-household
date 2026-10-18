#!/usr/bin/env python3
"""Reports the chosen model at its chosen window/cutoff on every split, the
per-phrase false-accept rates of the confusable probes (test voices), and
writes the v2 manifest from the export.

  python -I report.py --eval-dir EVAL --stream-eval SE --neg-templates T.csv \
      --arena arena.json --config RUN/training_config.yaml --out-dir wakeword/
"""

import argparse
import csv
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from choose import REFRACTORY, detections, split_streams, window_sums  # noqa: E402

# A v2 model (feature_step_size, streaming state variables) needs the
# micro_wake_word component of ESPHome 2024.7.0 or later.
MIN_ESPHOME_FOR_V2 = "2024.7.0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dir", required=True)
    ap.add_argument("--stream-eval", required=True)
    ap.add_argument("--neg-templates", required=True, help="hard-negative templates.csv")
    ap.add_argument("--arena", required=True, help="arena.py output for the chosen model")
    ap.add_argument("--config", required=True, help="training_config.yaml of the run")
    ap.add_argument("--arena-margin", type=float, default=0.10)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    import yaml
    config = yaml.load(open(args.config), yaml.Loader)
    choice = json.load(open(os.path.join(args.eval_dir, "choice.json")))["chosen"]
    if choice is None:
        sys.exit("no candidate reached 0 false accepts on validation_ambient")
    name, w, cutoff = choice["candidate"], int(choice["window"]), float(choice["cutoff"])
    thr = int(cutoff * 255) * w
    info = json.load(open(os.path.join(args.eval_dir, name, "info.json")))
    npz = np.load(os.path.join(args.eval_dir, name, "streams.npz"))

    metrics, probe_acc = {}, {}
    for set_name, si in info["sets"].items():
        streams = split_streams(npz, set_name)
        if set_name.endswith("ambient"):
            fa = sum(detections(window_sums(s, w), thr) for s in streams)
            metrics[set_name] = {"false_accepts": int(fa), "hours": round(si["hours"], 3),
                                 "fa_per_hour": round(fa / si["hours"], 4)}
        else:
            acc = [bool(len(s) and window_sums(s, w).max() > thr) for s in streams]
            metrics[set_name] = {"n": len(acc), "accepted": int(sum(acc)),
                                 "rate": round(float(np.mean(acc)), 4)}
            if set_name.startswith("test_probe"):
                probe_acc[set_name] = acc

    # Per-phrase accept rates on the probes (test voices)
    tsplit = {}
    for r in csv.DictReader(open(args.neg_templates, encoding="utf-8")):
        tsplit[r["text"]] = r["split"]
    by_text = {}
    for set_name, prefix in (("test_probe", "probe"), ("test_probe_rhyme", "probeB")):
        if set_name not in probe_acc:
            continue
        index = []
        for p in sorted(glob.glob(os.path.join(args.stream_eval, f"testing_index_{prefix}_*.csv"))):
            index += list(csv.DictReader(open(p, encoding="utf-8")))
        assert len(index) == len(probe_acc[set_name]), (set_name, len(index))
        for r, a in zip(index, probe_acc[set_name]):
            by_text.setdefault(r["text"], []).append(a)
    phrases = sorted(({"text": t, "n": len(v), "accepts": int(sum(v)), "rate": round(float(np.mean(v)), 3),
                       "template_split": tsplit.get(t, "probe-only")} for t, v in by_text.items()),
                     key=lambda x: (-x["rate"], x["text"]))
    with open(os.path.join(args.out_dir, "confusables_test_voices.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(phrases[0]))
        wr.writeheader()
        wr.writerows(phrases)

    arena = json.load(open(args.arena))
    arena_size = int(np.ceil(arena["min_arena_bytes_host"] * (1 + args.arena_margin) / 1024) * 1024)
    manifest = {
        "type": "micro",
        "wake_word": "Hey Atlas",
        "author": "Atlas household (private, non-commercial)",
        "website": "https://github.com/OHF-Voice/micro-wake-word",
        "model": "hey_atlas.tflite",
        "trained_languages": ["en"],
        "version": 2,
        "micro": {
            "probability_cutoff": cutoff,
            "feature_step_size": int(config["window_step_ms"]),
            "sliding_window_size": w,
            "tensor_arena_size": arena_size,
            "minimum_esphome_version": MIN_ESPHOME_FOR_V2,
        },
    }
    json.dump(manifest, open(os.path.join(args.out_dir, "hey_atlas.json"), "w"), indent=2)
    summary = {"chosen": choice, "threshold_u8_sum": thr, "refractory_inferences": REFRACTORY,
               "metrics": metrics, "arena": arena, "manifest": manifest,
               "worst_confusables": phrases[:15]}
    json.dump(summary, open(os.path.join(args.out_dir, "results.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
