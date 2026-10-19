"""Summarise systems against the teacher.
Reads score_clips.py jsonl files (one per system, same clip ids as the teacher's) and the audio dirs.
Per system: UTMOS, WER, speaker similarity to the reference and to the teacher centroid (mean ECAPA embedding of the
teacher's renders of the same eval set), same-text MCD-DTW vs the teacher (dB, lower = closer), pitch (median Hz and
spread in semitones) and pace (words per voiced second).
usage: compare.py <teacher_name> name=scores.jsonl:audio_dir ... > table"""
import glob, json, os, sys
import numpy as np, librosa

def load(spec):
    name, rest = spec.split("=", 1)
    sc, d = rest.split(":", 1)
    S = {json.loads(l)["id"]: json.loads(l) for l in open(sc)}
    return name, S, d

def audio(d, cid):
    f = (glob.glob(os.path.join(d, cid + ".*")) or [None])[0]
    y, _ = librosa.load(f, sr=16000)
    return librosa.effects.trim(y, top_db=40)[0]

def mcd(a, b):
    ma = librosa.feature.mfcc(y=a, sr=16000, n_mfcc=25, n_fft=1024, hop_length=160)[1:]
    mb = librosa.feature.mfcc(y=b, sr=16000, n_mfcc=25, n_fft=1024, hop_length=160)[1:]
    D, wp = librosa.sequence.dtw(ma, mb, metric="euclidean")
    diff = ma[:, wp[:, 0]] - mb[:, wp[:, 1]]
    return float(np.mean(np.sqrt(2 * np.sum(diff ** 2, axis=0)))) * 10 / np.log(10) / 10  # rough dB scale

def pitch(y):
    f0, v, _ = librosa.pyin(y, fmin=55, fmax=300, sr=16000, frame_length=1024)
    f0 = f0[~np.isnan(f0)]
    return (float(np.median(f0)), float(np.std(12 * np.log2(f0 / np.median(f0))))) if len(f0) else (np.nan, np.nan)

teacher = sys.argv[1]
systems = [load(s) for s in sys.argv[2:]]
T = dict((n, (S, d)) for n, S, d in systems)[teacher]
cent = np.mean([s["emb"] for s in T[0].values()], axis=0); cent /= np.linalg.norm(cent)
print("| system | n | UTMOS | WER | spk sim → ref | spk sim → teacher | MCD vs teacher | median F0 | F0 spread (st) | words/s |")
print("|---|---|---|---|---|---|---|---|---|---|")
for name, S, d in systems:
    ids = sorted(set(S) & set(T[0]))
    g = lambda k: np.mean([S[i][k] for i in ids if k in S[i]])
    if name == teacher:  # leave-one-out, so the teacher is not compared with itself
        loo = lambda i: (lambda c: c / np.linalg.norm(c))(np.mean([T[0][j]["emb"] for j in T[0] if j != i], axis=0))
        st = np.mean([np.dot(S[i]["emb"], loo(i)) for i in ids])
    else:
        st = np.mean([np.dot(S[i]["emb"], cent) for i in ids])
    m = np.mean([mcd(audio(d, i), audio(T[1], i)) for i in ids]) if name != teacher else 0.0
    p = [pitch(audio(d, i)) for i in ids]
    print(f"| {name} | {len(ids)} | {g('utmos'):.2f} | {100*g('wer'):.1f}% | {g('spk_ref'):.3f} | {st:.3f} | {m:.2f} | "
          f"{np.nanmedian([x[0] for x in p]):.0f} Hz | {np.nanmean([x[1] for x in p]):.2f} | {g('wps'):.2f} |", flush=True)
