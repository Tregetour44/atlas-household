import sys, json, re, numpy as np, soundfile as sf, os
sys.path.insert(0, "/home/user/atlas-household/voice-fablemix")
import kokoro_backend as kb, onnxruntime as ort
g = kb.build_g2p(); vocab = json.load(open("dl/pt/config.json"))["vocab"]
pack = np.load("work/en_GB-fablemix.npy"); short = np.load("work/en_GB-fablemix-short.npy")
s = ort.InferenceSession("dl/onnx/onnx/model.onnx", providers=["CPUExecutionProvider"])
texts = {"L01": ["Done.", "Kitchen lights off."], "H01": ["Done: Fountain Spotlight on.", "Checked."], "A01": ["Done: Study lights on.", "Checked."],
         "S04": ["Done.", "Blinds closed."], "S08": ["Done.", "Loft lamp off."], "W01": ["Done: Good Night is on.", "Checked."], "H06": ["Done: Wall Light off.", "Checked."]}
J = {"sp": " ", "ell": "… ", "dash": " — ", "semi": "; ", "dots": ". . ", "stopell": ".… "}
os.makedirs("out/joins", exist_ok=True)
for tag, j in J.items():
    for lid, parts in texts.items():
        ps = [kb.phonemize(g, p, vocab) for p in parts]
        if tag != "sp":
            ps = [re.sub(r"[.!?]$", "", ps[0]) ] + ps[1:] if tag in ("ell", "dash", "semi") else ps
        p = ps[0] + j + ps[1] if tag in ("ell", "dash", "semi") else (ps[0][:-1] + j + ps[1] if tag in ("dots", "stopell") else ps[0] + " " + ps[1])
        n = len(p); w = min(max((60 - n) / 20, 0), 1)
        st = (1 - w) * pack[n - 1] + w * short[max(n, 40) - 1]
        y = s.run(None, {"input_ids": np.array([[0] + [vocab[c] for c in p if c in vocab] + [0]]), "style": st.astype(np.float32), "speed": np.array([0.95], np.float32)})[0].reshape(-1) * 0.678
        sf.write(f"out/joins/{tag}-{lid}.wav", y, 24000, subtype="FLOAT")
        print(json.dumps({"tag": tag, "id": lid, "text": " ".join(parts), "ps": p}, ensure_ascii=False))
