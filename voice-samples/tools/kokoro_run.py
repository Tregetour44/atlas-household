import misaki.espeak
from phonemizer.backend.espeak.wrapper import EspeakWrapper
EspeakWrapper.set_library("/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1")
EspeakWrapper.set_data_path("/usr/lib/x86_64-linux-gnu/espeak-ng-data")
import numpy as np, torch
from kokoro import KPipeline
from common import run
torch.set_num_threads(4)
pipe = KPipeline(lang_code="b")  # British English
pipe("Warm up.", voice="bm_george")
def make(v, speed):
    def synth(text):
        chunks = [a.numpy() if hasattr(a, "numpy") else a for _, _, a in pipe(text, voice=v, speed=speed)]
        return np.concatenate(chunks), 24000
    return synth
for v in ["bm_george", "bm_lewis", "bm_daniel", "bm_fable"]:
    run("kokoro", v, make(v, 0.92))
