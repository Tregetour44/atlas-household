"""Variant renderer for the weak-spot experiments (ONNX fp32 + misaki British G2P, deterministic).
Usage: exp.py spec.json lines.tsv outdir
spec: {TAG: {"pred": {"fable": .7, "inno": .3, ...}, "dec": {...}, "floor": 0, "speed": 0.95,
             "short_speed": null, "short_len": 40, "short_pred": null, "mode": "whole"|"sent"|"merge", "merge_min": 30,
             "gap": 0.0, "lex": {word: phonemes}, "sub": [[regex, repl], ...]}}
pred/dec default to the Fable-mix pack itself. Packs: fable, george, lewis, daniel (stock), inno (reconstructed
from the Fable-mix blend), mix (Fable-mix). "short_*" applies to whole replies with <= short_len phonemes."""
import sys, os, json, re, time
import numpy as np, soundfile as sf, onnxruntime as ort
HERE = os.path.dirname(os.path.abspath(__file__)); SCR = os.path.dirname(HERE)
spec = json.load(open(sys.argv[1])); lines = [l.rstrip("\n").split("\t", 1) for l in open(sys.argv[2]) if l.strip()]
out = sys.argv[3]; os.makedirs(out, exist_ok=True)
from misaki import en, espeak
vocab = json.load(open(f"{SCR}/dl/pt/config.json"))["vocab"]
P = {k: np.load(f"{SCR}/work/packs/{k}.npy") for k in ("fable", "george", "lewis", "daniel", "inno", "mix")}
so = ort.SessionOptions(); so.intra_op_num_threads = 4; so.inter_op_num_threads = 1
sess = ort.InferenceSession(f"{SCR}/dl/onnx/onnx/model.onnx", so, providers=["CPUExecutionProvider"])
SENT = re.compile(r"(?<=[.!?…])[\"')\]]*\s+")

def blend(w):
    return sum(v * P[k] for k, v in w.items()) / sum(w.values())

def build(c, short=False):
    d = blend(c["dec"]) if "dec" in c else P["mix"]
    pw = c.get("short_pred") if short and c.get("short_pred") else c.get("pred")
    p = blend(pw) if pw else P["mix"]
    return np.concatenate([d[..., :128], p[..., 128:]], -1).astype(np.float32)

def run(ps, pack, speed, floor):
    ids = [0] + [vocab[x] for x in ps if x in vocab] + [0]
    row = pack[min(max(len(ps), floor), 510) - 1]
    return sess.run(None, {"input_ids": np.array([ids], np.int64), "style": row, "speed": np.array([speed], np.float32)})[0].reshape(-1)

for tag, c in spec.items():
    g2p = en.G2P(british=True, fallback=espeak.EspeakFallback(british=True), unk="")
    g2p.lexicon.golds.update(c.get("lex", {}))
    ph = lambda t: "".join(x for x in g2p(t)[0] if x in vocab).strip()
    for lid, text in lines:
        for a, b in c.get("sub", []):
            text = re.sub(a, b, text)
        full = ph(text); short = len(full) <= c.get("short_len", 40)
        pack = build(c, short); speed = c.get("short_speed") if short and c.get("short_speed") else c.get("speed", 0.95)
        mode = c.get("mode", "whole")
        if mode == "whole":
            chunks = [full]
        else:
            chunks = [ph(s) for s in SENT.split(text.strip()) if s.strip()]
            if mode == "merge":
                m = []
                for x in chunks:
                    if m and len(m[-1]) < c.get("merge_min", 30):
                        m[-1] = m[-1] + " " + x
                    else:
                        m.append(x)
                if len(m) > 1 and len(m[-1]) < c.get("merge_min", 30):
                    m[-2] = m[-2] + " " + m.pop()
                chunks = m
        gap = np.zeros(int(c.get("gap", 0.0) * 24000), np.float32)
        t0 = time.perf_counter(); parts = []
        for i, x in enumerate(chunks):
            parts.append(run(x, pack, speed, c.get("floor", 0)))
            if i < len(chunks) - 1 and len(gap):
                parts.append(gap)
        y = np.concatenate(parts); dt = time.perf_counter() - t0
        sf.write(f"{out}/{tag}-{lid}.wav", y, 24000, subtype="FLOAT")
        print(json.dumps({"tag": tag, "id": lid, "text": text, "ps": " | ".join(chunks), "dur": round(len(y) / 24000, 2),
                          "secs": round(dt, 2)}, ensure_ascii=False), flush=True)
