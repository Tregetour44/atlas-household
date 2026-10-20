"""Quick screen of arbitrary wavs (no text): accent, median F0, UTMOS, sim to the Chatterbox-Fable centroid."""
import sys, os, glob, json, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); os.environ["VLS_MODELS"] = os.path.join(HERE, "models")
import numpy as np, librosa, torch
sys.path.insert(0, HERE); import metrics
ev = metrics.Evaluator(want=("spk", "mos"))
from speechbrain.inference.classifiers import EncoderClassifier
acc = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa", savedir=os.path.join(HERE, "models", "accent"))
lab = acc.hparams.label_encoder; ENG, US = lab.encode_label("england"), lab.encode_label("us")
R = os.path.join(os.path.dirname(HERE), "refs")
cent = np.mean([ev.embed(metrics.load16(f)) for f in sorted(glob.glob(os.path.join(R, "chatterbox-kokoro-fable-ref-*.mp3")))], 0); cent /= np.linalg.norm(cent)
for f in sys.argv[1:]:
    y = metrics.load16(f)
    with torch.no_grad(): o = acc.classify_batch(torch.tensor(y).unsqueeze(0))[0].squeeze()
    top = o.argsort(descending=True)[:2]
    f0, _, _ = librosa.pyin(y, fmin=55, fmax=320, sr=16000, frame_length=1024); f0 = f0[~np.isnan(f0)]
    print(json.dumps({"f": os.path.basename(f), "acc": [lab.decode_ndim(int(i)) for i in top], "eng_us": round(float(o[ENG] - o[US]), 2),
                      "f0": round(float(np.median(f0)), 1), "utmos": round(ev.utmos(y), 2), "sim": round(float(ev.embed(y) @ cent), 3)}), flush=True)
