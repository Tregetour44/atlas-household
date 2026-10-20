#!/bin/sh
# PC Steward's order (20 Oct 22:1x Sydney): candidate arm on everything, then the current prompt on a 25-case subset. Resumable.
cd "$(dirname "$0")"
while [ -n "$WAIT_PID" ] && kill -0 "$WAIT_PID" 2>/dev/null; do sleep 5; done
python3 -B run_eval.py --arm candidate --cases cases/own.json --out results/own-candidate.jsonl
python3 -B run_eval.py --arm candidate --cases cases/codex.json --out results/codex-candidate.jsonl
python3 -B run_eval.py --arm current --cases cases/baseline-subset.json --out results/subset-current.jsonl
