"""DRAFT: House AI and Energy review. Read explicit non-secret source files only.
Write provenance and a scorer copy solely to run49. No network or subprocesses.
"""
from pathlib import Path
import ast
import hashlib
import json

ROOT=Path(__file__).resolve().parent
BASE=Path('<projects-root>')   # local path removed for export; this script only runs on the house PC
NOTICE='DRAFT: House AI and Energy review'
SOURCES=[
 'PCSteward/Directives/20261018-2225-atlas-energy-advice-reasoned.md',
 'HomeAssistant/Scripts/HouseAiAssist/prompt-template.jinja',
 'HomeAssistant/Scripts/HouseAiAssist/fact-cards.mjs',
 'HomeAssistant/Scripts/HouseAiAssist/energy-history.jinja.txt',
 'HomeAssistant/Scripts/HouseAiAssist/energy-input-20261017-1645.md',
 'HouseAI/Smarts/FACT-CARDS-SPEC.md',
 'HouseAI/Smarts/RESULTS-T2-CARDS-20261018.md',
 'HouseAI/TestSuite/README.md', 'HouseAI/TestSuite/helper-contracts.md',
 'HouseAI/TestSuite/ADOPTED.md','HouseAI/TestSuite/scenarios.md',
 'Codex-Inbox/2026-10-18-run42/README.md','Codex-Inbox/2026-10-18-run42/FACTS-CONTRACT.md',
 'Codex-Inbox/2026-10-18-run42/JUDGE.md','Codex-Inbox/2026-10-18-run42/kit.py',
 'Codex-Inbox/2026-10-18-run42/benchmark.json','Codex-Inbox/2026-10-18-run42/expected.json',
 'Codex-Inbox/2026-10-18-run42/seal_summary.py',
 'EnergyCommandCentre/CURRENT-STATE.md','EnergyCommandCentre/README.md',
 'PCSteward/Reviews/Energy-Economics-2026-10.md']
SOURCES += ['EnergyCommandCentre/Rules/'+n+'.md' for n in (
 'authority-and-never-lists','candidate-design','controls-faults-restarts','incidents',
 'live-change-method','paths-and-records','protected-time','tool-use')]

def save(name,obj):
    p=ROOT/name
    if p.parent!=ROOT: raise ValueError('Output outside run49')
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='')

def main():
    rows=[]
    for rel in SOURCES:
        p=BASE/rel
        raw=p.read_bytes()
        rows.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
          status='Read-only local record; not a live service verification'))
    save('source-index.json',dict(notice=NOTICE,sources=rows))
    old=(BASE/'Codex-Inbox/2026-10-18-run42/kit.py').read_text(encoding='utf-8-sig')
    new=old.replace('DRAFT: House AI reviews',NOTICE).replace('Files must stay in the run42 directory','Files must stay in the run49 directory')
    (ROOT/'kit.py').write_text(new,encoding='utf-8',newline='')
    names=['score','check_answer','compare_reports','digest','number','canonical_unit']
    def functions(src): return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(src).body if isinstance(n,ast.FunctionDef)}
    a,b=functions(old),functions(new)
    same={n:a[n]==b[n] for n in names}
    assert all(same.values())
    save('compatibility.json',dict(notice=NOTICE,source='Codex-Inbox/2026-10-18-run42/kit.py',unchanged_functions=same,
      changes=['Draft notice','Directory error wording'],generate_for_run49='Use build.py; original generator stays frozen to 120 cases'))
    original=json.loads((BASE/'Codex-Inbox/2026-10-18-run42/benchmark.json').read_text(encoding='utf-8-sig'))
    ids={f'AS{i:03}' for i in [1,2,3,4,5,6,8,9,10,13,18,28,29,30,33,37,47,51,53,61,62,64,91,98,106,113,114]}
    selected=[c for c in original['cases'] if c['id'] in ids]
    assert {c['id'] for c in selected}==ids
    save('run42-energy-regressions.json',dict(notice=NOTICE,
      provenance='Verbatim selected original case objects; references/rubrics preserved, not new run49 model_input.',
      use='Separate regression run with original run42 expected.json and frozen facts; adjudicate obsolete blanket timing against new directive.',cases=selected))
    print(f'Hashed {len(rows)} explicit source files; copied scorer; retained {len(selected)} run42 regression cases.')

if __name__=='__main__': main()
