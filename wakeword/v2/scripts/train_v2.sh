#!/bin/sh
# Trains, then converts the best weights to a quantised streaming TFLite model
# and runs the trainer's own streaming test. Model flags are the notebook's.
# usage: train.sh CONFIG.yaml [TRAIN(1|0)]
set -eu
CFG=$1; TRAIN=${2:-1}
: "${MWW_PY:?set MWW_PY to the trainer venv python}"
"$MWW_PY" -m microwakeword.model_train_eval \
  --training_config="$CFG" \
  --train "$TRAIN" \
  --restore_checkpoint 1 \
  --test_tf_nonstreaming 0 \
  --test_tflite_nonstreaming 0 \
  --test_tflite_nonstreaming_quantized 0 \
  --test_tflite_streaming 0 \
  --test_tflite_streaming_quantized 0 \
  --use_weights "best_weights" \
  mixednet \
  --pointwise_filters "64,64,64,64" \
  --repeat_in_block "1, 1, 1, 1" \
  --mixconv_kernel_sizes '[5], [7,11], [9,15], [23]' \
  --residual_connection "0,0,0,0" \
  --first_conv_filters 32 \
  --first_conv_kernel_size 5 \
  --stride 3
