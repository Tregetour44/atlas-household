#!/bin/sh
# EN026 and EN039 again after the "ON TRACK so far" wording (the model read "SAFE so far" as "safe").
cd "$(dirname "$0")"
while [ -n "$WAIT_PID" ] && kill -0 "$WAIT_PID" 2>/dev/null; do sleep 5; done
python3 -B run_eval.py --arm candidate2 --cases cases/codex.json --only EN026,EN039 --out results/r2-redo3-candidate2.jsonl
