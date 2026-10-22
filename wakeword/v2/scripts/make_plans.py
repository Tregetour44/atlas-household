#!/usr/bin/env python3
"""Writes the v2 voice plans (which voices each engine uses in each split).

Splits are by voice, decided here once (seed 20261022):
  * VCTK (Piper en_GB-vctk-medium, 109 speakers): the two Australian speakers
    are split p374 -> train, p326 -> test; the one New Zealand speaker p335 ->
    train. The rest are split 80/10/10 within each accent. Australian, New
    Zealand and British voices are listed more than once, so they are drawn
    (and mixed) more often.
  * ARU (Piper en_GB-aru-medium, 12 UK speakers): 10 / 1 / 1.
  * Kokoro-82M: 28 English voices; 4 held out for validation and 4 for test.
  * Single-voice Piper GB models: alba and northern_english_male -> train,
    cori -> validation, southern_english_female -> test.

  python -I make_plans.py TTS_DIR VCTK_SPEAKERS_JSON OUT_DIR
"""
import json
import os
import sys

import numpy as np

tts, spk_json, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
rng = np.random.default_rng(20261022)
acc = json.load(open(spk_json))
ids = sorted(json.load(open(os.path.join(tts, "en_GB-vctk-medium.onnx.json")))["speaker_id_map"])
vctk = {"train": [], "validation": [], "test": []}
fixed = {"p374": "train", "p335": "train", "p326": "test"}
weight = {"Australian": 8, "NewZealand": 6, "English": 2, "Scottish": 2, "Irish": 2, "Welsh": 2,
          "NorthernIrish": 2, "British": 2}
for s, sp in fixed.items():
    vctk[sp] += [s] * weight[acc[s][0]]
by_acc = {}
for s in ids:
    if s not in fixed:
        by_acc.setdefault(acc[s][0], []).append(s)
for a, ss in sorted(by_acc.items()):
    ss = [ss[i] for i in rng.permutation(len(ss))]
    n = len(ss)
    nv = int(round(0.1 * n)) if n >= 5 else 0
    nt = int(round(0.1 * n)) if n >= 5 else (1 if n >= 3 else 0)
    for i, s in enumerate(ss):
        sp = "validation" if i < nv else "test" if i < nv + nt else "train"
        vctk[sp] += [s] * weight.get(a, 1)
plans = {
    "vctk": {"engine": "piper", "model": f"{tts}/en_GB-vctk-medium.onnx", "mix_prob": 0.6,
             "length_scale_base": 1.0, "voices": vctk},
    "aru": {"engine": "piper", "model": f"{tts}/en_GB-aru-medium.onnx", "mix_prob": 0.6,
            "voices": {"train": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"],
                       "validation": ["11"], "test": ["12"]}},
    "kokoro": {"engine": "kokoro", "model": f"{tts}/kokoro-v1.0.onnx", "mix_prob": 0.6,
               "voices": {
                   "train": ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore",
                             "af_nicole", "af_river", "af_sarah", "am_adam", "am_eric", "am_fenrir",
                             "am_liam", "am_michael", "am_puck", "am_santa"]
                            + ["bf_alice", "bf_emma", "bm_fable", "bm_lewis"] * 2,
                   "validation": ["af_sky", "am_echo", "bf_isabella", "bm_george"],
                   "test": ["af_nova", "am_onyx", "bf_lily", "bm_daniel"]}},
    "alba": {"engine": "piper", "model": f"{tts}/en_GB-alba-medium.onnx", "voices": {"train": ["alba"]}},
    "nem": {"engine": "piper", "model": f"{tts}/en_GB-northern_english_male-medium.onnx",
            "voices": {"train": ["nem"]}},
    "cori": {"engine": "piper", "model": f"{tts}/en_GB-cori-high.onnx", "voices": {"validation": ["cori"]}},
    "sef": {"engine": "piper", "model": f"{tts}/en_GB-southern_english_female-low.onnx",
            "voices": {"test": ["sef"]}},
}
for name, p in plans.items():
    p["name"] = name
    json.dump(p, open(os.path.join(out, f"{name}.json"), "w"), indent=1)
summary = {s: sorted({(v, acc[v][0]) for v in vctk[s]}) for s in vctk}
print(json.dumps({s: [f"{v}:{a}" for v, a in x] for s, x in summary.items()}))
