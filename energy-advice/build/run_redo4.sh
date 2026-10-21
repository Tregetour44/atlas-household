#!/bin/sh
# DW-08 again after the credit advice defers to the energy Lean (it said "after 8 pm" where the energy said the next free window).
cd "$(dirname "$0")"
while [ -n "$WAIT_PID" ] && kill -0 "$WAIT_PID" 2>/dev/null; do sleep 5; done
python3 -B run_eval.py --arm candidate2 --cases cases/own.json --only DW-08 --out results/r2-redo4-candidate2.jsonl
