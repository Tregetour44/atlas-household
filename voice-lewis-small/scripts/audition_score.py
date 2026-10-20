"""Score audition voices. Files: <dir>/<tag>-<S1..S4|L01..L10>.wav (or <tag>-<1..14>.wav from fable_render.py).
Per voice: median F0 (pYIN), F0 spread (st), UTMOS, Whisper small.en WER, England-accent score (CommonAccent ECAPA,
England minus US cosine), ECAPA similarity to a reference clip, pace (words per voiced second), and the end-of-question
pitch rise on L02 (semitones, last 20% of voiced frames vs the median).
usage: audition_score.py <all14.txt> <ref.wav> <out.jsonl> <wav_dir>"""
import glob, json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, librosa, torch
from metrics import Evaluator, load16, wer

lines_path, ref, out, d = sys.argv[1:5]
lines = [l.strip() for l in open(lines_path, encoding="utf-8") if l.strip()]
NAMES = [f"S{i}" for i in range(1, 5)] + [f"L{i:02d}" for i in range(1, 11)]
ev = Evaluator(("asr", "spk", "mos"), threads=int(os.environ.get("OMP_NUM_THREADS", "4")))
from speechbrain.inference.classifiers import EncoderClassifier
acc = EncoderClassifier.from_hparams(source="Jzuluaga/accent-id-commonaccent_ecapa",
                                     savedir=os.path.join(os.environ.get("VLS_MODELS", "/tmp/claude-0/work/models"), "accent"))
lab = acc.hparams.label_encoder
eng, us = lab.encode_label("england"), lab.encode_label("us")
ref_e = ev.embed(load16(ref))
groups = collections.defaultdict(dict)
for f in sorted(glob.glob(os.path.join(d, "*.wav"))):
    m = re.match(r"(.+)-(S\d|L\d\d|\d+)\.wav$", os.path.basename(f))
    tag, key = m.group(1), m.group(2)
    if key.isdigit():
        key = NAMES[int(key) - 1]
    groups[tag][key] = f
for tag, files in groups.items():
    rec = collections.defaultdict(list)
    for key, f in files.items():
        y = load16(f); text = lines[NAMES.index(key)]
        f0, vf, _ = librosa.pyin(y, fmin=55, fmax=350, sr=16000, frame_length=1024)
        v = f0[~np.isnan(f0)]
        if len(v):
            rec["f0"].append(float(np.median(v))); rec["f0_spread"].append(float(np.std(12 * np.log2(v / np.median(v)))))
            if key == "L02":
                tail = v[int(0.8 * len(v)):]
                rec["q_rise"].append(float(12 * np.log2(np.median(tail) / np.median(v))))
        rec["utmos"].append(ev.utmos(y))
        hyp, _ = ev.transcribe(y); rec["wer"].append(wer(text, hyp))
        rec["spk_ref"].append(float(ev.embed(y) @ ref_e))
        o = acc.classify_batch(torch.tensor(y).unsqueeze(0))[0].squeeze()
        rec["eng_us"].append(float(o[eng] - o[us]))
        voiced = float(np.sum(vf)) * 1024 / 4 / 16000 if vf is not None else len(y) / 16000
        rec["wps"].append(len(text.split()) / max(len(y) / 16000, 0.1))
        rec["asr_" + key] = hyp
    r = {k: (round(float(np.median(v)), 1) if k == "f0" else round(float(np.mean(v)), 3)) if isinstance(v, list) else v
         for k, v in rec.items()}
    r["tag"] = tag; r["n"] = len(files)
    open(out, "a").write(json.dumps(r) + "\n")
    print(tag, {k: r[k] for k in ("f0", "f0_spread", "utmos", "wer", "spk_ref", "eng_us", "wps", "q_rise") if k in r}, flush=True)
