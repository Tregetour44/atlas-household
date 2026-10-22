#!/usr/bin/env python3
"""Writes a microWakeWord training YAML (the notebook's config, adapted).

Changes from the notebook, on purpose:
  * a hard-negative feature set (synthetic confusable phrases) is added;
  * clip_duration_ms comes from the measured positive durations (--clip-ms);
  * positives are stored once and shifted with "fixed_right_cutoff" 0-9
    (the notebook stores 10 shifted copies instead);
  * the published negative sets use the speech/no_speech/dinner_party
    folders as downloaded (10 ms features, checked); the in-loop ambient
    validation is a 3.2 h subset of dinner_party_eval (memory; see
    make_inloop_ambient.py), DiPCo testing_ambient is unchanged.

  python -I make_config.py --out cfg.yaml --train-dir DIR --pos FEATDIR \
     --hardneg FEATDIR --neg-root NEGDIR --steps 10000 --clip-ms 2500
"""

import argparse
import os

import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--train-dir", required=True)
    ap.add_argument("--pos", required=True)
    ap.add_argument("--hardneg", required=True)
    ap.add_argument("--neg-root", required=True)
    ap.add_argument("--ambient-dir", required=True,
                    help="in-loop ambient set (make_inloop_ambient.py output)")
    ap.add_argument("--steps", type=int, nargs="+", required=True)
    ap.add_argument("--lr", type=float, nargs="+", default=[0.001])
    ap.add_argument("--clip-ms", type=int, required=True)
    ap.add_argument("--neg-class-weight", type=float, nargs="+", default=[20])
    ap.add_argument("--pos-weight", type=float, default=2.0)
    ap.add_argument("--hardneg-weight", type=float, default=3.0)
    ap.add_argument("--hardneg-penalty", type=float, default=1.0)
    ap.add_argument("--time-mask", type=int, default=0)
    ap.add_argument("--freq-mask", type=int, default=0)
    ap.add_argument("--eval-interval", type=int, default=500)
    ap.add_argument("--batch-size", type=int, default=128)
    args = ap.parse_args()

    neg = lambda name: os.path.join(args.neg_root, name)  # noqa: E731
    config = {
        "window_step_ms": 10,
        "train_dir": args.train_dir,
        "features": [
            {"features_dir": args.pos, "sampling_weight": args.pos_weight, "penalty_weight": 1.0,
             "truth": True, "truncation_strategy": "fixed_right_cutoff",
             "fixed_right_cutoffs": list(range(10)), "type": "mmap"},
            {"features_dir": args.hardneg, "sampling_weight": args.hardneg_weight,
             "penalty_weight": args.hardneg_penalty, "truth": False,
             "truncation_strategy": "random", "type": "mmap"},
            {"features_dir": neg("speech"), "sampling_weight": 10.0, "penalty_weight": 1.0,
             "truth": False, "truncation_strategy": "random", "type": "mmap"},
            {"features_dir": neg("dinner_party"), "sampling_weight": 10.0, "penalty_weight": 1.0,
             "truth": False, "truncation_strategy": "random", "type": "mmap"},
            {"features_dir": neg("no_speech"), "sampling_weight": 5.0, "penalty_weight": 1.0,
             "truth": False, "truncation_strategy": "random", "type": "mmap"},
            {"features_dir": args.ambient_dir, "sampling_weight": 0.0,
             "penalty_weight": 1.0, "truth": False, "truncation_strategy": "split",
             "type": "mmap"},
        ],
        "training_steps": args.steps,
        "positive_class_weight": [1],
        "negative_class_weight": args.neg_class_weight,
        "learning_rates": args.lr,
        "batch_size": args.batch_size,
        "time_mask_max_size": [args.time_mask],
        "time_mask_count": [2 if args.time_mask else 0],
        "freq_mask_max_size": [args.freq_mask],
        "freq_mask_count": [2 if args.freq_mask else 0],
        "eval_step_interval": args.eval_interval,
        "clip_duration_ms": args.clip_ms,
        "target_minimization": 0.9,
        "minimization_metric": None,
        "maximization_metric": "average_viable_recall",
    }
    with open(args.out, "w") as f:
        yaml.dump(config, f, sort_keys=False)


if __name__ == "__main__":
    main()
