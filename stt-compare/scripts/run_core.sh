#!/bin/sh
# Budget-trimmed matrix (PC Steward, 21 Oct: ceiling ~US$15): 80 commands x (AU clean, GB clean, room noise) = 240 clips.
# Parakeet v2/v3 and Kroko streaming already ran on all 604 clips (run_matrix.sh) and are scored on the same 240.
set -u
RAW=$1; D=$(dirname "$0"); AUD=$D/../testset/audio; M=$AUD/manifest.jsonl
WY=${WY_DATA:-/home/user/models/wy}; HF=${HF_SNAP:-/home/user/models/hf}
# Qwen3-ASR from a plain folder: onnxruntime >= 1.27 refuses external weights reached through HF-cache symlinks
QWEN=${QWEN_DIR:-/home/user/models/qwen3-asr-0.6b-onnx-int4-merged}
PROMPT=$(cat "$D/../testset/house_prompt.txt")
snap() { ls -d $HF/models--$1/snapshots/* | head -1; }
MAN=$AUD/manifest_core.jsonl; SUF=
run() { name=$1$SUF; shift; [ -f "$RAW/$name.meta.json" ] && return; echo "== $name $(date +%T)"; python -I "$D/wyoming_bench.py" "$name" "$MAN" "$AUD" "$RAW" -- --data-dir "$WY" --language en --cpu-threads 4 "$@" | tail -1; }
run qwen3asr-0.6b-int4 --stt-library qwen3-asr --model "$QWEN"
run qwen3asr-0.6b-int4+prompt --stt-library qwen3-asr --model "$QWEN" --initial-prompt "$PROMPT"
run fw-small.en-int8 --stt-library faster-whisper --model "$(snap Systran--faster-whisper-small.en)" --compute-type int8 --beam-size 5
run fw-small.en-int8+prompt --stt-library faster-whisper --model "$(snap Systran--faster-whisper-small.en)" --compute-type int8 --beam-size 5 --initial-prompt "$PROMPT"
run fw-large-v3-turbo-int8 --stt-library faster-whisper --model "$(snap mobiuslabsgmbh--faster-whisper-large-v3-turbo)" --compute-type int8 --beam-size 5
run fw-large-v3-turbo-int8+prompt --stt-library faster-whisper --model "$(snap mobiuslabsgmbh--faster-whisper-large-v3-turbo)" --compute-type int8 --beam-size 5 --initial-prompt "$PROMPT"
run fw-distil-large-v3-int8 --stt-library faster-whisper --model "$(snap Systran--faster-distil-whisper-large-v3)" --compute-type int8 --beam-size 5
# accent control: the AU speakers without the vowel shift (151 clean clips), for the leader and the Whisper reference
MAN=$AUD/manifest_au0.jsonl; SUF=@au0
run parakeet-v2-int8 --stt-library sherpa --model sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8
run fw-large-v3-turbo-int8 --stt-library faster-whisper --model "$(snap mobiuslabsgmbh--faster-whisper-large-v3-turbo)" --compute-type int8 --beam-size 5
run qwen3asr-0.6b-int4+prompt --stt-library qwen3-asr --model "$QWEN" --initial-prompt "$PROMPT"
echo "== done $(date +%T)"
