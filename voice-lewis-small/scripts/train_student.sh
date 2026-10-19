#!/usr/bin/env bash
# Fine-tune Piper medium (piper1-gpl) on the filtered teacher corpus, on CPU.
#   new run:  train_student.sh <dataset_dir> <out_dir> <base.ckpt> [extra LightningCLI args]
#   resume:   RESUME=<out_dir>/runs/lightning_logs/version_N/checkpoints/last.ckpt train_student.sh <dataset_dir> <out_dir> - [--trainer.max_steps N]
# Needs: a venv with piper1-gpl installed as in its docs/TRAINING.md (pip install -e '.[train]', build_monotonic_align.sh,
# python setup.py build_ext --inplace). PIPER_PY points at that venv's python.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
ds=$1; out=$2; base=$3; shift 3
PY=${PIPER_PY:-python3}
mkdir -p "$out"
args=(fit --config "$here/../configs/piper_train.yaml"
      --data.voice_name en_GB-lewis_small-medium
      --data.csv_path "$ds/metadata.csv" --data.audio_dir "$ds/wav"
      --data.cache_dir "$out/cache" --data.config_path "$out/en_GB-lewis_small-medium.onnx.json"
      --trainer.default_root_dir "$out/runs")
if [ -n "${RESUME:-}" ]; then args+=(--ckpt_path "$RESUME"); else args+=(--model.warmstart_ckpt "$base"); fi
OMP_NUM_THREADS=${OMP_NUM_THREADS:-4} exec "$PY" "$here/piper_fit.py" "${args[@]}" "$@"
