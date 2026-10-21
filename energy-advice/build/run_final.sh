#!/bin/sh
# Round 2, frozen build (04:10 UTC): one consistent pass over every case the round-2 fixes touch. Resumable.
cd "$(dirname "$0")"
C=EN004,EN012,EN015,EN016,EN017,EN018,EN019,EN020,EN021,EN022,EN023,EN025,EN026,EN029,EN035,EN038,EN039,EN040
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only $C --out results/r2-final-codex.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/own.json --only DW-05,DW-07,DW-08,DW-12,DW-13,COOL-01,COOL-02,COOL-03 --out results/r2-final-own.jsonl
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN012,EN015,EN017,EN038 --repeats 3 --out results/r2-final-codex.jsonl
