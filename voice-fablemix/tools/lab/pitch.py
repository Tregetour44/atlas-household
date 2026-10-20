"""Pitch 'listen-proxies' for sing-song: spread (sd, st), range (p90-p10, st), end (last-third median minus the
rest, st; positive = ends high), and jump (mean |st change| between voiced 10 ms frames). Merges eval scores.
Usage: pitch.py scores.jsonl wavdir ids... -> markdown table per tag"""
import sys, json, glob, os, collections
import numpy as np, librosa
rows = {(r["voice"], r["id"]): r for r in map(json.loads, open(sys.argv[1]))}
wavdir, ids = sys.argv[2], sys.argv[3].split(",")
tags = list(dict.fromkeys(v for v, _ in rows))
def feats(f):
    y, _ = librosa.load(f, sr=16000)
    f0, _, _ = librosa.pyin(y, fmin=55, fmax=320, sr=16000, frame_length=1024, hop_length=160)
    v = ~np.isnan(f0); st = 12 * np.log2(f0[v] / np.median(f0[v]))
    k = len(st) * 2 // 3
    d = np.abs(np.diff(12 * np.log2(f0)))  # nan across unvoiced gaps
    return dict(sd=float(np.std(st)), rng=float(np.percentile(st, 90) - np.percentile(st, 10)),
                end=float(np.median(st[k:]) - np.median(st[:k])), jump=float(np.nanmean(d)))
agg = collections.defaultdict(list)
for t in tags:
    for i in ids:
        f = os.path.join(wavdir, f"{t}-{i}.wav")
        if (t, i) in rows and os.path.exists(f):
            agg[t].append({**feats(f), "utmos": rows[(t, i)]["utmos"], "eng_us": rows[(t, i)]["eng_us"],
                           "wer": rows[(t, i)]["wer"], "brit": rows[(t, i)]["accent"] in ("england", "australia"),
                           "lmd": rows[(t, i)].get("lmd_ref", 0.0), "dur": rows[(t, i)]["dur"]})
print("| variant | n | F0 spread (st) | F0 range p10–p90 (st) | ending (st) | frame jump (st) | UTMOS | Eng−US | British | WER | dur (s) |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for t, xs in agg.items():
    m = lambda k: np.mean([x[k] for x in xs])
    print(f"| {t} | {len(xs)} | {m('sd'):.2f} | {m('rng'):.2f} | {m('end'):+.2f} | {m('jump'):.3f} | {m('utmos'):.3f} | {m('eng_us'):+.3f} | {sum(x['brit'] for x in xs)}/{len(xs)} | {m('wer'):.3f} | {m('dur'):.2f} |")
