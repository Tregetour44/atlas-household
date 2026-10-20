#!/bin/sh
# The full run, in order: own cases (owner, dishwasher, arithmetic) in both arms, then Codex 49's 40 in both arms. Resumable.
cd "$(dirname "$0")"
python3 -B run_eval.py --arm candidate --cases cases/own.json --out results/own-candidate.jsonl
python3 -B run_eval.py --arm current --cases cases/own.json --out results/own-current.jsonl
python3 -B run_eval.py --arm candidate --cases cases/codex.json --out results/codex-candidate.jsonl
python3 -B run_eval.py --arm current --cases cases/codex.json --out results/codex-current.jsonl
