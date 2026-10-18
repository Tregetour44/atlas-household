#!/usr/bin/env python3
"""Exports one checkpoint to a quantised streaming TFLite model and records its
raw uint8 output stream on every evaluation set.

The device side is emulated as ESPHome's micro_wake_word does it: the
frontend's uint16 features are turned into int8 as
    int8 = clamp(round(raw * 256 / 666) - 128, -128, 127)
and the model is fed 3 new feature frames (30 ms) per inference. The
detector (sliding-window sum against the cutoff, refractory period) runs in
choose.py over these saved streams, so cutoffs and window sizes can be swept
without re-running the model.

  python -I evaluate.py --train-dir RUN --weights RUN/train/xxx_weights_9000.weights.h5 \
     --name s9000 --eval-dir EVAL --set val_pos=DIR ... --ambient val_ambient=MMAPDIR ...
"""

import argparse
import glob
import json
import os
import random
import time
from argparse import Namespace

import numpy as np
import yaml
from absl import logging
from mmap_ninja.ragged import RaggedMmap

logging.set_verbosity(logging.ERROR)

import tensorflow as tf  # noqa: E402
from ai_edge_litert.interpreter import Interpreter  # noqa: E402

import microwakeword.data as input_data  # noqa: E402
import microwakeword.mixednet as mixednet  # noqa: E402
import microwakeword.utils as utils  # noqa: E402
from microwakeword.layers import modes  # noqa: E402


def export(config, weights, out_dir, seed=1234):
    """Same conversion as model_train_eval.evaluate_model (streaming, quantised)."""
    flags = Namespace(**config["flags"])
    model = mixednet.model(flags, shape=config["training_input_shape"], batch_size=1)
    model.load_weights(weights)
    cfg = dict(config, train_dir=out_dir)
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
    utils.convert_model_saved(model, cfg, folder="stream_state_internal",
                              mode=modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)
    data_processor = input_data.FeatureHandler(cfg)
    random.seed(seed)
    np.random.seed(seed)
    utils.convert_saved_model_to_tflite(
        cfg, audio_processor=data_processor,
        path_to_model=os.path.join(out_dir, "stream_state_internal"),
        folder=out_dir, fname="model.tflite", quantize=True)
    return os.path.join(out_dir, "model.tflite")


class Streamer:
    def __init__(self, path):
        self.content = open(path, "rb").read()
        self._new()
        self.inp = self.interp.get_input_details()[0]
        self.out = self.interp.get_output_details()[0]
        assert self.inp["dtype"] == np.int8 and self.out["dtype"] == np.uint8
        self.stride = int(self.inp["shape"][1])
        self.state_inputs = self.interp.get_input_details()
        q = self.inp["quantization_parameters"]
        self.input_scale = float(q["scales"][0])
        self.input_zero_point = int(q["zero_points"][0])

    def _new(self):
        self.interp = Interpreter(model_content=self.content)
        self.interp.allocate_tensors()

    def reset(self):
        # A fresh interpreter: the streaming state variables start at zero.
        # (reset_all_variables() does not clear them.)
        self._new()

    def run(self, spec_u16):
        """spec_u16: (frames, 40) raw frontend values. Returns uint8 probabilities."""
        raw = spec_u16.astype(np.int64)
        q = np.clip((raw * 256 + 333) // 666 - 128, -128, 127).astype(np.int8)
        self.reset()
        n = (q.shape[0] // self.stride) * self.stride
        chunks = q[:n].reshape(-1, 1, self.stride, 40)
        out = np.empty(chunks.shape[0], dtype=np.uint8)
        set_t, invoke, get_t = self.interp.set_tensor, self.interp.invoke, self.interp.get_tensor
        i_idx, o_idx = self.inp["index"], self.out["index"]
        for k in range(chunks.shape[0]):
            set_t(i_idx, chunks[k])
            invoke()
            out[k] = get_t(o_idx)[0][0]
        return out


def as_u16(spec):
    if np.issubdtype(spec.dtype, np.uint16):
        return np.asarray(spec)
    return np.round(np.asarray(spec, dtype=np.float32) / 0.0390625).astype(np.uint16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-dir", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--eval-dir", required=True)
    ap.add_argument("--set", action="append", default=[],
                    help="name=GLOB of *_mmap dirs (one stream per clip)")
    ap.add_argument("--ambient", action="append", default=[],
                    help="name=GLOB of *_mmap dirs with long tracks")
    ap.add_argument("--tflite", default=None, help="skip export, use this model")
    args = ap.parse_args()

    config = yaml.load(open(os.path.join(args.train_dir, "training_config.yaml")), yaml.Loader)
    out_dir = os.path.join(args.eval_dir, args.name)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    path = args.tflite or export(config, args.weights, out_dir)
    t_export = time.time() - t0
    s = Streamer(path)
    info = {"weights": args.weights, "tflite": path, "input_scale": s.input_scale,
            "input_zero_point": s.input_zero_point, "stride": s.stride,
            "esphome_equivalent_scale": 666 / 256 * 0.0390625, "export_s": round(t_export, 1),
            "sets": {}}
    arrays = {}
    for spec in args.set + args.ambient:
        name, d = spec.split("=", 1)
        streams, frames = [], 0
        for m in sorted(glob.glob(d)):
            r = RaggedMmap(m)
            for i in range(len(r)):
                x = as_u16(r[i])
                frames += x.shape[0]
                streams.append(s.run(x))
        lengths = np.array([len(x) for x in streams], dtype=np.int64)
        arrays[name + "__probs"] = np.concatenate(streams) if streams else np.zeros(0, np.uint8)
        arrays[name + "__lengths"] = lengths
        info["sets"][name] = {"streams": len(streams), "frames": int(frames),
                              "hours": frames * 0.01 / 3600, "dir": d}
        print(f"{args.name} {name}: {len(streams)} streams, {frames * 0.01 / 3600:.2f} h", flush=True)
    np.savez_compressed(os.path.join(out_dir, "streams.npz"), **arrays)
    info["total_s"] = round(time.time() - t0, 1)
    json.dump(info, open(os.path.join(out_dir, "info.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in info.items() if k != "sets"}), flush=True)


if __name__ == "__main__":
    main()
