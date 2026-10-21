#!/bin/sh
# Budget cut (PC Steward, 15:1x Sydney: about US$10 left): only the credit-rule re-runs. The remaining credit-hour Codex cases, then
# EN012/EN015/EN017/EN038 to 3 repeats. Dishwasher, cooling and EN035 re-runs dropped.
cd "$(dirname "$0")"
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN023,EN025,EN026,EN029,EN038,EN039,EN040 --out results/r2-final-codex.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN012,EN015,EN017,EN038 --repeats 3 --out results/r2-final-codex.jsonl
