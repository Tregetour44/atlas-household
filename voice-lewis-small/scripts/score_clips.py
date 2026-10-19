"""Score audio clips against their manifest text: ASR (+second opinion), speaker similarity, UTMOS, artefacts.
usage: score_clips.py <manifest.tsv> <out.jsonl> <ref.wav> <file>... | --glob 'dir/*.flac'
Clip id = file basename up to the first '.'; already-scored files are skipped (resumable)."""
import csv, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from metrics import Evaluator, load16, wer, critical_ok, artefacts

manifest, out, ref = sys.argv[1:4]
files = sorted(glob.glob(sys.argv[5])) if sys.argv[4] == "--glob" else sys.argv[4:]
want = os.environ.get("VLS_WANT", "asr,spk,mos").split(",")
text = {r["id"]: r["text"] for r in csv.DictReader(open(manifest, encoding="utf-8"), delimiter="\t")}
done = {json.loads(l)["file"] for l in open(out)} if os.path.exists(out) else set()
ev = Evaluator(want, threads=int(os.environ.get("OMP_NUM_THREADS", "4")))
ref_e = ev.embed(load16(ref)) if "spk" in want else None
for f in files:
    if os.path.basename(f) in done:
        continue
    cid = os.path.basename(f).split(".")[0]
    y = load16(f)
    r = {"file": os.path.basename(f), "id": cid}
    if "spk" in want:
        e = ev.embed(y); r["spk_ref"] = round(float(e @ ref_e), 4); r["emb"] = [round(float(v), 5) for v in e]
    if "mos" in want:
        r["utmos"] = round(ev.utmos(y), 3)
    if "asr" in want and cid in text:
        hyp, span = ev.transcribe(y)
        r.update(asr=hyp, wer=round(wer(text[cid], hyp), 4), crit_ok=critical_ok(text[cid], hyp)[0])
        if (r["wer"] > 0.05 or not r["crit_ok"]) and not os.environ.get("VLS_NO_MEDIUM"):  # second opinion from a stronger ASR before blaming the audio
            hyp2, span2 = ev.transcribe(y, "medium")
            r.update(asr2=hyp2, wer2=round(wer(text[cid], hyp2), 4), crit_ok2=critical_ok(text[cid], hyp2)[0])
            if r["wer2"] < r["wer"]:
                span = span2
        r.update(artefacts(y, 16000, span))
        r["wps"] = round(len(text[cid].split()) / max(r["voiced_s"], 0.1), 2)
    with open(out, "a") as fo:
        fo.write(json.dumps(r) + "\n")
    print({k: v for k, v in r.items() if k != "emb"}, flush=True)
