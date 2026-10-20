"""Qwen3-TTS Base clone with optional speaker-embedding (x-vector) mixing.
cfg JSON: {voice: {"model": "0.6B"|"1.7B", "ref": wav, "ref_text": str, "xvec": [[wav, weight], ...] (optional),
"xvec_only": bool, "temperature": float (optional)}}. Usage: qwen_clone.py cfg.json lines.tsv outdir [seed] [threads]"""
import sys, time, json, torch, numpy as np, soundfile as sf, librosa
from qwen_tts import Qwen3TTSModel
cfg = json.load(open(sys.argv[1])); lines = [l.rstrip('\n').split('\t') for l in open(sys.argv[2])]; outdir = sys.argv[3]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1234
torch.set_num_threads(int(sys.argv[5]) if len(sys.argv) > 5 else 4)
models = {}
def load(sz):
    if sz not in models:
        models[sz] = Qwen3TTSModel.from_pretrained(f"Qwen/Qwen3-TTS-12Hz-{sz}-Base", device_map="cpu", dtype=torch.float32)
    return models[sz]
def wav(p):
    y, sr = librosa.load(p, sr=24000, mono=True); return (y, sr)
for name, c in cfg.items():
    m = load(c.get("model", "0.6B"))
    item = m.create_voice_clone_prompt(ref_audio=wav(c["ref"]), ref_text=c.get("ref_text"), x_vector_only_mode=c.get("xvec_only", False))[0]
    if c.get("xvec"):
        embs = []
        for p, w in c["xvec"]:
            e = m.create_voice_clone_prompt(ref_audio=wav(p), x_vector_only_mode=True)[0].ref_spk_embedding
            embs.append(w * e)
        mix = sum(embs)
        item.ref_spk_embedding = mix * (item.ref_spk_embedding.norm() / mix.norm()) if c.get("renorm", True) else mix
    gen = {k: c[k] for k in ("temperature", "top_p", "top_k") if k in c}
    for lid, text in lines:
        torch.manual_seed(seed)
        t = time.time(); wavs, sr = m.generate_voice_clone(text=text, language="English", voice_clone_prompt=[item], **gen); dt = time.time() - t
        sf.write(f"{outdir}/{name}-{lid}.wav", wavs[0], sr)
        print(json.dumps({"voice": name, "id": lid, "secs": round(dt, 2), "dur": round(len(wavs[0]) / sr, 2), "rtf": round(dt / (len(wavs[0]) / sr), 2)}), flush=True)
