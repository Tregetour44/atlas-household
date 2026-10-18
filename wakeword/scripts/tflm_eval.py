#!/usr/bin/env python3
"""Re-runs the final model's evaluation streams on TFLite Micro (ESPHome's
runtime) instead of LiteRT, writing streams.npz in evaluate.py's format so
report.py can score it. Same int8 feature conversion as evaluate.py.

  python -I tflm_eval.py MODEL.tflite LITERT_EVAL_DIR/NAME OUT_DIR
(reads the set list from the LiteRT run's info.json)
"""
import glob
import json
import os
import sys

import numpy as np
from mmap_ninja.ragged import RaggedMmap
from tflite_micro.python.tflite_micro import runtime

model, src, out = sys.argv[1:4]
info = json.load(open(os.path.join(src, "info.json")))
os.makedirs(out, exist_ok=True)
arrays = {}
for name, si in info["sets"].items():
    streams = []
    for m in sorted(glob.glob(si["dir"])):
        r = RaggedMmap(m)
        for i in range(len(r)):
            raw = np.asarray(r[i]).astype(np.int64)
            q = np.clip((raw * 256 + 333) // 666 - 128, -128, 127).astype(np.int8)
            it = runtime.Interpreter.from_file(model, arena_size=1 << 20)
            n = q.shape[0] // 3
            o = np.empty(n, np.uint8)
            for c in range(n):
                it.set_input(q[c * 3:(c + 1) * 3].reshape(1, 3, 40), 0)
                it.invoke()
                o[c] = it.get_output(0).flatten()[0]
            streams.append(o)
    arrays[name + "__probs"] = np.concatenate(streams)
    arrays[name + "__lengths"] = np.array([len(s) for s in streams], np.int64)
    print(name, len(streams), flush=True)
np.savez_compressed(os.path.join(out, "streams.npz"), **arrays)
json.dump(dict(info, runtime="tflite-micro"), open(os.path.join(out, "info.json"), "w"), indent=1)
