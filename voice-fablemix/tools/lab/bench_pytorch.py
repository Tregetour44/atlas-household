"""Same measurements as eval/bench.py for Kokoro's PyTorch model (kokoro 0.9.4 KModel, CPU), fed the backend's own
phoneme chunks, for the engine comparison. Usage: bench_pytorch.py kokoro-v1_0.pth config.json voice.npy threads"""
import json, os, statistics, sys, time
t0 = time.perf_counter()
import numpy as np, torch
sys.path.insert(0, "/home/user/atlas-household/voice-fablemix"); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import kokoro_backend as kb
from kokoro import KModel
torch.set_num_threads(int(sys.argv[4]))
model = KModel(config=sys.argv[2], model=sys.argv[1]).eval()
pack = torch.from_numpy(np.load(sys.argv[3]))
g2p = kb.build_g2p()
load_s = time.perf_counter() - t0
import resource
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "eval"))
from bench import REPLIES
def run(text):
    t = time.perf_counter(); first = None; n = 0
    for ps in kb.plan_chunks(g2p, text):
        torch.manual_seed(0)
        with torch.no_grad():
            y = model(ps, pack[len(ps) - 1], 0.95).numpy()
        first = first if first is not None else time.perf_counter() - t
        n += len(y)
    return first, time.perf_counter() - t, n / 24000
out = {"engine": "pytorch", "threads": int(sys.argv[4]), "load_s": round(load_s, 2),
       "rss_after_load_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)}
f, tot, dur = run(REPLIES["medium"]); out["cold_medium"] = {"first_s": round(f, 3), "total_s": round(tot, 3)}
for name, text in REPLIES.items():
    rs = [run(text) for _ in range(5)]
    out[name] = {"first_s": round(statistics.median(r[0] for r in rs), 3), "rtf": round(statistics.median(r[1] / r[2] for r in rs), 3)}
out["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
print(json.dumps(out))
