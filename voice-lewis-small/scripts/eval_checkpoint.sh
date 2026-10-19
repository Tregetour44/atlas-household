#!/usr/bin/env bash
# Evaluate one student checkpoint on the eval-only text (held-out families, dev sentences, the four sample lines):
# export to ONNX, render + time on CPU, score (Whisper WER, ECAPA similarity, UTMOS), compare with the teacher.
#   eval_checkpoint.sh <ckpt> <name> <work_dir> [length_scale]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
ckpt=$1; name=$2; W=$3; ls=${4:-}
M="$here/../corpus/manifest.tsv"
out="$W/eval/$name"; mkdir -p "$out"
if [ ! -f "$out/model.onnx" ]; then
  TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 OMP_NUM_THREADS=4 "$W/venv-piper/bin/python" -m piper.train.export_onnx --checkpoint "$ckpt" --output-file "$out/model.onnx" > "$out/export.log" 2>&1
  cp "$W/student/en_GB-lewis_small-medium.onnx.json" "$out/model.onnx.json"
fi
rm -rf "$out/wav"; rm -f "$out/scores.jsonl"
"$W/venv-piper/bin/python" "$here/student_synth.py" "$out/model.onnx" "$M" heldout,dev,sample "$out/wav" "$W/eval/student_rtf.jsonl" "$name" $ls > "$out/synth.log" 2>&1
OMP_NUM_THREADS=4 "$W/venv-eval/bin/python" "$here/score_clips.py" "$M" "$out/scores.jsonl" "$W/ref_lewis.wav" --glob "$out/wav/*.wav" > "$out/score.log" 2>&1
tail -n 1 "$W/eval/student_rtf.jsonl"
OMP_NUM_THREADS=4 "$W/venv-eval/bin/python" "$here/compare.py" teacher "teacher=$W/eval/teacher.jsonl:$W/eval/teacher" "$name=$out/scores.jsonl:$out/wav" 2>/dev/null | tail -n 1
