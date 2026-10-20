"""Per-line parity tables: one engine/variant from scores.jsonl against the voice-scout's own Fable-mix scores.
Usage: make_report.py scout_scores.jsonl scores.jsonl VARIANT [centroid_sims.jsonl] > table.md
centroid_sims.jsonl (tools/lab/simcent.py) adds ECAPA / Resemblyzer similarity to the centroid of the scout's 18
Fable-mix clips, which covers the lines the scout never rendered."""
import json
import sys


def load(path, voice):
    with open(path, encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f) if r["voice"] == voice}


scout = load(sys.argv[1], "kokoro-fablemix")
mine = load(sys.argv[2], sys.argv[3])
cent = load(sys.argv[4], sys.argv[3]) if len(sys.argv) > 4 else {}


def cell(r, k, fmt):
    return "—" if r is None or r.get(k) is None else format(r[k], fmt)


def pair(s, m, k, fmt):
    return f"{cell(s, k, fmt)} → {cell(m, k, fmt)}" if s else cell(m, k, fmt)


print(f"| line | UTMOS scout → {sys.argv[3]} | WER | median F0 (Hz) | F0 spread (st) | Eng−US | "
      "ECAPA sim to scout's clip | Resemblyzer sim | ECAPA / Resemblyzer sim to scout centroid | sim → liked Fable | "
      "Whisper heard |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for lid in sorted(mine):
    m, s = mine[lid], scout.get(lid)
    print(f"| {lid} | {pair(s, m, 'utmos', '.2f')} | {pair(s, m, 'wer', '.2f')} | {pair(s, m, 'f0', '.0f')} | "
          f"{pair(s, m, 'f0_st', '.1f')} | {pair(s, m, 'eng_us', '+.2f')} | {cell(m, 'sim_scout', '.3f')} | {cell(m, 'rsim_scout', '.3f')} | "
          f"{cell(cent.get(lid), 'ecapa_scoutcent', '.3f')} / {cell(cent.get(lid), 'resem_scoutcent', '.3f')} | "
          f"{pair(s, m, 'sim_cbfable', '.2f')} | {m['asr']} |")
