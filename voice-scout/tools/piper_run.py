"""Piper voice on the audition lines. Usage: piper_run.py model.onnx NAME lines.tsv outdir"""
import sys, time, json, wave, numpy as np, soundfile as sf
from piper import PiperVoice
v = PiperVoice.load(sys.argv[1]); name, lf, outdir = sys.argv[2:5]
for l in open(lf):
    lid, text = l.rstrip("\n").split("\t")
    t = time.time(); y = np.concatenate([c.audio_float_array for c in v.synthesize(text)]); dt = time.time() - t
    sf.write(f"{outdir}/{name}-{lid}.wav", y, v.config.sample_rate)
    print(json.dumps({"voice": name, "id": lid, "secs": round(dt, 3), "dur": round(len(y) / v.config.sample_rate, 2), "rtf": round(dt / (len(y) / v.config.sample_rate), 3)}), flush=True)
