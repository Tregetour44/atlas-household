#!/usr/bin/env python3
"""Checks that TFLite Micro (the runtime ESPHome uses) gives the same uint8
outputs as the LiteRT interpreter used for evaluation, on real streams.
Step 1 (trainer venv):  python -I check_tflm_equivalence.py dump MODEL MMAP_GLOB... OUT.npz
Step 2 (TFLM venv):     python -I check_tflm_equivalence.py tflm MODEL OUT.npz
"""
import glob
import sys

import numpy as np

if sys.argv[1] == "dump":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from evaluate import Streamer
    from mmap_ninja.ragged import RaggedMmap
    model, globs, out = sys.argv[2], sys.argv[3:-1], sys.argv[-1]
    s = Streamer(model)
    arrays = {}
    k = 0
    for g in globs:
        for m in sorted(glob.glob(g)):
            r = RaggedMmap(m)
            for i in range(min(3, len(r))):
                x = np.asarray(r[i])[:3000].astype(np.int64)
                q = np.clip((x * 256 + 333) // 666 - 128, -128, 127).astype(np.int8)
                arrays[f"in{k}"] = q
                arrays[f"out{k}"] = s.run(np.asarray(r[i])[:3000])
                k += 1
    np.savez(out, **arrays)
    print(k, "streams dumped")
else:
    from tflite_micro.python.tflite_micro import runtime
    model, path = sys.argv[2], sys.argv[3]
    d = np.load(path)
    n = len([k for k in d.files if k.startswith("in")])
    total = same = maxdiff = 0
    for k in range(n):
        it = runtime.Interpreter.from_file(model, arena_size=1 << 20)
        q, ref = d[f"in{k}"], d[f"out{k}"]
        outs = []
        for c in range(len(ref)):
            it.set_input(q[c * 3:(c + 1) * 3].reshape(1, 3, 40), 0)
            it.invoke()
            outs.append(int(it.get_output(0).flatten()[0]))
        outs = np.array(outs)
        total += len(ref)
        same += int((outs == ref).sum())
        maxdiff = max(maxdiff, int(np.abs(outs.astype(int) - ref.astype(int)).max()))
    print(f"{n} streams, {total} inferences: identical {same}/{total}, max |diff| {maxdiff} (uint8)")
