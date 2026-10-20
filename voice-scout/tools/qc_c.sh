#!/bin/bash
# Qwen3-TTS C engine (int8, ICL clone of the WORLD-lowered Fable reference): timing + renders
cd /home/user/vs; mkdir -p out/cq
T1="Good evening. The house is in order: battery at eighty percent, solar's done for the day, and the evening credit looks safe. I'd hold off on the dryer until eight, unless you're feeling reckless."
QB=$(ls -d ~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-0.6B-Base/snapshots/*/)
for j in 4 2; do
  for id in L06 L09 L03; do
    text=$(grep "^$id" tools/lines.tsv | cut -f2)
    s=$(date +%s.%N)
    src-qwen3c/qwen_tts -d $QB --int8 -j $j --seed 1234 --ref-audio refs/deep/m3-24k.wav --ref-text "$T1" -l English --text "$text" -o out/cq/qc-int8-j$j-$id.wav > out/cq/log-j$j-$id.txt 2>&1
    e=$(date +%s.%N); echo "{\"j\": $j, \"id\": \"$id\", \"wall\": $(echo "$e - $s" | bc)}" >> out/cq/wall.jsonl
    [ $j = 2 ] && break
  done
done
