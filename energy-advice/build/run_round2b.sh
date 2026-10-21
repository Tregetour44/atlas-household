#!/bin/sh
# Round 2 after the card wording fix (01:40 UTC): Codex resumes with the fixed card; the cases that ran with the old wording and are
# affected by it (EN004, EN022, EN023, EN026) are redone; EN012/EN015/EN017/EN038 get 3 repeats, all with the fixed card.
cd "$(dirname "$0")"
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --out results/r2-codex-candidate2.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/own.json --only DW-01,DW-02,DW-03,DW-04,DW-05,DW-06,DW-07,DW-08,DW-09,DW-10,DW-11,DW-12,DW-13,DW-14 --out results/r2-dw-candidate2.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN004,EN022,EN023,EN026,EN035 --out results/r2-redo-candidate2.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN012,EN015,EN017,EN038 --repeats 3 --out results/r2-repeats-candidate2.jsonl
