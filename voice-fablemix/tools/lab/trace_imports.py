import sys, os, json, importlib.metadata as md
SCR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["HF_HUB_OFFLINE"]="1"
import numpy as np, onnxruntime as ort, spacy.util
from misaki import en, espeak
g=en.G2P(british=True, fallback=espeak.EspeakFallback(british=True), unk="")
print(g("Timer set: ZeroCharge pergola ensuite at 9:05pm, 23 degrees. Xyzzyq!")[0], file=sys.stderr)
s=ort.InferenceSession(f"{SCR}/dl/onnx/onnx/model_quantized.onnx", providers=["CPUExecutionProvider"])
pk=np.load(f"{SCR}/work/en_GB-fablemix.npy")
s.run(None,{"input_ids":np.array([[0,50,51,0]],np.int64),"style":pk[1],"speed":np.array([1.0],np.float32)})
top={m.split(".")[0] for m in list(sys.modules)}
pkg2dist=md.packages_distributions()
dists=sorted({d for t in top for d in pkg2dist.get(t,[])})
print(json.dumps(dists))
