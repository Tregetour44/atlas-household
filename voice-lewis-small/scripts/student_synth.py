"""Render manifest lines with a Piper ONNX voice and time it (per-clip RTF, p50/p95, peak RSS).
usage: student_synth.py <model.onnx> <manifest.tsv> <splits> <out_dir> <stats.jsonl> [tag] [length_scale]"""
import csv, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import run
from piper import PiperVoice, SynthesisConfig

onnx, manifest, splits, out, stats = sys.argv[1:6]
tag = sys.argv[6] if len(sys.argv) > 6 else "student"
ls = float(sys.argv[7]) if len(sys.argv) > 7 else None
rows = [r for r in csv.DictReader(open(manifest, encoding="utf-8"), delimiter="\t") if r["split"] in splits.split(",")]
v = PiperVoice.load(onnx)
cfg = SynthesisConfig(length_scale=ls) if ls else None

def synth(text):
    chunks = [c.audio_float_array for c in v.synthesize(text, syn_config=cfg)]
    return np.concatenate(chunks), v.config.sample_rate

run(tag, synth, [r["text"] for r in rows], out, stats, names=[r["id"] for r in rows])
