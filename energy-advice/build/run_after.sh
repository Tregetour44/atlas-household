#!/bin/sh
# After the baseline subset: AR-04/13/20 again with the guard's money fix, then the cards-at-end position check (8 cases). Resumable.
cd "$(dirname "$0")"
while [ -n "$WAIT_PID" ] && kill -0 "$WAIT_PID" 2>/dev/null; do sleep 5; done
python3 -B run_eval.py --arm candidate --cases cases/own.json --only AR-04,AR-13,AR-20 --out results/own-candidate-money-rerun.jsonl
python3 -B run_end.py --arm candidate --cases cases/own.json --only OWN-01,DW-01,DW-02,DW-03,DW-07,DW-08,DW-10,DW-11 --out results/position-end-candidate.jsonl
