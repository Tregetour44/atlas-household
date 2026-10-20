"""Score <voice>-<id>.wav files the voice-scout way, plus parity measures.
UTMOS22-strong, median F0 + spread (pYIN, semitones), WER (faster-whisper small.en, voice-lewis-small normaliser),
accent (CommonAccent ECAPA, England-minus-US), ECAPA similarity to the liked Chatterbox-Fable centroid (sim_cbfable,
as the scout) and to the scout's own Fable-mix render of the same line (sim_scout, ECAPA; rsim_scout, Resemblyzer),
and log-mel distance (dB) to a reference render of the same line (lmd_ref) when REF_DIR/REF_TAG are set.
Usage: eval.py OUT.jsonl wav...   env: TEXT=lines.tsv SCOUT=dir-of-scout-mp3 REF_DIR=dir REF_TAG=pt"""
import sys, os, json, glob, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["VLS_MODELS"] = os.path.join(HERE, "models")
import numpy as np, librosa, torch
sys.path.insert(0, HERE)
import metrics
TEXT = dict(l.rstrip("\n").split("\t", 1) for l in open(os.environ["TEXT"])) if os.environ.get("TEXT") else {}
for _l in (open(os.environ["TEXTLOG"]) if os.environ.get("TEXTLOG") else []):
    if _l.startswith("{"): _r = json.loads(_l); TEXT[(_r["tag"], _r["id"])] = _r["text"]
M = os.path.join(HERE, "models")
ev = metrics.Evaluator(want=("asr", "spk", "mos"))
from speechbrain.inference.classifiers import EncoderClassifier
acc = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa", savedir=os.path.join(M, "accent"))
lab = acc.hparams.label_encoder
ENG, US = lab.encode_label("england"), lab.encode_label("us")
from resemblyzer import VoiceEncoder, preprocess_wav
venc = VoiceEncoder("cpu", verbose=False)
R = os.environ.get("REFS", os.path.join(os.path.dirname(HERE), "refs"))
cent = np.mean([ev.embed(metrics.load16(f)) for f in sorted(glob.glob(os.path.join(R, "chatterbox-kokoro-fable-ref-*.mp3")))], 0)
cent /= np.linalg.norm(cent)
SCOUT = os.environ.get("SCOUT"); REF_DIR = os.environ.get("REF_DIR"); REF_TAG = os.environ.get("REF_TAG", "pt")

def logmel(y):
    m = librosa.feature.melspectrogram(y=y, sr=16000, n_fft=1024, hop_length=160, n_mels=80, fmin=50, fmax=7600)
    return 10 * np.log10(np.maximum(m, 1e-6))

out = open(sys.argv[1], "a")
for f in sys.argv[2:]:
    b = os.path.basename(f).rsplit(".", 1)[0]; voice, lid = b.rsplit("-", 1)
    y = metrics.load16(f)
    r = {"voice": voice, "id": lid, "dur": round(len(y) / 16000, 2)}
    r["utmos"] = round(ev.utmos(y), 3)
    f0, vo, _ = librosa.pyin(y, fmin=55, fmax=320, sr=16000, frame_length=1024)
    f0 = f0[~np.isnan(f0)]
    r["f0"] = round(float(np.median(f0)), 1) if len(f0) else None
    r["f0_st"] = round(float(np.std(12 * np.log2(f0 / np.median(f0)))), 2) if len(f0) else None
    hyp, span = ev.transcribe(y)
    import re; ref = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", TEXT.get((voice, lid), TEXT.get(lid))); r["wer"] = round(metrics.wer(ref, hyp), 3); r["asr"] = hyp
    r["wps"] = round(len(ref.split()) / max(span[1] - span[0], 0.1), 2)
    with torch.no_grad():
        o = acc.classify_batch(torch.tensor(y).unsqueeze(0))[0].squeeze()
    r["accent"] = lab.decode_ndim(int(o.argmax())); r["eng_us"] = round(float(o[ENG] - o[US]), 3)
    e = ev.embed(y)
    r["sim_cbfable"] = round(float(e @ cent), 3)
    sc = os.path.join(SCOUT, f"kokoro-fablemix-{lid}.mp3") if SCOUT else None
    if sc and os.path.exists(sc):
        ys = metrics.load16(sc)
        r["sim_scout"] = round(float(e @ ev.embed(ys)), 3)
        r["rsim_scout"] = round(float(venc.embed_utterance(preprocess_wav(y, 16000)) @ venc.embed_utterance(preprocess_wav(ys, 16000))), 3)
    rf = os.path.join(REF_DIR, f"{REF_TAG}-{lid}.wav") if REF_DIR else None
    if rf and os.path.exists(rf) and os.path.abspath(rf) != os.path.abspath(f):
        a, c = logmel(y), logmel(metrics.load16(rf)); n = min(a.shape[1], c.shape[1])
        r["lmd_ref"] = round(float(np.mean(np.abs(a[:, :n] - c[:, :n]))), 2); r["len_ratio"] = round(c.shape[1] / a.shape[1], 3)
    out.write(json.dumps(r, ensure_ascii=False) + "\n"); out.flush(); print(json.dumps(r, ensure_ascii=False), flush=True)
