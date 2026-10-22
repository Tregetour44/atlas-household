#!/usr/bin/env python3
"""Measures the TFLite Micro tensor arena a model needs, by bisection: the
smallest arena with which the TFLM interpreter allocates, and runs the
streaming model for 200 inferences with outputs identical to a large arena.
Runs in its own venv (tflite-micro wheels are built for CPython 3.13).

On this 64-bit host, TFLM's persistent structures hold 8-byte pointers; the
ESP32-S3 uses 4-byte ones, so the host figure is an upper bound.

  python -I arena.py MODEL.tflite [OUT.json]
"""
import json
import sys

import numpy as np
from tflite_micro.python.tflite_micro import runtime


def run(model, arena, steps=200, seed=0):
    try:
        it = runtime.Interpreter.from_bytes(model, arena_size=arena)
    except Exception:
        return None
    rng = np.random.default_rng(seed)
    d = it.get_input_details(0)
    outs = []
    try:
        for _ in range(steps):
            x = rng.integers(-128, 0, size=d["shape"], dtype=np.int8)
            it.set_input(x, 0)
            it.invoke()
            outs.append(int(it.get_output(0).flatten()[0]))
    except Exception:
        return None
    return outs


def main():
    model = open(sys.argv[1], "rb").read()
    reference = run(model, 1 << 20)
    assert reference is not None, "model does not run in TFLM even with a 1 MiB arena"
    lo, hi = 1024, 1 << 20
    while hi - lo > 16:
        mid = (lo + hi) // 2
        if run(model, mid) == reference:
            hi = mid
        else:
            lo = mid
    res = {"min_arena_bytes_host": hi, "model_bytes": len(model),
           "reference_outputs_first5": reference[:5]}
    print(json.dumps(res))
    if len(sys.argv) > 2:
        json.dump(res, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
