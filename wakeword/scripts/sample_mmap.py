#!/usr/bin/env python3
"""Copies N evenly spaced entries of a Ragged MMap (a fixed, reproducible
sample), e.g. 2 h of CHiME-6 *training* chunks to measure false accepts on
the train split.  python -I sample_mmap.py SRC_MMAP OUT_MMAP N"""
import sys
import numpy as np
from mmap_ninja.ragged import RaggedMmap

src, out, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
r = RaggedMmap(src)
idx = np.linspace(0, len(r) - 1, n).astype(int)
RaggedMmap.from_generator(out_dir=out, sample_generator=(np.asarray(r[int(i)]) for i in idx),
                          batch_size=200, verbose=False)
print(out, n, "of", len(r))
