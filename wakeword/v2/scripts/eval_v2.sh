#!/bin/sh
# Streams models over every v1 and v2 evaluation set (v1's evaluate.py), J at a time.
# usage: eval_v2.sh RUN_DIR EVAL_DIR J NAME=WEIGHTS|NAME=tflite:PATH ...
# needs MWW_PY, SE1 (v1 sets), SE2 (v2 sets), NEG
set -eu
RUN=$1; OUT=$2; J=$3; shift 3
V1=$(cd "$(dirname "$0")/../../scripts" && pwd)
mkdir -p "$OUT"; n=0
for spec in "$@"; do
  name=${spec%%=*}; w=${spec#*=}
  [ -f "$OUT/$name/streams.npz" ] && continue
  case $w in tflite:*) wa="--weights none --tflite ${w#tflite:}" ;; *) wa="--weights $w" ;; esac
  "$MWW_PY" -I $V1/evaluate.py --train-dir "$RUN" $wa --name "$name" --eval-dir "$OUT" \
    --set "val_pos=$SE1/validation/positive_*_mmap" --set "val_neg=$SE1/validation/negative_*_mmap" \
    --set "test_pos=$SE1/testing/positive_*_mmap" --set "test_neg=$SE1/testing/negative_*_mmap" \
    --set "test_probe=$SE1/testing/probe_*_mmap" --set "test_probe_rhyme=$SE1/testing/probeB_*_mmap" \
    --set "val_ffpos=$SE2/validation/ffpos_*_mmap" --set "val_ffneg=$SE2/validation/ffneg_*_mmap" \
    --set "test_ffpos=$SE2/testing/ffpos_*_mmap" --set "test_ffneg=$SE2/testing/ffneg_*_mmap" \
    --set "test_weak=$SE2/testing/weak_*_mmap" --set "test_weak_near=$SE2/testing/weaknear_*_mmap" \
    --ambient "val_ambient=$NEG/dinner_party_eval/validation_ambient/*_mmap" \
    --ambient "test_ambient=$NEG/dinner_party_eval/testing_ambient/*_mmap" \
    --ambient "val_tv_ambient=$SE2/validation/tv_*_mmap" \
    --ambient "test_tv_ambient=$SE2/testing/tv_*_mmap" > "$OUT/$name.log" 2>&1 &
  n=$((n + 1)); if [ $((n % J)) -eq 0 ]; then wait; fi
done
wait
