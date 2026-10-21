#!/bin/sh
# EN040 ran on the card before the typical-duration label: redo it with the final card (after the cooling cases).
cd "$(dirname "$0")"
while [ -n "$WAIT_PID" ] && kill -0 "$WAIT_PID" 2>/dev/null; do sleep 5; done
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN040 --out results/r2-redo2-candidate2.jsonl
