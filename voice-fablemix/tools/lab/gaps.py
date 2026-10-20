"""Internal pauses (>= 80 ms below -40 dB of the clip's peak, 10 ms frames) per clip. Usage: gaps.py wav..."""
import sys, numpy as np, soundfile as sf
for f in sys.argv[1:]:
    y, sr = sf.read(f); hop = sr // 100; n = len(y) // hop
    e = np.sqrt(np.mean(y[: n * hop].reshape(n, hop) ** 2, 1)) + 1e-9
    v = 20 * np.log10(e / e.max()) > -40; idx = np.flatnonzero(v)
    gaps, run = [], 0
    for x in v[idx[0]: idx[-1] + 1]:
        if x:
            if run >= 8: gaps.append(run * 10)
            run = 0
        else:
            run += 1
    print(f.rsplit("/", 1)[-1], "lead", idx[0] * 10, "tail", (n - 1 - idx[-1]) * 10, "pauses", gaps)
