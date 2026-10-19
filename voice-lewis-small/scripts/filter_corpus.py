"""Accept/reject teacher clips from score_clips.py output using configs/filter.json thresholds.
For each clip id the first passing attempt (attempt 0, then retries) is kept.
Writes: <out>/accepted.tsv (id, file, text), <out>/rejects.jsonl (every failing attempt + reasons), <out>/retry_ids.txt.
usage: filter_corpus.py <manifest.tsv> <scores.jsonl> <filter.json> <out_dir>"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import wer, critical_ok
manifest, scores, cfgp, out = sys.argv[1:5]
cfg = json.load(open(cfgp))
rows = {r["id"]: r for r in csv.DictReader(open(manifest, encoding="utf-8"), delimiter="\t")}
S = [json.loads(l) for l in open(scores)]
for s in S:  # re-derive WER / critical words from the stored transcripts with the current normaliser
    if s.get("id") in rows and "asr" in s:
        ref = rows[s["id"]]["text"]
        s["wer"], s["crit_ok"] = wer(ref, s["asr"]), critical_ok(ref, s["asr"])[0]
        if "asr2" in s:
            s["wer2"], s["crit_ok2"] = wer(ref, s["asr2"]), critical_ok(ref, s["asr2"])[0]


def reasons(s):
    r = []
    a1 = s.get("wer", 1) <= cfg["wer_max"] and s.get("crit_ok", False)
    a2 = s.get("wer2", 1) <= cfg["wer_max"] and s.get("crit_ok2", False)
    if not (a1 or a2):
        r.append(f"asr wer={s.get('wer')}/{s.get('wer2')} crit={s.get('crit_ok')}/{s.get('crit_ok2')} hyp={s.get('asr2', s.get('asr'))!r}")
    cut = cfg["spk_ref_min"] if s["dur"] >= cfg["spk_short_dur_s"] else cfg["spk_ref_min_short"]
    if s["spk_ref"] < cut:
        r.append(f"speaker sim {s['spk_ref']:.3f} < {cut} (dur {s['dur']}s)")
    if s["utmos"] < cfg["utmos_min"]:
        r.append(f"utmos {s['utmos']:.2f} < {cfg['utmos_min']}")
    if s["clip_frac"] > cfg["clip_frac_max"]:
        r.append(f"clipping {s['clip_frac']:.4f}")
    if s["max_pause"] > cfg["max_pause_s"]:
        r.append(f"internal pause {s['max_pause']}s")
    if s["extra_after"] > cfg["extra_sound_s"] or s["extra_before"] > cfg["extra_sound_s"]:
        r.append(f"sound outside words before={s['extra_before']}s after={s['extra_after']}s")
    if not cfg["wps_min"] <= s["wps"] <= cfg["wps_max"]:
        r.append(f"speaking rate {s['wps']} words/s")
    if s["dur"] > cfg["max_dur_s"]:
        r.append(f"too long {s['dur']}s")
    return r


os.makedirs(out, exist_ok=True)
best, rej, tried = {}, [], {}
for s in sorted(S, key=lambda s: s["file"]):
    if s["id"] not in rows or rows[s["id"]]["split"] != "train":
        continue
    tried.setdefault(s["id"], 0); tried[s["id"]] += 1
    rs = reasons(s)
    if rs:
        rej.append({"id": s["id"], "file": s["file"], "text": rows[s["id"]]["text"], "reasons": rs})
    elif s["id"] not in best:
        best[s["id"]] = s
with open(os.path.join(out, "accepted.tsv"), "w", encoding="utf-8") as f:
    f.write("id\tfile\tdur\tspk_ref\tutmos\ttext\n")
    for cid, s in sorted(best.items()):
        f.write(f"{cid}\t{s['file']}\t{s['dur']}\t{s['spk_ref']}\t{s['utmos']}\t{rows[cid]['text']}\n")
with open(os.path.join(out, "rejects.jsonl"), "w", encoding="utf-8") as f:
    for r in rej:
        f.write(json.dumps(r) + "\n")
retry = sorted(c for c in tried if c not in best)
open(os.path.join(out, "retry_ids.txt"), "w").write("\n".join(retry) + ("\n" if retry else ""))
mins = sum(s["dur"] for s in best.values()) / 60
print(f"scored ids {len(tried)} attempts {len(S)} accepted {len(best)} ({mins:.1f} min) rejected attempts {len(rej)} ids needing retry {len(retry)}")
