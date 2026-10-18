import os, numpy as np
from piper import PiperVoice, SynthesisConfig
from common import run, S
M = os.path.join(S, "models/piper")
for name, onnx, spk in [("alan", "en_GB-alan-medium", None),
                        ("northern-english-male", "en_GB-northern_english_male-medium", None),
                        ("semaine-obadiah", "en_GB-semaine-medium", 2),
                        ("semaine-spike", "en_GB-semaine-medium", 1)]:
    v = PiperVoice.load(os.path.join(M, onnx + ".onnx"))
    cfg = SynthesisConfig(speaker_id=spk, length_scale=1.1)
    def synth(text):
        chunks = [c.audio_float_array for c in v.synthesize(text, syn_config=cfg)]
        return np.concatenate(chunks), v.config.sample_rate
    run("piper", name, synth)
