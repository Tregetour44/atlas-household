import os, sys, torch, numpy as np
os.environ["COQUI_TOS_AGREED"] = "1"  # CPML: non-commercial use
from TTS.api import TTS
from common import run, LINES
torch.set_num_threads(4)
t = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
mode = sys.argv[1]
if mode == "screen":  # one short line per built-in male speaker, to shortlist British-sounding ones
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen"), exist_ok=True)
    for spk in sys.argv[2].split(","):
        torch.manual_seed(1)
        w = t.tts(LINES[3], speaker=spk, language="en")
        import soundfile as sf
        sf.write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen", f"xtts-{spk.replace(' ', '_')}-4.wav"), np.array(w), 24000)
        print("screened", spk, flush=True)
else:
    for spk in sys.argv[2].split(","):
        ref = sys.argv[3] if len(sys.argv) > 3 else None
        def synth(text):
            torch.manual_seed(1)
            if ref:
                w = t.tts(text, speaker_wav=ref, language="en", speed=0.95)
            else:
                w = t.tts(text, speaker=spk, language="en", speed=0.95)
            return np.array(w, dtype=np.float32), 24000
        run("xtts", spk.lower().replace(" ", "-"), synth, note=f"ref={ref}")
