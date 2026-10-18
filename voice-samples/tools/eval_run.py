"""Score wavs: accent (CommonAccent ECAPA), UTMOS naturalness, Whisper WER."""
import sys, os, glob, json, re, warnings
warnings.filterwarnings("ignore")
import torch, librosa, numpy as np, jiwer
torch.set_num_threads(4)
S = os.path.dirname(os.path.abspath(__file__))
LINES = [l.strip() for l in open(os.path.join(S, "lines.txt")) if l.strip()]
files = sorted(glob.glob(sys.argv[1]))
want = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else {"accent", "mos", "wer"}
from speechbrain.inference.classifiers import EncoderClassifier
acc = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa",
                                     savedir=os.path.join(S, "models/accent"))
labels = acc.hparams.label_encoder
if "mos" in want:
    mos = torch.hub.load(os.path.join(S, "models/SpeechMOS"), "utmos22_strong", source="local", trust_repo=True)
if "wer" in want:
    from faster_whisper import WhisperModel
    asr = WhisperModel("small.en", device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[^a-z0-9' ]", " ", s.lower().replace("80", "eighty").replace("8", "eight").replace("10", "ten"))
for f in files:
    y, _ = librosa.load(f, sr=16000)
    t = torch.tensor(y).unsqueeze(0)
    r = {"file": os.path.basename(f)}
    out = acc.classify_batch(t)
    o = out[0].squeeze()  # cosine scores per accent class
    idx = o.argsort(descending=True)[:2]
    r["accent"] = [(labels.decode_ndim(int(i)), round(float(o[i]), 2)) for i in idx]
    eng = labels.encode_label("england"); us = labels.encode_label("us")
    r["eng_minus_us"] = round(float(o[eng] - o[us]), 2)
    f0, vo, _ = librosa.pyin(y, fmin=60, fmax=300, sr=16000)
    r["f0_hz"] = round(float(np.nanmedian(f0)), 0)
    n_line = int(re.search(r"-(\d)\.wav$", f).group(1))
    r["wps"] = round(len(LINES[n_line - 1].split()) / (len(y) / 16000), 2)
    if "mos" in want:
        r["utmos"] = round(float(mos(t, 16000)), 2)
    if "wer" in want:
        n = int(re.search(r"-(\d)\.wav$", f).group(1))
        hyp = " ".join(s.text for s in asr.transcribe(y, beam_size=1)[0])
        r["wer"] = round(jiwer.wer(norm(LINES[n - 1]), norm(hyp)), 2)
        r["asr"] = hyp.strip()
    print(json.dumps(r), flush=True)
