#!/bin/sh
# Runs synth.py in W single-thread workers (faster than one multi-thread
# process on CPU). Each worker writes its own directory with its own seed;
# voice/template splits are identical across workers (same --split-seed).
# usage: synth_parallel.sh KIND TOTAL OUTROOT SEEDBASE [WORKERS]
set -eu
KIND=$1; TOTAL=$2; OUTROOT=$3; SEEDBASE=$4; W=${5:-4}
HERE=$(cd "$(dirname "$0")" && pwd)
: "${PSG_ROOT:?set PSG_ROOT}"; : "${PSG_MODEL:?set PSG_MODEL}"; : "${PSG_PY:?set PSG_PY}"
PER=$(( (TOTAL + W - 1) / W ))
i=0
while [ $i -lt $W ]; do
  SYNTH_THREADS=1 PSG_ROOT=$PSG_ROOT "$PSG_PY" -I "$HERE/synth.py" --kind "$KIND" --n $PER \
    --out "$OUTROOT/w$i" --model "$PSG_MODEL" --seed $((SEEDBASE + i)) \
    --start-index $((i * 1000000)) --batch-size 16 > "$OUTROOT/w$i.log" 2>&1 &
  i=$((i + 1))
done
wait
echo "synth $KIND done"
