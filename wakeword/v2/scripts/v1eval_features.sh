#!/bin/sh
# v1's validation/test evaluation sets, regenerated: v1 augmentation assets
# (gen_aug_assets.py, v1 seeds 22/33, babble from that split's regenerated
# hard negatives) and v1's make_features.py --stream-eval, 4 shards.
# usage: v1eval_features.sh SYNTH_ROOT OUT_ROOT  (needs MWW_PY)
set -eu
SRC=$1; OUT=$2
V1=$(cd "$(dirname "$0")/../../scripts" && pwd)
"$MWW_PY" -I $V1/gen_aug_assets.py --out $OUT/aug --split validation --seed 22 $(for i in 0 1 2 3; do echo --babble-dir $SRC/neg_w$i/validation; done) &
"$MWW_PY" -I $V1/gen_aug_assets.py --out $OUT/aug --split test --seed 33 $(for i in 0 1 2 3; do echo --babble-dir $SRC/neg_w$i/test; done) &
wait
syn() { for d in "$@"; do printf -- "--synth %s " "$d"; done; }
for s in 0 1 2 3; do
  "$MWW_PY" -I $V1/make_features.py $(syn $SRC/pos_w0 $SRC/pos_w1 $SRC/pos_w2 $SRC/pos_w3) --aug $OUT/aug --out $OUT/se --kind positive --duration 5.6 --splits validation,test --stream-eval --shard $s/4 --seed 7 > $OUT/feat_pos_$s.log 2>&1 &
done; wait
for s in 0 1 2 3; do
  "$MWW_PY" -I $V1/make_features.py $(syn $SRC/neg_w0 $SRC/neg_w1 $SRC/neg_w2 $SRC/neg_w3) --aug $OUT/aug --out $OUT/se --kind negative --duration 5.6 --splits validation,test --stream-eval --shard $s/4 --seed 7 > $OUT/feat_neg_$s.log 2>&1 &
done; wait
for s in 0 1 2 3; do
  "$MWW_PY" -I $V1/make_features.py $(syn $SRC/probe_w0 $SRC/probe_w1 $SRC/probe_w2 $SRC/probe_w3) --aug $OUT/aug --out $OUT/se --kind negative --kind-name probe --duration 5.6 --splits test --stream-eval --shard $s/4 --seed 7 > $OUT/feat_probe_$s.log 2>&1 &
done
for s in 0 1; do
  "$MWW_PY" -I $V1/make_features.py $(syn $SRC/probeB_w0 $SRC/probeB_w1) --aug $OUT/aug --out $OUT/se --kind negative --kind-name probeB --duration 5.6 --splits test --stream-eval --shard $s/2 --seed 7 > $OUT/feat_probeB_$s.log 2>&1 &
done; wait
echo "v1 eval features done"
