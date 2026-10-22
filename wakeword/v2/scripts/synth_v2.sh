#!/bin/sh
# v2 synthesis: every job below, 4 at a time. Seeds are fixed per job.
# usage: synth_v2.sh DATA_ROOT  (needs PSG_ROOT, PSG_MODEL, PSG_PY, V2_PY, PLANS)
set -eu
D=$1
HERE=$(cd "$(dirname "$0")" && pwd)
POSW="au=2,au2=3,nz=1.5,casual=1.5,gb=1.5,gb2=1.5,us=1,other=0.5"
NEGW="mid_atlas=4,hi_atlas=1.5,pay_atlas=1,hey_alice=1,hey_alex=1,at_last=1.5,atlas=1,ask_atlas=0.5,rocket=0.3,hey_name=1,okay_nabu=0.3,hey=0.8,other=0.5,z_rhyme=1"
WEAK="hi Atlas|pay Atlas|hey Alice|hey Alex|at last"
mkdir -p "$D"
jobs=$D/jobs.txt; : > "$jobs"
psg() { # name kind counts seed weights
  echo "SYNTH_THREADS=1 PSG_ROOT=$PSG_ROOT $PSG_PY -I $HERE/synth_psg.py --kind $2 --n 0 --counts $3 --out $D/$1 --model $PSG_MODEL --seed $4 --template-set v2 --family-weights $5 --batch-size 16 > $D/$1.log 2>&1" >> "$jobs"; }
onnx() { # name plan kind counts seed weights|-  [probe texts]
  w=""; [ "$6" = - ] || w="--family-weights $6"
  p=""; [ -z "${7:-}" ] || p="--probe-texts '$7'"
  echo "SYNTH_THREADS=1 $V2_PY -I $HERE/synth_onnx.py --plan $PLANS/$2.json --kind $3 --counts $4 --out $D/$1 --seed $5 $w $p > $D/$1.log 2>&1" >> "$jobs"; }
# Kokoro is the slowest: start it first
for i in 0 1 2 3; do onnx pos_kokoro_w$i kokoro positive 1000,100,100 $((3100+i)) $POSW; done
for i in 0 1 2 3; do onnx neg_kokoro_w$i kokoro negative 375,50,50 $((3200+i)) $NEGW; done
onnx probe_kokoro kokoro negative 0,0,160 3300 - "$WEAK"
for i in 0 1 2 3; do psg pos_lib_w$i positive 5000,100,100 $((2100+i)) $POSW; done
for i in 0 1 2 3; do psg neg_lib_w$i negative 3500,250,250 $((2200+i)) $NEGW; done
for i in 0 1 2 3; do onnx pos_vctk_w$i vctk positive 2250,125,125 $((3400+i)) $POSW; done
for i in 0 1 2 3; do onnx neg_vctk_w$i vctk negative 1000,75,75 $((3500+i)) $NEGW; done
onnx probe_vctk vctk negative 0,0,240 3600 - "$WEAK"
for i in 0 1; do onnx pos_aru_w$i aru positive 1500,125,125 $((3700+i)) $POSW; done
for i in 0 1; do onnx neg_aru_w$i aru negative 500,50,50 $((3800+i)) $NEGW; done
onnx probe_aru aru negative 0,0,160 3900 - "$WEAK"
onnx pos_alba alba positive 1000,0,0 4000 $POSW
onnx pos_nem nem positive 1000,0,0 4001 $POSW
onnx pos_cori cori positive 0,300,0 4002 $POSW
onnx pos_sef sef positive 0,0,300 4003 $POSW
onnx neg_alba alba negative 500,0,0 4100 $NEGW
onnx neg_nem nem negative 500,0,0 4101 $NEGW
onnx neg_cori cori negative 0,150,0 4102 $NEGW
onnx neg_sef sef negative 0,0,150 4103 $NEGW
xargs -P 4 -I{} sh -c '{}' < "$jobs"
echo "synth v2 done"
