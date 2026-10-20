"""Kokoro-82M with a voice built from a spec. cfg JSON: {voice: {"dec": [[src, w], ...], "pred": [[src, w], ...], "speed": 1.0}}
src = stock voice name (bm_fable) or a .pt path. "dec" mixes the decoder (timbre) half of the style vector, "pred" the
predictor (prosody/duration) half; "pred" defaults to "dec". Saves each built pack as outdir/<voice>.pt.
Usage: kokoro_run.py cfg.json lines.tsv outdir [threads]"""
import sys, time, json, torch, soundfile as sf
from kokoro import KPipeline
from huggingface_hub import hf_hub_download
cfg = json.load(open(sys.argv[1])); lines = [l.rstrip('\n').split('\t') for l in open(sys.argv[2])]; outdir = sys.argv[3]
torch.set_num_threads(int(sys.argv[4]) if len(sys.argv) > 4 else 4)
pipe = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")
def pack(src):
    p = src if src.endswith(".pt") else hf_hub_download("hexgrad/Kokoro-82M", f"voices/{src}.pt")
    return torch.load(p, weights_only=True).float()
def mix(spec): return sum(w * pack(s) for s, w in spec) / sum(w for _, w in spec)
for name, c in cfg.items():
    d = mix(c["dec"]); p = mix(c.get("pred", c["dec"]))
    v = torch.cat([d[..., :128], p[..., 128:]], -1)
    torch.save(v, f"{outdir}/{name}.pt")
    for lid, text in lines:
        t = time.time(); y = torch.cat([r.audio for r in pipe(text, voice=v, speed=c.get("speed", 1.0))]).numpy(); dt = time.time() - t
        sf.write(f"{outdir}/{name}-{lid}.wav", y, 24000)
        print(json.dumps({"voice": name, "id": lid, "secs": round(dt, 2), "dur": round(len(y) / 24000, 2), "rtf": round(dt / (len(y) / 24000), 2)}), flush=True)
