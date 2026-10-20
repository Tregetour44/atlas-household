"""Score <voice>-<id>.wav files: UTMOS, median F0, F0 spread, WER (small.en), accent (CommonAccent ECAPA),
speaker similarity (ECAPA) to the household's liked Chatterbox-on-Kokoro-bm_fable render. Usage: eval.py OUT.jsonl wav...
Reuses metrics.py (voice-lewis-small) for text normalisation and WER."""
import sys, os, json, glob, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["VLS_MODELS"] = os.path.join(HERE, "models")
import numpy as np, librosa, torch
sys.path.insert(0, HERE)
import metrics
TEXT = {}
for fn in ("lines.tsv", "heldout.tsv", "reftext.tsv"):
    for l in open(os.path.join(HERE, fn)):
        k, v = l.rstrip("\n").split("\t"); TEXT[k] = v
M = os.path.join(HERE, "models")
ev = metrics.Evaluator(want=("asr", "spk", "mos"))
from speechbrain.inference.classifiers import EncoderClassifier
acc = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa", savedir=os.path.join(M, "accent"))
lab = acc.hparams.label_encoder
ENG, US = lab.encode_label("england"), lab.encode_label("us")
R = os.path.join(os.path.dirname(HERE), "refs")
cent = np.mean([ev.embed(metrics.load16(f)) for f in sorted(glob.glob(os.path.join(R, "chatterbox-kokoro-fable-ref-*.mp3")))], 0)
cent /= np.linalg.norm(cent)
out = open(sys.argv[1], "a")
for f in sys.argv[2:]:
    b = os.path.basename(f)[:-4]; voice, lid = b.rsplit("-", 1)
    y = metrics.load16(f)
    r = {"voice": voice, "id": lid, "dur": round(len(y) / 16000, 2)}
    r["utmos"] = round(ev.utmos(y), 3)
    f0, vo, _ = librosa.pyin(y, fmin=55, fmax=320, sr=16000, frame_length=1024)
    f0 = f0[~np.isnan(f0)]
    r["f0"] = round(float(np.median(f0)), 1) if len(f0) else None
    r["f0_st"] = round(float(np.std(12 * np.log2(f0 / np.median(f0)))), 2) if len(f0) else None
    hyp, span = ev.transcribe(y)
    r["wer"] = round(metrics.wer(TEXT[lid], hyp), 3); r["asr"] = hyp
    r["wps"] = round(len(TEXT[lid].split()) / max(span[1] - span[0], 0.1), 2)
    with torch.no_grad():
        o = acc.classify_batch(torch.tensor(y).unsqueeze(0))[0].squeeze()
    r["accent"] = lab.decode_ndim(int(o.argmax())); r["eng_us"] = round(float(o[ENG] - o[US]), 3)
    r["sim_cbfable"] = round(float(ev.embed(y) @ cent), 3)
    out.write(json.dumps(r) + "\n"); out.flush(); print(json.dumps(r), flush=True)
