#!/bin/sh
# The owner's cooling note (21 Oct): three hot-day cases, after round 2's queue.
cd "$(dirname "$0")"
while [ -n "$WAIT_PID" ] && kill -0 "$WAIT_PID" 2>/dev/null; do sleep 5; done
python3 -B run_eval.py --arm candidate2 --cases cases/own.json --only COOL-01,COOL-02,COOL-03 --out results/r2-cool-candidate2.jsonl
