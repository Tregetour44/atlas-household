#!/bin/sh
# Final settings check for the front-runner (faster-whisper small.en int8 + house prompt): beam 1 (speed) and Silero --vad-filter
# (drops non-speech before decoding), on the core 240 clips and the 12 no-speech clips.
set -u
RAW=$1; D=$(dirname "$0"); AUD=$D/../testset/audio; WY=${WY_DATA:-/home/user/models/wy}; HF=${HF_SNAP:-/home/user/models/hf}
PROMPT=$(cat "$D/../testset/house_prompt.txt")
SMALL=$(ls -d $HF/models--Systran--faster-whisper-small.en/snapshots/* | head -1)
run() { name=$1; man=$2; shift 2; [ -f "$RAW/$name.meta.json" ] && return; echo "== $name $(date +%T)"; python -I "$D/wyoming_bench.py" "$name" "$man" "$AUD" "$RAW" -- --data-dir "$WY" --language en --cpu-threads 4 --stt-library faster-whisper --model "$SMALL" --compute-type int8 --initial-prompt "$PROMPT" "$@" | tail -1; }
run fw-small.en-int8+prompt-beam1 $AUD/manifest_core.jsonl --beam-size 1
run fw-small.en-int8+prompt-beam1@nospeech $AUD/manifest_nospeech.jsonl --beam-size 1
run fw-small.en-int8+prompt-beam1-vadfilter $AUD/manifest_core.jsonl --beam-size 1 --vad-filter
run fw-small.en-int8+prompt-beam1-vadfilter@nospeech $AUD/manifest_nospeech.jsonl --beam-size 1 --vad-filter
run fw-small.en-int8+prompt-vadfilter@nospeech $AUD/manifest_nospeech.jsonl --beam-size 5 --vad-filter
echo "== done"
