#!/usr/bin/env python3
"""Exports the trainer's TensorBoard scalars (train and in-loop validation)
to a long CSV: run,split,metric,step,value.

  python -I curves.py OUT.csv RUN_NAME=TRAIN_DIR [RUN_NAME=TRAIN_DIR ...]
"""
import csv
import glob
import os
import sys

import tensorflow as tf
from tensorflow.core.util import event_pb2

rows = []
for spec in sys.argv[2:]:
    run, train_dir = spec.split("=", 1)
    for split in ("train", "validation"):
        for path in sorted(glob.glob(os.path.join(train_dir, "logs", split, "events.*"))):
            for raw in tf.data.TFRecordDataset(path):
                ev = event_pb2.Event.FromString(raw.numpy())
                for v in ev.summary.value:
                    value = tf.make_ndarray(v.tensor).item() if v.HasField("tensor") else v.simple_value
                    rows.append({"run": run, "split": split, "metric": v.tag,
                                 "step": ev.step, "value": round(float(value), 6)})
rows.sort(key=lambda r: (r["run"], r["split"], r["metric"], r["step"]))
with open(sys.argv[1], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["run", "split", "metric", "step", "value"])
    w.writeheader()
    w.writerows(rows)
print(len(rows), "rows")
