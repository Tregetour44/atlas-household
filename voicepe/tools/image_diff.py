#!/usr/bin/env python3
"""Lists every byte range in which two application images differ, with context.
  python -I tools/image_diff.py OLD.bin NEW.bin"""
import sys

a, b = (open(p, "rb").read() for p in sys.argv[1:3])
assert len(a) == len(b), (len(a), len(b))
d = [i for i in range(len(a)) if a[i] != b[i]]
runs, s, p = [], d[0], d[0]
for i in d[1:]:
    if i != p + 1:
        runs.append((s, p))
        s = i
    p = i
runs.append((s, p))
print(f"{len(a)} bytes each; {len(d)} bytes differ in {len(runs)} ranges")
for s, e in runs:
    lo, hi = max(0, s - 16), e + 17
    print(f"0x{s:06x} +{e - s + 1}: {a[s:e + 1].hex()} -> {b[s:e + 1].hex()}")
    print(f"    context old {a[lo:hi]!r}")
    print(f"    context new {b[lo:hi]!r}")
