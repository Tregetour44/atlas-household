"""DRAFT: House AI and Energy review. Seal files within this directory only."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent
NOTICE='DRAFT: House AI and Energy review'
def main():
    v=json.loads((ROOT/'validation.json').read_text(encoding='utf-8'))
    if not v['passed']: raise ValueError('Offline checks failed')
    scenarios=json.loads((ROOT/'scenarios.json').read_text(encoding='utf-8'))['cases']
    lines=['# '+NOTICE,'',
      'Atlas should recommend a time because the particular load fits the available solar, battery and expected household demand—not just because the clock is in a tariff window. This draft separates battery energy from short import spikes, treats comfort and deadlines as real needs, and allows “little difference” only when both choices are supported. It supplies proposed read-only fact cards, brief prompt guidance, 40 synthetic scenarios compatible with run42’s scorer and eight sample answers. Everything is for House AI and Energy review; no live system, Git state or controller was changed, and no household service or model was contacted. Actual advice improvement, live card availability, forecast calibration and owner preference are NO DATA.','',
      '## Design in brief','',
      '- HA supplies the maths: whole-cycle timing, SOC trend, separate reserve/export margins, remaining solar, representative evening/overnight demand, programme profiles, each credit hour and uncertainty ranges.',
      '- Compare now, a feasible later interval and the next free window. Paid tariff is not proof of paid import. Tomorrow’s solar cannot cover tonight. Free grid does not mean unlimited simultaneous power.',
      '- Keep credit status separate from risk: each hour must stay strictly below 0.030 kWh; no netting or averaging. A completed miss cannot be repaired. HA indicates; the bill decides.',
      '- Confidence belongs to each claim. Give a supported recommendation, a specific missing-data answer or an evidence-backed “little difference”; never a battery-runtime or credit promise.',
      '- Atlas gives the advice and one short reason, with at most one apt question. No controller changes, lectures or routine offers.',
      f'- Validation: {v["tests_run"]} offline formula, fixture and scorer checks passed. These are not model or production HA tests. 32 development cases and 8 visible holdouts; 27 original run42 cases retained as separate regressions.','',
      '## Eight sample answers','',
      'These are authored answers to synthetic situations, not live readings or measured Atlas responses. Full fact snapshots are in SAMPLES.md and SCENARIOS.md.','']
    for n in [2,1,3,8,4,13,12,17]:
        c=scenarios[n-1]
        lines += [f'**{c["id"]} — {c["question"]}**', '',c['expected_advice'],'']
    lines += ['## Files and SHA-256','',
      'Start with this summary; DESIGN.md and FACT-CARDS.md explain the design, PROMPT.md supplies the short guidance, and EVALUATION.md explains the scorer contract and limits. All output files are listed below. Ordinary hashes cover exact whole-file bytes except SUMMARY.md’s explicitly canonical self-hash. Source provenance hashes are in source-index.json.','',
      '| File | Bytes | SHA-256 |','|---|---:|---|']
    files=sorted(p for p in ROOT.iterdir() if p.is_file() and p.name!='SUMMARY.md')
    for p in files:
        b=p.read_bytes(); lines.append(f'| [{p.name}]({p.name}) | {len(b)} | `{hashlib.sha256(b).hexdigest()}` |')
    lines += ['| [SUMMARY.md](SUMMARY.md) | canonical self-hash | `'+'0'*64+'` |','',
      'SUMMARY.md self-hash convention: UTF-8, LF newlines and final newline retained; replace only the 64 hexadecimal characters in its own table row with 64 zeros before hashing. An ordinary whole-file self-hash cannot practically be embedded in the same file; the final chat supplies that whole-file hash separately. Re-run seal.py after changing any output.','']
    text='\n'.join(lines); own=hashlib.sha256(text.encode()).hexdigest()
    text=text.replace('`'+'0'*64+'`','`'+own+'`')
    (ROOT/'SUMMARY.md').write_bytes(text.encode())
    canonical=re.sub(r'(\| \[SUMMARY\.md\]\(SUMMARY\.md\) \| canonical self-hash \| `)[0-9a-f]{64}',lambda m:m[1]+'0'*64,text)
    assert hashlib.sha256(canonical.encode()).hexdigest()==own
    for p in files: assert hashlib.sha256(p.read_bytes()).hexdigest() in text
    print(f'{len(files)+1} output files sealed; all manifest entries verified.')
    print('SUMMARY.md whole-file SHA-256: '+hashlib.sha256(text.encode()).hexdigest())

if __name__=='__main__': main()
