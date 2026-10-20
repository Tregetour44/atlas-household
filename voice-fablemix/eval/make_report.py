"""Per-line parity tables: one engine/variant from scores.jsonl against the voice-scout's own Fable-mix scores.
Usage: make_report.py scout_scores.jsonl scores.jsonl VARIANT [lines.tsv] > table.md"""
import json
import sys

scout = {}
for line in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(line)
    if r["voice"] == "kokoro-fablemix":
        scout[r["id"]] = r
rows = [json.loads(line) for line in open(sys.argv[2], encoding="utf-8")]
mine = {r["id"]: r for r in rows if r["voice"] == sys.argv[3]}
text = {}
if len(sys.argv) > 4:
    for line in open(sys.argv[4], encoding="utf-8"):
        k, v = line.rstrip("\n").split("\t", 1)
        text[k] = v


def cell(r, k, fmt):
    return "—" if r is None or r.get(k) is None else format(r[k], fmt)


print(f"| line | UTMOS scout → {sys.argv[3]} | WER | median F0 (Hz) | F0 spread (st) | Eng−US | "
      "ECAPA sim to scout's clip | Resemblyzer sim | sim → liked Fable | Whisper heard |")
print("|---|---|---|---|---|---|---|---|---|---|")
for lid in sorted(mine):
    m, s = mine[lid], scout.get(lid)
    pair = lambda k, f: f"{cell(s, k, f)} → {cell(m, k, f)}" if s else cell(m, k, f)  # noqa: E731
    print(f"| {lid} | {pair('utmos', '.2f')} | {pair('wer', '.2f')} | {pair('f0', '.0f')} | {pair('f0_st', '.1f')} | "
          f"{pair('eng_us', '+.2f')} | {cell(m, 'sim_scout', '.3f')} | {cell(m, 'rsim_scout', '.3f')} | "
          f"{pair('sim_cbfable', '.2f')} | {m['asr']} |")
