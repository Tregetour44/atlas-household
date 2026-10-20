"""Render the four sample lines with the teacher (Chatterbox 0.1.7, exaggeration 0.4, cfg_weight 0.4, defaults otherwise,
torch.manual_seed(7) before each line, as in voice-samples/tools/chatterbox_run.py) from each reference clip.
usage: fable_render.py <lines.txt> <out_dir> <ref.wav>..."""
import os, sys, time
import numpy as np, soundfile as sf, torch
from chatterbox.tts import ChatterboxTTS

lines_path, out = sys.argv[1:3]
refs = sys.argv[3:]
torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
lines = [l.strip() for l in open(lines_path, encoding="utf-8") if l.strip()]
os.makedirs(out, exist_ok=True)
m = ChatterboxTTS.from_pretrained(device="cpu")
for ref in refs:
    tag = os.path.basename(ref)[:-4]
    for i, text in enumerate(lines, 1):
        path = os.path.join(out, f"{tag}-{i}.wav")
        if os.path.exists(path):
            continue
        torch.manual_seed(7)
        t = time.perf_counter()
        w = m.generate(text, audio_prompt_path=ref, exaggeration=0.4, cfg_weight=0.4).squeeze().numpy()
        sf.write(path, np.clip(w, -1, 1), m.sr, subtype="PCM_16")
        print(f"{tag}-{i}: {len(w)/m.sr:.1f}s in {time.perf_counter()-t:.0f}s", flush=True)
