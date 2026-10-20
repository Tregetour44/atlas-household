"""Pocket TTS built-in voice. Usage: pocket_run.py VOICE NAME lines.tsv outdir [threads] [language]"""
import sys, time, json, torch, soundfile as sf
from pocket_tts import TTSModel
voice, name, lf, outdir = sys.argv[1:5]
torch.set_num_threads(int(sys.argv[5]) if len(sys.argv) > 5 else 4)
lang = sys.argv[6] if len(sys.argv) > 6 else "english"
m = TTSModel.load_model(language=lang) if lang != "english" else TTSModel.load_model()
st = m.get_state_for_audio_prompt(voice)
for l in open(lf):
    lid, text = l.rstrip("\n").split("\t")
    torch.manual_seed(1234)
    t = time.time(); a = m.generate_audio(st, text); dt = time.time() - t
    y = a.numpy() if hasattr(a, "numpy") else a
    sf.write(f"{outdir}/{name}-{lid}.wav", y, m.sample_rate)
    print(json.dumps({"voice": name, "id": lid, "secs": round(dt, 2), "dur": round(len(y) / m.sample_rate, 2), "rtf": round(dt / (len(y) / m.sample_rate), 2)}), flush=True)
