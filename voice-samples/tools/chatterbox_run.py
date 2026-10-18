import sys, torch
from chatterbox.tts import ChatterboxTTS
from common import run, S
import os
torch.set_num_threads(4)
m = ChatterboxTTS.from_pretrained(device="cpu")
# name: (exaggeration, cfg_weight, reference wav or None for the built-in voice)
VARIANTS = {
    "default": (0.5, 0.5, None),
    "calm": (0.3, 0.3, None),            # less exaggeration + lower cfg = slower, calmer
    "expressive": (0.75, 0.3, None),
}
for name in sys.argv[1].split(","):
    # "kokoro-<voice>-ref": built-in Chatterbox model conditioned on a 10 s synthetic Kokoro clip (no human reference)
    ex, cfg, ref = VARIANTS[name] if name in VARIANTS else (0.4, 0.4, os.path.join(S, "refs", name.replace("-ref", "").replace("kokoro-", "kokoro-bm_") + ".wav"))
    def synth(text):
        torch.manual_seed(7)
        w = m.generate(text, audio_prompt_path=ref, exaggeration=ex, cfg_weight=cfg)
        return w.squeeze().numpy(), m.sr
    run("chatterbox", name, synth, note=f"exaggeration={ex} cfg_weight={cfg} ref={ref}")
