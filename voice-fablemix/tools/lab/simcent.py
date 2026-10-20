"""ECAPA and Resemblyzer cosine of each wav to the centroid of the scout's 18 Fable-mix clips (voice identity check
for lines the scout didn't render). Usage: simcent.py OUT.jsonl wav..."""
import sys, os, json, glob, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); os.environ["VLS_MODELS"] = os.path.join(HERE, "models")
sys.path.insert(0, HERE)
import numpy as np, metrics
from resemblyzer import VoiceEncoder, preprocess_wav
ev = metrics.Evaluator(want=("spk",)); ve = VoiceEncoder("cpu", verbose=False)
sc = sorted(glob.glob(os.path.join(os.path.dirname(HERE), "scoutmp3", "kokoro-fablemix-[LH]*.mp3")))
ys = [metrics.load16(f) for f in sc]
ce = np.mean([ev.embed(y) for y in ys], 0); ce /= np.linalg.norm(ce)
cr = np.mean([ve.embed_utterance(preprocess_wav(y, 16000)) for y in ys], 0); cr /= np.linalg.norm(cr)
out = open(sys.argv[1], "a")
for f in sys.argv[2:]:
    b = os.path.basename(f)[:-4]; v, i = b.rsplit("-", 1); y = metrics.load16(f)
    r = {"voice": v, "id": i, "ecapa_scoutcent": round(float(ev.embed(y) @ ce), 3),
         "resem_scoutcent": round(float(ve.embed_utterance(preprocess_wav(y, 16000)) @ cr), 3)}
    out.write(json.dumps(r) + "\n")
print(len(sc), "scout clips")
