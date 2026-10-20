"""Summarise eval jsonl: per voice means (optionally per id-prefix group). Usage: summ.py scores.jsonl [prefixes] [voices]"""
import sys, json, collections
rows = [json.loads(l) for l in open(sys.argv[1])]
groups = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else [""]
voices = sys.argv[3].split(",") if len(sys.argv) > 3 else list(dict.fromkeys(r["voice"] for r in rows))
K = ["utmos", "f0", "f0_st", "wer", "eng_us", "sim_cbfable", "sim_scout", "rsim_scout", "lmd_ref"]
print("| voice | lines | " + " | ".join(K) + " | British/US |")
print("|---|---|" + "---|" * (len(K) + 1))
for g in groups:
    for v in voices:
        rs = [r for r in rows if r["voice"] == v and r["id"].startswith(g)]
        if not rs:
            continue
        cells = []
        for k in K:
            xs = [r[k] for r in rs if r.get(k) is not None]
            cells.append(f"{sum(xs) / len(xs):.3f}" if xs else "—")
        brit = sum(r["accent"] in ("england", "australia") for r in rs); us = sum(r["accent"] == "us" for r in rs)
        print(f"| {v} | {g or 'all'} ({len(rs)}) | " + " | ".join(cells) + f" | {brit}/{us} |")
