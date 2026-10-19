"""Second-opinion pass (Whisper medium.en) for clips that failed the small.en check and were scored with VLS_NO_MEDIUM
(memory was too tight to load medium.en next to the teacher). Rewrites the scores jsonl in place.
usage: recheck_asr.py <manifest.tsv> <scores.jsonl> <audio_dir>"""
import csv, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import Evaluator, load16, wer, critical_ok, artefacts

manifest, scores, adir = sys.argv[1:4]
text = {r["id"]: r["text"] for r in csv.DictReader(open(manifest, encoding="utf-8"), delimiter="\t")}
S = [json.loads(l) for l in open(scores)]
ev = Evaluator(("asr",), threads=int(os.environ.get("OMP_NUM_THREADS", "4")))
n = 0
for r in S:
    t = text.get(r["id"])
    if t is None or "asr2" in r or (wer(t, r["asr"]) <= 0.05 and critical_ok(t, r["asr"])[0]):
        continue
    y = load16(os.path.join(adir, r["file"]))
    hyp2, span2 = ev.transcribe(y, "medium")
    r.update(asr2=hyp2, wer2=round(wer(t, hyp2), 4), crit_ok2=critical_ok(t, hyp2)[0])
    if r["wer2"] < r["wer"]:
        r.update(artefacts(y, 16000, span2))
        r["wps"] = round(len(t.split()) / max(r["voiced_s"], 0.1), 2)
    n += 1
    print(r["id"], r["wer"], r["wer2"], hyp2, flush=True)
with open(scores + ".tmp", "w") as f:
    f.writelines(json.dumps(r) + "\n" for r in S)
os.replace(scores + ".tmp", scores)
print("rechecked", n)
