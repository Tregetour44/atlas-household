#!/usr/bin/env python3
"""Measures clip durations and the speech span inside each clip (energy VAD),
so the model window can be set to cover the slowest utterances.
  python -I durations.py OUT.csv SYNTH_DIR [SYNTH_DIR ...]"""
import csv, os, sys, wave
import numpy as np

rows = []
for d in sys.argv[2:]:
    for r in csv.DictReader(open(os.path.join(d, "meta.csv"), encoding="utf-8")):
        with wave.open(os.path.join(d, r["file"])) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)
        frame = 160
        n = len(x) // frame
        e = 10 * np.log10(np.mean(x[: n * frame].reshape(n, frame) ** 2, axis=1) + 1e-9)
        active = np.where(e > e.max() - 40)[0]
        span = (active[-1] - active[0] + 1) * frame / 16000 if len(active) else 0
        rows.append({"file": r["file"], "split": r["split"], "template_id": r["template_id"],
                     "length_scale": r["length_scale"], "duration_s": round(len(x) / 16000, 3),
                     "speech_span_s": round(span, 3)})
with open(sys.argv[1], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
d = np.array([r["duration_s"] for r in rows]); s = np.array([r["speech_span_s"] for r in rows])
for name, v in (("duration_s", d), ("speech_span_s", s)):
    print(name, "n=%d min=%.3f p50=%.3f p95=%.3f p99=%.3f p99.9=%.3f max=%.3f" % (
        len(v), v.min(), *np.percentile(v, [50, 95, 99, 99.9]), v.max()))
