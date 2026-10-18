#!/bin/sh
# Streams candidate checkpoints of one run over every evaluation set
# (evaluate.py), J at a time, then sweeps window/cutoff on validation
# (choose.py).
# usage: run_eval.sh RUN_DIR STREAM_EVAL_DIR EVAL_DIR J WEIGHTS...
set -eu
RUN=$1; SE=$2; OUT=$3; J=$4; shift 4
: "${MWW_PY:?}"; : "${NEG:?set NEG to the negative-set root}"; : "${NEGX:?set NEGX to the derived-set root}"
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
n=0
for W in "$@"; do
  name=$(basename "$W" .weights.h5 | sed 's/^[0-9]*_weights_/s/')
  [ -f "$OUT/$name/streams.npz" ] && continue
  "$MWW_PY" -I "$HERE/evaluate.py" --train-dir "$RUN" --weights "$W" --name "$name" --eval-dir "$OUT" \
    --set "train_pos=$SE/training/positive_*_mmap" \
    --set "train_neg=$SE/training/negative_*_mmap" \
    --set "val_pos=$SE/validation/positive_*_mmap" \
    --set "val_neg=$SE/validation/negative_*_mmap" \
    --set "test_pos=$SE/testing/positive_*_mmap" \
    --set "test_neg=$SE/testing/negative_*_mmap" \
    --set "test_probe=$SE/testing/probe_*_mmap" \
    --ambient "train_ambient=$NEGX/train_ambient_sample/*_mmap" \
    --ambient "val_ambient=$NEG/dinner_party_eval/validation_ambient/*_mmap" \
    --ambient "test_ambient=$NEG/dinner_party_eval/testing_ambient/*_mmap" \
    > "$OUT/$name.log" 2>&1 &
  n=$((n + 1))
  if [ $((n % J)) -eq 0 ]; then wait; fi
done
wait
"$MWW_PY" -I "$HERE/choose.py" --eval-dir "$OUT" --out "$OUT/choice.json"
