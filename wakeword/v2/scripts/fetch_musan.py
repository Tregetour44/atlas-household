#!/usr/bin/env python3
"""Streams MUSAN (OpenSLR 17, CC BY 4.0) and keeps a bounded subset, so the
11 GB archive never lands on disk: every text file (README, LICENSE,
ANNOTATIONS: per-file sources and licences), and WAVs per category up to a
cap in hours, taking every k-th file so the subset spans the whole set.

  python -I fetch_musan.py OUT_DIR
"""
import hashlib
import os
import sys
import tarfile
import urllib.request

URL = "https://www.openslr.org/resources/17/musan.tar.gz"
# category prefix -> (hours cap, keep every k-th wav)
CAPS = {"musan/speech/us-gov/": (4.0, 2), "musan/speech/librivox/": (1.0, 6),
        "musan/music/": (6.0, 3), "musan/noise/": (3.0, 2)}

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
seen = {k: 0 for k in CAPS}
hours = {k: 0.0 for k in CAPS}
h = hashlib.sha256()


class Hashing:
    def __init__(self, f):
        self.f = f

    def read(self, n=-1):
        b = self.f.read(n)
        h.update(b)
        return b


resp = urllib.request.urlopen(URL, timeout=120)
with tarfile.open(fileobj=Hashing(resp), mode="r|gz") as tar:
    for m in tar:
        if not m.isfile():
            continue
        name = m.name
        keep = False
        if not name.endswith(".wav"):
            keep = True
        else:
            for k, (cap, every) in CAPS.items():
                if name.startswith(k):
                    seen[k] += 1
                    dur = (m.size - 44) / 32000 / 3600
                    if seen[k] % every == 0 and hours[k] + dur <= cap:
                        keep = True
                        hours[k] += dur
                    break
        if keep:
            dst = os.path.join(out, name)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(tar.extractfile(m).read())
# drain the rest of the stream so the archive hash is complete
while resp.read(1 << 20):
    pass
print("archive sha256", h.hexdigest())
for k in CAPS:
    print(k, "seen", seen[k], "kept hours", round(hours[k], 2))
