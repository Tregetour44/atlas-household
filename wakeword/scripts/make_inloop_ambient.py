#!/usr/bin/env python3
"""Builds the trainer's in-loop ambient validation set: the first third of
each CHiME-6 dev/eval track of dinner_party_eval/validation_ambient (~3.2 h).
The full 9.7 h set does not fit in this machine's memory inside the trainer
(it holds every 0.3 s window as float32, then Keras copies it). Model and
threshold selection still uses the full 9.7 h, streamed, in evaluate.py.
DiPCo (testing_ambient) is linked unchanged.

  python -I make_inloop_ambient.py NEG_ROOT OUT_DIR
"""
import os, sys
from mmap_ninja.ragged import RaggedMmap

neg_root, out = sys.argv[1], sys.argv[2]
src = RaggedMmap(os.path.join(neg_root, "dinner_party_eval/validation_ambient/chime6_dev_eval_mmap"))
os.makedirs(os.path.join(out, "validation_ambient"), exist_ok=True)
RaggedMmap.from_generator(
    out_dir=os.path.join(out, "validation_ambient", "chime6_dev_eval_first_third_mmap"),
    sample_generator=(src[i][: src[i].shape[0] // 3] for i in range(len(src))),
    batch_size=1, verbose=False)
os.symlink(os.path.abspath(os.path.join(neg_root, "dinner_party_eval/testing_ambient")),
           os.path.join(out, "testing_ambient"))
print("ok", [src[i].shape[0] // 3 for i in range(len(src))])
