#!/usr/bin/env python3
"""Checks the frame step of published negative features against the trainer's
10 ms frontend.

Test: the syllable-rate peak of speech. Speech energy is modulated at about
3-6 Hz. Read at an assumed 10 ms step, 10 ms features show that peak there;
20 ms features read as 10 ms would show it near half the rate. References are
synthetic speech streams (this project's own TTS clips joined into 5 s
streams), featurised with the same frontend at 10 ms and at 20 ms.

  python -I check_feature_step.py --ref-wavs DIR --mmap PATH [--mmap PATH ...] --out x.json
"""
import argparse, glob, json, wave
import numpy as np
import tensorflow as tf
from mmap_ninja.ragged import RaggedMmap
from scipy.signal import welch
from tensorflow.lite.experimental.microfrontend.python.ops import audio_microfrontend_op as fe
from microwakeword.audio.audio_utils import generate_features_for_clip


def modulation_peak(spec, assumed_step_s=0.01):
    """Share of envelope modulation power in 8-25 Hz relative to 1-25 Hz,
    reading frames at assumed_step_s. Speech has little modulation above
    ~8 Hz; features read at twice their real step put twice the rate there."""
    e = spec.astype(np.float64).mean(axis=1)
    e = e - e.mean()
    f, p = welch(e, fs=1 / assumed_step_s, nperseg=min(128, len(e)))
    hi = p[(f >= 8) & (f <= 25)].sum()
    tot = p[(f >= 1) & (f <= 25)].sum() + 1e-12
    return float(hi / tot)


def tf_features(audio_i16, step):
    with tf.device("/cpu:0"):
        return fe.audio_microfrontend(tf.convert_to_tensor(audio_i16), sample_rate=16000, window_size=30,
                                      window_step=step, num_channels=40, upper_band_limit=7500,
                                      lower_band_limit=125, enable_pcan=True, min_signal_remaining=0.05,
                                      out_scale=1, out_type=tf.uint16).numpy()


ap = argparse.ArgumentParser()
ap.add_argument("--ref-wavs", action="append", required=True)
ap.add_argument("--mmap", action="append", required=True)
ap.add_argument("--out")
a = ap.parse_args()
rng = np.random.default_rng(0)
clips = []
for d in a.ref_wavs:
    for p in sorted(glob.glob(d + "/*.wav"))[:300]:
        with wave.open(p) as w:
            clips.append(np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16))
refs = {"tf_10ms": [], "pymicro_10ms": [], "tf_20ms": []}
for _ in range(60):
    stream = []
    while sum(len(c) for c in stream) < 80000:
        stream.append(clips[rng.integers(len(clips))])
        stream.append(np.zeros(rng.integers(800, 4000), dtype=np.int16))
    s = np.concatenate(stream)[:80000]
    s = np.clip(s + rng.normal(0, 30, len(s)), -32768, 32767).astype(np.int16)
    refs["tf_10ms"].append(modulation_peak(tf_features(s, 10)))
    refs["pymicro_10ms"].append(modulation_peak(generate_features_for_clip(s, 10)))
    refs["tf_20ms"].append(modulation_peak(tf_features(s, 20)))  # read as if 10 ms
result = {"reference (8-25 Hz power share, read as 10 ms)": {k: [round(float(np.mean(v)), 2), round(float(np.std(v)), 2)]
                                           for k, v in refs.items()}}
for m in a.mmap:
    r = RaggedMmap(m)
    idx = rng.choice(len(r), size=min(300, len(r)), replace=False)
    vals = []
    for i in idx:
        s = r[int(i)]
        if s.shape[0] > 6000:  # long ambient tracks: sample several 5 s chunks
            for _ in range(30):
                o = rng.integers(0, s.shape[0] - 500)
                vals.append(modulation_peak(s[o:o + 500]))
        else:
            vals.append(modulation_peak(s))
    result[m] = [round(float(np.mean(vals)), 2), round(float(np.std(vals)), 2)]
print(json.dumps(result, indent=1))
if a.out:
    json.dump(result, open(a.out, "w"), indent=1)
