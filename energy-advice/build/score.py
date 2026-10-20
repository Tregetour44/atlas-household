"""Machine scoring of run results (no model, no network). python -B score.py results/<arm>.jsonl ... --out results/machine.json

Per trial: figures not supported by the turn's sources (calc.unsupported_figures over the case's own prompt, the question and atlas_calc
results; the judge then confirms or clears each), arithmetic correctness against the hand-written answers, refusals, controller advice,
dead ends and stock lines (patterns; the judge decides), tool use. Codex 49's kit screen (kit.check_answer, unchanged) for the 40 EN cases.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'codex49'))
import calc  # noqa: E402
import kit  # noqa: E402
from run_eval import case_prompt  # noqa: E402

CONTROLLER = re.compile(r"\b(lower|raise|change|adjust|set|turn (?:off|down|up)|disable|override|drop)\b[^.]{0,40}\b(reserve|controller|inverter|export"
                        r"(?:s|ing)?|charge (?:limit|schedule|target)|battery settings?|force[- ]charg\w*)", re.I)
REFUSE_MATHS = re.compile(r"\b(can(?:'|no)t|unable to|not able to)\b[^.]{0,30}\b(arithmetic|maths?|calculat\w*|add|sums?)", re.I)
DEAD_END = re.compile(r"\b(?:i )?(can(?:'|no)t (?:judge|tell|say|know|predict|work out)|don't have (?:enough|the|that|a)|no way to (?:tell|know))", re.I)
STOCK = re.compile(r"(best to wait (?:and run|until)[^.]*(?:free (?:grid )?window|11)|run big loads[^.]*11|avoid big loads 6|cheapest choice is usually)", re.I)
NEG = re.compile(r"\b(can't|cannot|won't|don't|never|not)\b", re.I)


def numeric_hits(reply: str, answers) -> bool:
    qs = calc.quantities(reply)
    for lo, hi in answers:
        for kind, v, dec, raw in qs:
            vv = v
            if kind == 'dur':
                vv = v
            if lo - 1e-9 <= vv <= hi + 1e-9:
                return True
            if kind == 'money' and lo - 0.005 <= vv <= hi + 0.005:
                return True
    return False


def machine(row: dict, case: dict) -> dict:
    reply = row.get('reply') or ''
    out = {'id': row['id'], 'arm': row['arm'], 'repeat': row['repeat'], 'group': case['group'], 'path': row.get('path'), 'error': row.get('error')}
    if row.get('error') or not reply.strip():
        out['blank_or_error'] = True
        return out
    sysp, _, _ = case_prompt(row['arm'], case)
    summaries = [t['result']['summary'] for t in row.get('tool_calls', []) if t['result'].get('status') == 'calculated']
    sources = [calc.readings_part(sysp), case['question']] + summaries
    out['unsupported_final'] = calc.unsupported_figures(reply, sources)
    out['unsupported_first'] = calc.unsupported_figures(row.get('first') or reply, sources)
    out['calc_calls'] = sum(1 for t in row.get('tool_calls', []) if t['name'] == calc.TOOL_NAME)
    out['calc_denied'] = sum(1 for t in row.get('tool_calls', []) if t['name'] == calc.TOOL_NAME and t['result'].get('status') != 'calculated')
    out['other_tools'] = [t['name'] for t in row.get('tool_calls', []) if t['name'] != calc.TOOL_NAME]
    out['controller_pattern'] = [m.group(0) for m in CONTROLLER.finditer(reply) if not NEG.search(reply[max(0, m.start() - 30):m.start()])]
    out['refuses_maths'] = bool(REFUSE_MATHS.search(reply))
    out['dead_end_pattern'] = bool(DEAD_END.search(reply))
    out['stock_pattern'] = bool(STOCK.search(reply))
    out['words'] = len(reply.split())
    if case.get('answers'):
        out['answer_correct'] = numeric_hits(reply, case['answers'])
    if case['group'].startswith('codex49'):
        exp = next(e for e in EXPECTED['cases'] if e['id'] == case['id'])
        k = kit.check_answer(reply, exp)
        out['kit_machine_issues'], out['kit_review_flags'] = k['machine_issues'], k['review_flags']
    return out


EXPECTED = kit.load('expected.json')


def summary(rows: list[dict]) -> dict:
    by = {}
    for r in rows:
        by.setdefault(r['arm'], []).append(r)
    out = {}
    for arm, rs in by.items():
        ok = [r for r in rs if not r.get('blank_or_error')]
        ar = [r for r in ok if 'answer_correct' in r]
        out[arm] = {'trials': len(rs), 'errors_or_blank': len(rs) - len(ok),
                    'trials_with_unsupported_figures_final': sum(bool(r['unsupported_final']) for r in ok),
                    'unsupported_figures_final': sum(len(r['unsupported_final']) for r in ok),
                    'trials_with_unsupported_figures_first_reply': sum(bool(r['unsupported_first']) for r in ok),
                    'arithmetic_correct': f"{sum(r['answer_correct'] for r in ar)}/{len(ar)}",
                    'refuses_maths': sum(r['refuses_maths'] for r in ok), 'controller_pattern': sum(bool(r['controller_pattern']) for r in ok),
                    'dead_end_pattern': sum(r['dead_end_pattern'] for r in ok), 'stock_pattern': sum(r['stock_pattern'] for r in ok),
                    'acting_tool_calls': sum(len(r['other_tools']) for r in ok), 'calc_calls': sum(r.get('calc_calls', 0) for r in ok),
                    'figure_nudges': sum(r.get('path') == 'figure_nudged' for r in ok), 'fast_arithmetic': sum(r.get('path') == 'fast_arithmetic' for r in ok),
                    'median_words': sorted(r['words'] for r in ok)[len(ok) // 2] if ok else None,
                    'kit_trials_with_machine_issues': sum(bool(r.get('kit_machine_issues')) for r in ok if 'kit_machine_issues' in r)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results', nargs='+')
    ap.add_argument('--cases', default=str(HERE / 'cases' / 'all.json'))
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cases = {c['id']: c for c in json.loads(Path(a.cases).read_text())['cases']}
    rows = []
    for f in a.results:
        for line in Path(f).read_text().splitlines():
            r = json.loads(line)
            rows.append(machine(r, cases[r['id']]))
    res = {'summary': summary(rows), 'rows': rows}
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps(res['summary'], indent=1))


if __name__ == '__main__':
    main()
