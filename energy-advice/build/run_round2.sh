#!/bin/sh
# Round 2 (PC Steward, owner-approved): candidate2 on Codex 49's 40 and the 14 dishwasher states, then EN012/EN015/EN017/EN038 to 3 repeats.
cd "$(dirname "$0")"
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --out results/r2-codex-candidate2.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/own.json --only DW-01,DW-02,DW-03,DW-04,DW-05,DW-06,DW-07,DW-08,DW-09,DW-10,DW-11,DW-12,DW-13,DW-14 --out results/r2-dw-candidate2.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN012,EN015,EN017,EN038 --repeats 3 --out results/r2-codex-candidate2.jsonl
