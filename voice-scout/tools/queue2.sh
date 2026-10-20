#!/bin/bash
# timing pass (nothing else running): each engine on L06 at 4 and 2 threads; Qwen C engine int8 ICL
cd /home/user/vs; T=out/timing; mkdir -p $T out/cq
T1="Good evening. The house is in order: battery at eighty percent, solar's done for the day, and the evening credit looks safe. I'd hold off on the dryer until eight, unless you're feeling reckless."
QB=$(ls -d ~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-0.6B-Base/snapshots/*/)
for j in 4 2; do
  for id in L06 L09 L03; do
    text=$(grep "^$id" tools/lines.tsv | cut -f2)
    /usr/bin/time -f "%e s %M KB" src-qwen3c/qwen_tts -d $QB --int8 -j $j --seed 1234 --ref-audio refs/deep/m3-24k.wav --ref-text "$T1" -l English --text "$text" -o out/cq/qc-int8-j$j-$id.wav > out/cq/log-j$j-$id.txt 2>&1
    [ $j = 2 ] && break
  done
done
source qwen/bin/activate
python -c "import json;json.dump({'t-qwen':json.load(open('tools/e_qwen.json'))['qwen06-fablemature']},open('tools/t_qwen.json','w'))"
for j in 4 2; do python tools/qwen_clone.py tools/t_qwen.json tools/l06w.tsv $T 1234 $j > $T/qwen-j$j.txt 2>&1; done
deactivate; source cbx/bin/activate
for j in 4 2; do python tools/cbnano_run.py tools/a_nano.json tools/l06w.tsv $T $j > $T/nano-j$j.txt 2>&1; done
deactivate; source kit/bin/activate
for j in 4 2; do python tools/kitten_run.py tools/a_kit.json tools/l06w.tsv $T $j > $T/kit-j$j.txt 2>&1; done
deactivate; source pkt/bin/activate
for j in 4 2; do python tools/pocket_run.py peter_yearsley pocket-peter tools/l06w.tsv $T $j > $T/pocket-j$j.txt 2>&1; done
deactivate; source kvw/bin/activate
for j in 4 2; do python tools/kokoro_run.py tools/a_kok.json tools/l06w.tsv $T $j > $T/kok-j$j.txt 2>&1; done
echo done > $T/queue2.done
