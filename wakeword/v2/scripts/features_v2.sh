#!/bin/sh
# v2 augmentation assets and features, then the synthetic WAVs of the train
# split are deleted (disk). usage: features_v2.sh DATA_ROOT (needs MWW_PY, V2_PY, MUSAN, NEG)
set -eu
D=$1; SY=$D/v2; FF=$D/ff; AUG=$D/aug; F=$D/feat; SE=$D/se2
HERE=$(cd "$(dirname "$0")" && pwd); V1=$(cd "$HERE/../../scripts" && pwd)
syn() { for x in "$@"; do printf -- "--synth %s " "$x"; done; }
negdirs() { for x in $SY/neg_*; do [ -d "$x/$1" ] && printf -- "%s/%s " "$x" "$1"; done; }
echo "assets $(date -u +%T)"
"$MWW_PY" -I $V1/gen_aug_assets.py --out $AUG --split train --seed 11 $(for x in $SY/neg_lib_w*; do echo --babble-dir $x/train; done) > $D/aug_train.log 2>&1 &
for p in 0 1 2; do
  "$V2_PY" -I $HERE/gen_farfield_assets.py --out $FF --split train --seed 111 --rooms 300 --musan $MUSAN --speech-clips $(negdirs train) --part $p/3 > $D/ff_train_$p.log 2>&1 &
done; wait
for sp in validation:222 test:333; do s=${sp%:*}; sd=${sp#*:}
  for p in 0 1; do
    "$V2_PY" -I $HERE/gen_farfield_assets.py --out $FF --split $s --seed $sd --rooms 60 --long-tv 12 --musan $MUSAN --speech-clips $(negdirs $s) --part $p/2 > $D/ff_${s}_$p.log 2>&1 &
  done
done; wait
echo "features $(date -u +%T)"
POS=$(ls -d $SY/pos_*); NEGS=$(ls -d $SY/neg_*); PROBES=$(ls -d $SY/probe_*)
for s in 0 1 2 3; do
  "$MWW_PY" -I $HERE/make_features_v2.py $(syn $POS) --aug $AUG --ff $FF --out $F/pos --kind positive --duration 4.0 --splits train,validation --shard $s/4 --seed 17 > $D/f_pos_$s.log 2>&1 &
done; wait
for s in 0 1 2 3; do
  "$MWW_PY" -I $HERE/make_features_v2.py $(syn $NEGS) --aug $AUG --ff $FF --out $F/neg --kind negative --duration 4.6 --splits train,validation --shard $s/4 --seed 27 > $D/f_neg_$s.log 2>&1 &
done; wait
for s in 0 1 2 3; do
  "$MWW_PY" -I $HERE/make_features_v2.py $(syn $POS) --ff $FF --out $SE --kind positive --kind-name ffpos --duration 5.6 --far-prob 1.0 --stream-eval --splits validation,test --shard $s/4 --seed 37 > $D/se_pos_$s.log 2>&1 &
done; wait
for s in 0 1 2 3; do
  "$MWW_PY" -I $HERE/make_features_v2.py $(syn $NEGS) --ff $FF --out $SE --kind negative --kind-name ffneg --duration 6.0 --far-prob 1.0 --stream-eval --splits validation,test --shard $s/4 --seed 47 > $D/se_neg_$s.log 2>&1 &
done
"$MWW_PY" -I $HERE/make_features_v2.py $(syn $PROBES) --ff $FF --out $SE --kind negative --kind-name weak --duration 5.6 --far-prob 1.0 --stream-eval --splits test --seed 57 > $D/se_weak.log 2>&1 &
wait
for s in 0 1; do
  "$MWW_PY" -I $HERE/make_features_v2.py --ff $FF --out $F/scene --kind scene --splits train,validation --shard $s/2 --seed 67 > $D/f_scene_$s.log 2>&1 &
done
"$MWW_PY" -I $HERE/make_features_v2.py --ff $FF --out $SE --kind scene --kind-name tv --scene-glob 'long_tv/*.wav' --splits validation,test --seed 77 > $D/se_tv.log 2>&1 &
wait
echo "done $(date -u +%T)"
