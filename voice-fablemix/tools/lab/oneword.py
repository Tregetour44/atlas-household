import json, numpy as np, soundfile as sf, onnxruntime as ort
vocab = json.load(open("dl/pt/config.json"))["vocab"]
pack = np.load("work/en_GB-fablemix.npy"); short = np.load("work/en_GB-fablemix-short.npy")
s = ort.InferenceSession("dl/onnx/onnx/model.onnx", providers=["CPUExecutionProvider"])
W = {"checked": "ʧˈɛkt", "done": "dˈʌn", "allset": "ˈɔːl sˈɛt", "lightsoff": "lˈIts ˈɒf"}
V = {"plain": ("{}.", None), "dotdot": ("{}..", None), "ellpre": ("… {}.", None), "excl": ("{}!", None), "spaces": (" {}. ", None),
     "row80": ("{}.", 80), "row120": ("{}.", 120), "ellpost": ("{}.…", None), "dashpre": ("— {}.", None)}
for vt, (fmt, row) in V.items():
    for wt, w in W.items():
        p = fmt.format(w); n = len(p)
        st = pack[row - 1] if row else short[39]
        y = s.run(None, {"input_ids": np.array([[0] + [vocab[c] for c in p if c in vocab] + [0]]), "style": st, "speed": np.array([0.95], np.float32)})[0].reshape(-1) * 0.678
        sf.write(f"out/oneword/{vt}-{wt}.wav", y, 24000, subtype="FLOAT")
