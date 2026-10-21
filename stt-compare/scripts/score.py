"""Score raw STT results: WER, command accuracy, house-word accuracy, latency; writes results tables.

Usage: python -I score.py RAW_DIR OUT_DIR
  RAW_DIR holds <config>.jsonl (clip, id, hyp, latency_s, dur) and <config>.meta.json from wyoming_bench.py / cpp_bench.py.
Command accuracy: every slot of the command (target name, on/off, number, time, scene, key question words) is heard right,
after canonicalisation (textnorm.py). It is the "would the right action be understood" proxy; a hypothesis with a wrong
device, number or time fails even if most words are right. House-word accuracy: of the clips whose reference contains a house
word (atrium, pergola, ensuite, loft, laundry, Good Night, Wind Down, kWh, ZeroCharge), the share where every such word is heard.
"""
import glob
import json
import os
import re
import sys

import jiwer
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from textnorm import canon, slot_form, slot_hit  # noqa: E402

CMDS = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "..", "testset", "commands.jsonl"))}
HOUSE = ["atrium", "pergola", "ensuite", "loft", "laundry", "goodnight", "wind down", "kwh", "zerocharge"]


def score_rows(rows):
    refs, hyps, ok, hw_ok, hw_n, lat, rtf = [], [], [], 0, 0, [], []
    per = []
    for r in rows:
        c = CMDS[r["id"]]
        ref, hyp = canon(c["text"]), canon(r.get("hyp") or "")
        refs.append(ref)
        hyps.append(hyp if hyp else "<empty>")
        hs = slot_form(r.get("hyp") or "")
        good = all(slot_hit(s, hs) for s in c["slots"])
        ok.append(good)
        words = [w for w in HOUSE if re.search(r"\b" + w + r"\b", ref)]
        if words:
            hw_n += 1
            hw_ok += all(re.search(r"\b" + w + r"\b", hyp) for w in words)
        lat.append(r["latency_s"])
        speech = max(r["dur"] - 0.6, 0.3)  # clips carry 0.25 s lead + 0.35 s tail silence
        rtf.append(r["latency_s"] / r["dur"])
        per.append({"clip": r["clip"], "ok": good, "ref": ref, "hyp": hyp})
    wer = jiwer.wer(refs, hyps)
    return {"n": len(rows), "wer": wer, "cmd_acc": float(np.mean(ok)), "house_word_acc": hw_ok / hw_n if hw_n else float("nan"),
            "lat_p50": float(np.median(lat)), "lat_p95": float(np.percentile(lat, 95)), "rtf": float(np.mean(rtf))}, per


def main(raw, out, min_rows=600):
    os.makedirs(out, exist_ok=True)
    table = {}
    for f in sorted(glob.glob(os.path.join(raw, "*.jsonl"))):
        name = os.path.basename(f)[:-6]
        rows = [json.loads(l) for l in open(f)]
        if len(rows) < min_rows or not os.path.exists(f[:-6] + ".meta.json"):
            continue
        meta = json.load(open(f[:-6] + ".meta.json")) if os.path.exists(f[:-6] + ".meta.json") else {}
        res = {}
        for label, sel in [("all", lambda r: True), ("clean", lambda r: r["clip"].startswith("clean/")),
                           ("noise", lambda r: r["clip"].startswith("noise/")), ("far", lambda r: r["clip"].startswith("far/")),
                           ("AU", lambda r: "-au_" in r["clip"]), ("GB", lambda r: "-gb_" in r["clip"]),
                           ("owner", lambda r: CMDS[r["id"]]["cat"] == "owner"),
                           ("2-5s", lambda r: 2.0 + 0.6 <= r["dur"] <= 5.0 + 0.6)]:
            sub = [r for r in rows if sel(r)]
            if not sub:
                continue
            res[label], per = score_rows(sub)
            if label == "all":
                with open(os.path.join(out, f"errors-{name}.tsv"), "w") as e:
                    e.write("clip\tref\thyp\n")
                    for p in per:
                        if not p["ok"]:
                            e.write(f"{p['clip']}\t{p['ref']}\t{p['hyp']}\n")
        res["meta"] = meta
        table[name] = res
    json.dump(table, open(os.path.join(out, "summary.json"), "w"), indent=1)
    pct = lambda x: "-" if x is None or x != x else f"{100 * x:.1f}%"
    g = lambda r, label, key: r.get(label, {}).get(key, float("nan"))
    lines = ["| config | WER all | WER clean | WER noise | WER far | cmd acc all | cmd clean | cmd noise | cmd far | cmd AU | cmd GB | house words | "
             "latency p50 (2-5 s) | p95 | peak RAM |", "|" + "---|" * 15]
    for name, r in sorted(table.items(), key=lambda kv: -kv[1]["all"]["cmd_acc"]):
        lines.append(f"| {name} | {pct(g(r, 'all', 'wer'))} | {pct(g(r, 'clean', 'wer'))} | {pct(g(r, 'noise', 'wer'))} | {pct(g(r, 'far', 'wer'))} | "
                     f"{pct(g(r, 'all', 'cmd_acc'))} | {pct(g(r, 'clean', 'cmd_acc'))} | {pct(g(r, 'noise', 'cmd_acc'))} | {pct(g(r, 'far', 'cmd_acc'))} | "
                     f"{pct(g(r, 'AU', 'cmd_acc'))} | {pct(g(r, 'GB', 'cmd_acc'))} | {pct(g(r, 'all', 'house_word_acc'))} | "
                     f"{g(r, '2-5s', 'lat_p50'):.2f} s | {g(r, '2-5s', 'lat_p95'):.2f} s | {r['meta'].get('peak_rss_mb', '?')} MB |")
    open(os.path.join(out, "accuracy_speed.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[sys.argv.index("--min-rows") + 1]) if "--min-rows" in sys.argv else 600)
