"""Render lines through the real kokoro_backend, with module settings overridden per variant (before/after pairs).
Usage: bk_render.py spec.json lines.tsv outdir
spec: {TAG: {"set": {"MERGE_BELOW": 0, "LEXICON": {}, "REWRITES": "none", ...}, "sub": [[regex, repl]], "speed": 0.95}}
"sub" are normaliser-level text rewrites applied before synth(). Writes TAG-ID.wav (float, 24 kHz) and a JSON log
line per clip with the text, the planned phoneme chunks, and the time to first chunk and in total."""
import sys, os, json, re, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SCR = os.path.dirname(HERE)
sys.path.insert(0, os.environ.get("BACKEND_DIR", "/home/user/atlas-household/voice-fablemix"))
import kokoro_backend as kb
import soundfile as sf
spec = json.load(open(sys.argv[1])); lines = [l.rstrip("\n").split("\t", 1) for l in open(sys.argv[2]) if l.strip()]
out = sys.argv[3]; os.makedirs(out, exist_ok=True)
MODEL = os.environ.get("MODEL_DIR", "/home/user/atlas-household/voice-fablemix/model")
defaults = {k: getattr(kb, k) for k in ("MERGE_WORDS", "ONE_WORD_ROW", "CLAUSE_SPLIT", "LEXICON", "REWRITES", "OUTPUT_GAIN", "SHORT_FULL", "SHORT_NONE", "EDGE_KEEP_S", "FINAL_PAUSE_S", "CLAUSE_PAUSE_S", "PAUSE_S")}
for tag, c in spec.items():
    for k, v in defaults.items():
        setattr(kb, k, v)
    for k, v in c.get("set", {}).items():
        setattr(kb, k, () if v == "none" else v)
    if c.get("drop_timer_rewrite"):
        kb.REWRITES = tuple(r for r in kb.REWRITES if "Timer" not in r[0].pattern)
    synth, rate = kb.kokoro_synth(MODEL, speed=c.get("speed", 0.95), threads=int(os.environ.get("THREADS", "4")))
    g2p = kb.build_g2p()
    for lid, text in lines:
        for a, b in c.get("sub", []):
            text = re.sub(a, b, text)
        t0 = time.perf_counter(); first = None; parts = []
        for pcm in synth(text):
            if first is None:
                first = time.perf_counter() - t0
            parts.append(np.frombuffer(pcm, "<i2"))
        total = time.perf_counter() - t0
        y = np.concatenate(parts).astype(np.float32) / 32768.0
        sf.write(f"{out}/{tag}-{lid}.wav", y, rate, subtype="FLOAT")
        print(json.dumps({"tag": tag, "id": lid, "text": text, "chunks": kb.plan_chunks(g2p, text), "dur": round(len(y) / rate, 2),
                          "first_s": round(first, 3), "total_s": round(total, 3)}, ensure_ascii=False), flush=True)
