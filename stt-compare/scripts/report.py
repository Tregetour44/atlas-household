"""Build the results tables (results/*.md, results/summary.json) from raw runs, on matched clip sets.

  core   80 commands x (AU clean, GB clean, room noise) = 240 clips: every engine (the budget-trimmed main comparison)
  full   all 604 clips incl. far-field: the engines that ran on everything
  au0    151 clean clips by the AU speakers WITHOUT the vowel shift (accent control)
  pc60   the 60-clip PC-bench subset: whisper.cpp vs the same clips from the others
  s2p    Speech-to-Phrase acceptance / false accepts, and "S2P in front, fallback to the main engine" simulated per clip
Usage: python -I report.py RAW_DIR OUT_DIR
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from score import CMDS, score_rows  # noqa: E402
from textnorm import slot_form, slot_hit  # noqa: E402

AUD = os.path.join(HERE, "..", "testset", "audio")
SETS = {k: {json.loads(l)["clip"] for l in open(os.path.join(AUD, f))} for k, f in
        [("core", "manifest_core.jsonl"), ("full", "manifest.jsonl"), ("au0", "manifest_au0.jsonl")]}
SETS["pc60"] = {json.loads(l)["clip"] for l in open(os.path.join(HERE, "..", "bench", "manifest_pc.jsonl"))}
# Per-thread speed of a Ryzen 7 9700X vs this sandbox's 2.1 GHz Xeon vCPU: 1.4-1.9x (PassMark single-thread 4,643 vs 2,469-3,258);
# the PC also has 8 cores/16 threads vs 4 vCPU here. Latency estimates for the PC divide sandbox times by 1.9 (low) .. 3 (high).
PC_LO, PC_HI = 1.9, 3.0
pct = lambda x: "-" if x is None or x != x else f"{100 * x:.1f}%"


def load(raw):
    runs = {}
    for f in sorted(glob.glob(os.path.join(raw, "*.jsonl"))):
        name = os.path.basename(f)[:-6]
        meta = f[:-6] + ".meta.json"
        if not os.path.exists(meta):
            continue
        rows = [json.loads(l) for l in open(f)]
        base, _, variant = name.partition("@")
        runs.setdefault(base, {})[variant or "main"] = (rows, json.load(open(meta)))
    return runs


def ok(r):
    return all(slot_hit(s, slot_form(r.get("hyp") or "")) for s in CMDS[r["id"]]["slots"])


def subset(rows, clips, pred=lambda r: True):
    return [r for r in rows if r["clip"] in clips and pred(r)]


def table_core(runs):
    head = ("| engine (CPU, int8 unless noted) | WER clean | WER noise | cmd clean AU | cmd clean GB | cmd noise | **cmd all** | house words | "
            "owner phrasings | latency p50 / p95 here | est. on 9700X | peak RAM |")
    lines = [head, "|" + "---|" * 12]
    rows_out = {}
    for name, v in runs.items():
        rows, meta = v.get("main", (None, None))
        if rows is None:
            continue
        core = subset(rows, SETS["core"])
        if len(core) < 0.95 * len(SETS["core"]):
            continue
        s = {k: score_rows(subset(core, SETS["core"], p))[0] for k, p in [
            ("all", lambda r: True), ("clean", lambda r: r["clip"].startswith("clean/")), ("noise", lambda r: r["clip"].startswith("noise/")),
            ("cleanAU", lambda r: r["clip"].startswith("clean/") and "-au_" in r["clip"]),
            ("cleanGB", lambda r: r["clip"].startswith("clean/") and "-gb_" in r["clip"]),
            ("owner", lambda r: CMDS[r["id"]]["cat"] == "owner"), ("2-5s", lambda r: 2.6 <= r["dur"] <= 5.6)]}
        rows_out[name] = s
        lat = s["2-5s"]
        est = f"{lat['lat_p50'] / PC_HI:.2f}-{lat['lat_p50'] / PC_LO:.2f} s"
        lines.append(f"| {name} | {pct(s['clean']['wer'])} | {pct(s['noise']['wer'])} | {pct(s['cleanAU']['cmd_acc'])} | "
                     f"{pct(s['cleanGB']['cmd_acc'])} | {pct(s['noise']['cmd_acc'])} | **{pct(s['all']['cmd_acc'])}** | "
                     f"{pct(s['all']['house_word_acc'])} | {pct(s['owner']['cmd_acc'])} | {lat['lat_p50']:.2f} / {lat['lat_p95']:.2f} s | {est} | "
                     f"{meta.get('peak_rss_mb', '?')} MB |")
    order = sorted(lines[2:], key=lambda l: -float(l.split("**")[1].rstrip("%")) if "**" in l else 0)
    return "\n".join(lines[:2] + order), rows_out


def table_full(runs):
    lines = ["| engine | WER clean | WER noise | WER far-field | cmd clean | cmd noise | cmd far-field | cmd all (604 clips) |", "|" + "---|" * 8]
    for name, v in runs.items():
        rows, _ = v.get("main", (None, None))
        if rows is None or len(subset(rows, SETS["full"])) < 600:
            continue
        s = {k: score_rows([r for r in rows if r["clip"].startswith(k + "/")])[0] for k in ("clean", "noise", "far")}
        a = score_rows(rows)[0]
        lines.append(f"| {name} | {pct(s['clean']['wer'])} | {pct(s['noise']['wer'])} | {pct(s['far']['wer'])} | {pct(s['clean']['cmd_acc'])} | "
                     f"{pct(s['noise']['cmd_acc'])} | {pct(s['far']['cmd_acc'])} | {pct(a['cmd_acc'])} |")
    return "\n".join(lines)


def table_au0(runs):
    lines = ["| engine | cmd acc: AU voices, vowel-shifted | cmd acc: same AU voices, no shift | cmd acc: GB voices | WER shifted / unshifted |",
             "|---|---|---|---|---|"]
    for name, v in runs.items():
        if "au0" not in v or "main" not in v or not v["au0"][0]:
            continue
        main = v["main"][0]
        au = [r for r in main if r["clip"].startswith("clean/") and "-au_" in r["clip"]]
        gb = [r for r in main if r["clip"].startswith("clean/") and "-gb_" in r["clip"]]
        ids = {r["id"] for r in au}
        a0 = [r for r in v["au0"][0] if r["id"] in ids]
        s, s0, g = score_rows(au)[0], score_rows(a0)[0], score_rows(gb)[0]
        lines.append(f"| {name} ({len(au)} clips) | {pct(s['cmd_acc'])} | {pct(s0['cmd_acc'])} | {pct(g['cmd_acc'])} | "
                     f"{pct(s['wer'])} / {pct(s0['wer'])} |")
    return "\n".join(lines)


def table_prompt(core):
    lines = ["| engine | cmd all: no prompt -> house prompt | house words | WER clean | WER noise |", "|---|---|---|---|---|"]
    for name in sorted(core):
        if name + "+prompt" in core:
            a, b = core[name], core[name + "+prompt"]
            lines.append(f"| {name} | {pct(a['all']['cmd_acc'])} -> {pct(b['all']['cmd_acc'])} | {pct(a['all']['house_word_acc'])} -> "
                         f"{pct(b['all']['house_word_acc'])} | {pct(a['clean']['wer'])} -> {pct(b['clean']['wer'])} | "
                         f"{pct(a['noise']['wer'])} -> {pct(b['noise']['wer'])} |")
    return "\n".join(lines)


def table_pc60(runs):
    lines = ["| engine (sandbox CPU, 4 threads) | cmd acc (60 clips) | WER | latency p50 / p95 | peak RAM |", "|---|---|---|---|---|"]
    for name, v in runs.items():
        rows, meta = v.get("main", (None, None))
        if rows is None:
            continue
        sub = subset(rows, SETS["pc60"])
        if len(sub) < 60:
            continue
        s = score_rows(sub)[0]
        lines.append(f"| {name} | {pct(s['cmd_acc'])} | {pct(s['wer'])} | {s['lat_p50']:.2f} / {s['lat_p95']:.2f} s | {meta.get('peak_rss_mb', '?')} MB |")
    return "\n".join(lines)


def table_s2p(runs, fallbacks=("parakeet-v2-int8", "qwen3asr-0.6b-int4+prompt", "fw-large-v3-turbo-int8")):
    lines = ["| grammar | accepted | accepted & right | **accepted & wrong (wrong action)** | rejected -> fallback | S2P latency p50 here | "
             "S2P alone cmd acc | front + fallback: cmd acc (fallback engine alone) |", "|" + "---|" * 8]
    out = {}
    for name in ("speech-to-phrase-default", "speech-to-phrase-tuned"):
        if name not in runs:
            continue
        rows = subset(runs[name]["main"][0], SETS["core"])
        acc = [r for r in rows if r["hyp"]]
        right = [r for r in acc if ok(r)]
        combo = []
        for fb in fallbacks:
            if fb not in runs:
                continue
            fbr = {r["clip"]: r for r in runs[fb]["main"][0]}
            both = [(r if r["hyp"] else fbr[r["clip"]]) for r in rows if r["clip"] in fbr]
            alone = [fbr[r["clip"]] for r in rows if r["clip"] in fbr]
            combo.append(f"{fb}: {pct(np.mean([ok(x) for x in both]))} ({pct(np.mean([ok(x) for x in alone]))})")
        lat = [r["latency_s"] for r in rows]
        out[name] = {"n": len(rows), "accepted": len(acc), "right": len(right)}
        lines.append(f"| {name.split('-')[-1]} ({runs[name]['main'][1].get('templates')} templates) | {pct(len(acc) / len(rows))} | "
                     f"{pct(len(right) / len(rows))} | **{pct((len(acc) - len(right)) / len(rows))}** | {pct(1 - len(acc) / len(rows))} | "
                     f"{np.median(lat):.2f} s | {pct(len(right) / len(rows))} | {'; '.join(combo)} |")
    return "\n".join(lines), out


def main(raw, out):
    runs = load(raw)
    os.makedirs(out, exist_ok=True)
    core_md, core = table_core(runs)
    s2p_md, s2p = table_s2p(runs)
    parts = [("Core comparison: 80 commands x (AU clean, GB clean, room noise) = 240 clips", core_md),
             ("All 604 clips incl. far-field (engines that ran on everything)", table_full(runs)),
             ("Vocabulary prompting (house names as initial prompt / Qwen3-ASR context)", table_prompt(core)),
             ("Accent control: AU speakers with and without the approximate vowel shift (clean)", table_au0(runs)),
             ("whisper.cpp vs the others on the 60-clip PC subset (sandbox CPU)", table_pc60(runs)),
             ("Speech-to-Phrase v2.2 on the core 240 clips", s2p_md)]
    md = "\n\n".join(f"### {t}\n\n{b}" for t, b in parts) + "\n"
    open(os.path.join(out, "tables.md"), "w").write(md)
    json.dump({"core": core, "s2p": s2p, "meta": {n: {k: m for k, (_, m) in v.items()} for n, v in runs.items()}},
              open(os.path.join(out, "summary.json"), "w"), indent=1, default=float)
    print(md)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
