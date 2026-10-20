"""KittenTTS 2: built-in voice or clone of a reference, with optional speaker-embedding mixing.
cfg JSON: {voice: {"voice": name | "reference": wav, "reference_text": str, "preset": "stable"|"expressive",
"mix": [[{"voice": n} | {"reference": wav, "reference_text": t}, weight], ...]}}. Usage: kitten_run.py cfg.json lines.tsv outdir [threads]"""
import sys, time, json, copy, torch, soundfile as sf
from kittenml import KittenTTS
cfg = json.load(open(sys.argv[1])); lines = [l.rstrip('\n').split('\t') for l in open(sys.argv[2])]; outdir = sys.argv[3]
torch.set_num_threads(int(sys.argv[4]) if len(sys.argv) > 4 else 4)
m = KittenTTS("KittenML/kitten-tts-2")
def spk(c): return m._speaker(c.get("voice"), c.get("reference"), c.get("reference_text"))
for name, c in cfg.items():
    ref = copy.copy(spk(c))
    if c.get("mix"):
        e = sum(w * spk(s)["embedding"] for s, w in c["mix"])
        ref["embedding"] = e * (ref["embedding"].norm() / e.norm())
    for lid, text in lines:
        opts = m._resolve_advanced({"seed": 1234})
        t = time.time()
        wavs = list(m._synthesize(ref, text, c.get("preset", "stable"), 1000, True, None,
                                  dict(temperature=None, top_k=None, top_p=None, min_p=None), opts))
        y = m._join(wavs, opts["chunk_gap_s"]); dt = time.time() - t
        sf.write(f"{outdir}/{name}-{lid}.wav", y, m.sample_rate)
        print(json.dumps({"voice": name, "id": lid, "secs": round(dt, 2), "dur": round(len(y) / m.sample_rate, 2), "rtf": round(dt / (len(y) / m.sample_rate), 2)}), flush=True)
