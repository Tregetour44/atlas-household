"""Render lines.tsv with one engine, whole line per inference (the scout's way), same misaki British G2P for all.
Usage: render.py ENGINE OUTDIR [threads] [ids-regex]
ENGINE: pt (kokoro PyTorch, seeded noise), pt0 (PyTorch with the sine-source noise and random phase zeroed),
        ort32 / ort16 / ort8 (onnx-community fp32 / fp16 / dynamic-int8 ONNX in onnxruntime)."""
import sys, os, json, time, re
os.environ["HF_HUB_OFFLINE"] = "1"
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); SCR = os.path.dirname(HERE)
eng, out = sys.argv[1], sys.argv[2]; thr = int(sys.argv[3]) if len(sys.argv) > 3 else 4
pat = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
os.makedirs(out, exist_ok=True)
lines = [l.rstrip("\n").split("\t") for l in open(os.path.join(HERE, "lines.tsv"))]
if pat: lines = [l for l in lines if pat.search(l[0])]
from misaki import en, espeak
g2p = en.G2P(british=True, fallback=espeak.EspeakFallback(british=True), unk="")
cfg = json.load(open(f"{SCR}/dl/pt/config.json")); vocab = cfg["vocab"]
pack = np.load(f"{SCR}/work/en_GB-fablemix.npy")
SPEED = 0.95

def phonemes(text):
    return g2p(text)[0]

if eng.startswith("pt"):
    import torch
    torch.set_num_threads(thr)
    from kokoro import KModel
    if eng == "pt0":
        torch.randn_like = lambda x, *a, **k: torch.zeros_like(x)
        _rand = torch.rand
        torch.rand = lambda *a, **k: torch.zeros(*a, device=k.get("device"))
    model = KModel(config=f"{SCR}/dl/pt/config.json", model=f"{SCR}/dl/pt/kokoro-v1_0.pth").eval()
    P = torch.from_numpy(pack)
    def synth(ps):
        torch.manual_seed(int(os.environ.get("SEED", "1234")))
        with torch.no_grad():
            return model(ps, P[len(ps) - 1], SPEED).numpy()
else:
    import onnxruntime as ort
    fn = {"ort32": "model.onnx", "ort16": "model_fp16.onnx", "ort8": "model_quantized.onnx"}[eng]
    so = ort.SessionOptions(); so.intra_op_num_threads = thr; so.inter_op_num_threads = 1
    sess = ort.InferenceSession(f"{SCR}/dl/onnx/onnx/{fn}", so, providers=["CPUExecutionProvider"])
    def synth(ps):
        ids = [0] + [vocab[c] for c in ps if c in vocab] + [0]
        return sess.run(None, {"input_ids": np.array([ids], np.int64), "style": pack[len(ps) - 1],
                               "speed": np.array([SPEED], np.float32)})[0].reshape(-1)

synth(phonemes("Warm up, please."))
for lid, text in lines:
    t0 = time.perf_counter(); ps = phonemes(text); t1 = time.perf_counter(); y = synth(ps); t2 = time.perf_counter()
    sf.write(f"{out}/{os.environ.get("TAG", eng)}-{lid}.wav", y, 24000, subtype="FLOAT")
    print(json.dumps({"eng": eng, "id": lid, "ps": ps, "g2p_s": round(t1 - t0, 3), "syn_s": round(t2 - t1, 3),
                      "dur": round(len(y) / 24000, 2), "rtf": round((t2 - t0) / (len(y) / 24000), 3)}, ensure_ascii=False), flush=True)
