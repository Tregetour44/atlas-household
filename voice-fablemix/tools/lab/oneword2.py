import json, numpy as np, soundfile as sf, onnxruntime as ort
vocab = json.load(open("dl/pt/config.json"))["vocab"]
pack = np.load("work/en_GB-fablemix.npy"); short = np.load("work/en_GB-fablemix-short.npy")
s = ort.InferenceSession("dl/onnx/onnx/model.onnx", providers=["CPUExecutionProvider"])
W = {"done": "dˈʌn", "checked": "ʧˈɛkt", "cancelled": "kˈansᵊld", "okay": "ˌQkˈA", "sorry": "sˈɒɹi", "certainly": "sˈɜːtᵊnli"}
V = {"s39": ("{}.", short, 39, 0.95), "p80": ("{}.", pack, 80, 0.95), "p120": ("{}.", pack, 120, 0.95), "s39sp": (" {}. ", short, 39, 0.95),
     "p80sp": (" {}. ", pack, 80, 0.95), "s39slow": ("{}.", short, 39, 0.85), "s80": ("{}.", short, 80, 0.95)}
for vt, (fmt, pk, row, sp) in V.items():
    for wt, w in W.items():
        p = fmt.format(w)
        y = s.run(None, {"input_ids": np.array([[0] + [vocab[c] for c in p if c in vocab] + [0]]), "style": pk[row - 1], "speed": np.array([sp], np.float32)})[0].reshape(-1) * 0.678
        sf.write(f"out/oneword/{vt}-{wt}.wav", y, 24000, subtype="FLOAT")
