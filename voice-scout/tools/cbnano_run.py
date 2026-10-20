"""Chatterbox-Nano (or Turbo) clone. cfg JSON: {voice: {"ref": wav, "nano": true, "temperature": 0.8,
"emb_mix": [[wav, w], ...] (optional: mixes the S3Gen speaker x-vector only)}}. Usage: cbnano_run.py cfg.json lines.tsv outdir [threads]"""
import sys, time, json, torch, soundfile as sf
from chatterbox.tts_turbo import ChatterboxTurboTTS
cfg = json.load(open(sys.argv[1])); lines = [l.rstrip('\n').split('\t') for l in open(sys.argv[2])]; outdir = sys.argv[3]
torch.set_num_threads(int(sys.argv[4]) if len(sys.argv) > 4 else 4)
models = {}
for name, c in cfg.items():
    nano = c.get("nano", True)
    if nano not in models: models[nano] = ChatterboxTurboTTS.from_pretrained(device="cpu", nano=nano)
    m = models[nano]
    if c.get("emb_mix"):
        embs = []
        for p, w in c["emb_mix"]:
            m.prepare_conditionals(p); embs.append(w * m.conds.gen["embedding"].clone())
    m.prepare_conditionals(c["ref"])
    if c.get("emb_mix"):
        e = sum(embs); m.conds.gen["embedding"] = e * (m.conds.gen["embedding"].norm() / e.norm())
    for lid, text in lines:
        torch.manual_seed(1234)
        t = time.time(); w = m.generate(text, temperature=c.get("temperature", 0.8), top_p=c.get("top_p", 0.95)); dt = time.time() - t
        y = w.squeeze(0).numpy(); sf.write(f"{outdir}/{name}-{lid}.wav", y, m.sr)
        print(json.dumps({"voice": name, "id": lid, "secs": round(dt, 2), "dur": round(len(y) / m.sr, 2), "rtf": round(dt / (len(y) / m.sr), 2)}), flush=True)
