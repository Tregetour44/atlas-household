#!/bin/bash
cd /home/user/vs; L=tools/lines.tsv; A=out/aud; mkdir -p $A out/qc4
source qwen/bin/activate
python tools/qwen_clone.py tools/qc4a.json tools/reftext.tsv out/qc4 7 > out/qc4/log.txt 2>&1
python tools/qwen_clone.py tools/a_qwen.json $L $A > $A/log-qwen.txt 2>&1
deactivate; source cbx/bin/activate
python tools/cbnano_run.py tools/a_nano.json $L $A > $A/log-nano.txt 2>&1
deactivate; source kit/bin/activate
python tools/kitten_run.py tools/a_kit.json $L $A > $A/log-kit.txt 2>&1
deactivate; source pkt/bin/activate
python tools/pocket_run.py peter_yearsley pocket-peter $L $A > $A/log-pocket.txt 2>&1
deactivate; source kvw/bin/activate
python tools/kokoro_enroll.py out/qc4/ev-m3-REF.wav out/qc4/inno-m3.pt > out/qc4/log-inno.txt 2>&1
python tools/kokoro_enroll.py refs/chatterbox-kokoro-fable-ref-1.mp3 out/qc4/inno-cbfable.pt >> out/qc4/log-inno.txt 2>&1
echo done > $A/queue1.done
