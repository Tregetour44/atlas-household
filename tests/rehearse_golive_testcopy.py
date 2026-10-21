"""TEST COPY ONLY: rehearse GoLive-Atlas.ps1's live sequence and its rollback on the Docker test copy (directive Lead 20261019-1250:
"rollback scripted and tested on the test copy"). Runs INSIDE the atlas-ha-test container (aiohttp; token from /config/.atlas-test-token,
never printed). The PowerShell scripts can't target the test copy (Tools/HaDashboardSession.ps1 is pinned to the live HA by Energy), so this
mirrors their API calls one for one:
  setup   : an Ollama entry on the PC's Ollama (host.docker.internal:11434, existing model only, no download), a question-only conversation
            sub-entry, and an "Atlas" pipeline on it with prefer_local_intents on (the live shape)
  Pipeline: refuse if another pipeline uses the agent; guarded_agent option; the guarded entity appears; exposure unchanged; Atlas pipeline ->
            guarded agent + prefer_local_intents off; every other pipeline unchanged
  Agent   : sub-entry reconfigure: llm_hass_api ['atlas_household'] + the go-live prompt; every field read back
  turns   : a fast-path level turn and a model-path turn through the guarded agent (the coordinator records each atlas_ call)
  Rollback: tools off first (agent options from the before-image), then the pipeline from its before-image, then guarded_agent cleared; every
            read-back equal to the before-image; exposure unchanged
Prints one JSON report. Usage (host): docker cp this file and the go-live prompt in, then
  docker exec atlas-ha-test python /tmp/rehearse_golive_testcopy.py /tmp/prompt-template.golive.jinja
"""
import asyncio
import json
import sys

import aiohttp

BASE = 'http://127.0.0.1:8123'
TOKEN = open('/config/.atlas-test-token', encoding='utf-8').read().strip()
H = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
OLLAMA_URL = 'http://host.docker.internal:11434'
MODEL = 'gemma4:12b-it-q4_K_M'
BEFORE_PROMPT = 'You answer questions about the house. You cannot change anything.'
report = {'steps': []}


def step(name, ok, **kw):
    report['steps'].append({'step': name, 'ok': bool(ok), **kw})
    if not ok:
        raise SystemExit(json.dumps(report, indent=1, default=str))


class HA:
    def __init__(self, s):
        self.s, self.ws, self.n = s, None, 0

    async def rest(self, m, p, b=None):
        async with self.s.request(m, BASE + p, headers=H, json=b) as r:
            t = await r.text()
            if r.status >= 400:
                raise RuntimeError(f'{m} {p} -> {r.status} {t[:300]}')
            return json.loads(t) if t else None

    async def wsc(self, msg):
        if self.ws is None:
            self.ws = await self.s.ws_connect(BASE + '/api/websocket')
            await self.ws.receive_json()
            await self.ws.send_json({'type': 'auth', 'access_token': TOKEN})
            assert (await self.ws.receive_json())['type'] == 'auth_ok'
        self.n += 1
        await self.ws.send_json({'id': self.n, **msg})
        while True:
            r = await self.ws.receive_json()
            if r.get('id') == self.n and r.get('type') == 'result':
                if not r.get('success'):
                    raise RuntimeError(f"{msg['type']}: {r.get('error')}")
                return r.get('result')


def current(flow):
    out = {}
    for fd in flow.get('data_schema') or []:
        v = (fd.get('description') or {}).get('suggested_value')
        out[fd['name']] = fd.get('default') if v is None else v
    return out


def options_of(flow, name):
    fd = next((f for f in flow.get('data_schema') or [] if f['name'] == name), None)
    opts = ((fd or {}).get('selector') or {}).get('select', {}).get('options') or []
    return [o if isinstance(o, str) else o.get('value') for o in opts]


async def main(prompt_path):
    golive = open(prompt_path, encoding='utf-8').read()
    async with aiohttp.ClientSession() as s:
        ha = HA(s)
        atlas = [e for e in await ha.rest('GET', '/api/config/config_entries/entry?domain=atlas_household') if e['state'] == 'loaded']
        step('coordinator loaded', len(atlas) == 1)
        atlas = atlas[0]
        # ---- setup (idempotent) ----
        oll = await ha.rest('GET', '/api/config/config_entries/entry?domain=ollama')
        if not oll:
            f = await ha.rest('POST', '/api/config/config_entries/flow', {'handler': 'ollama'})
            r = await ha.rest('POST', f"/api/config/config_entries/flow/{f['flow_id']}", {'url': OLLAMA_URL})
            step('ollama entry created', r.get('type') == 'create_entry', result=r.get('type'))
            oll = await ha.rest('GET', '/api/config/config_entries/entry?domain=ollama')
        oll = oll[0]
        await asyncio.sleep(3)
        states = await ha.rest('GET', '/api/states')
        agents = [x['entity_id'] for x in states if x['entity_id'].startswith('conversation.') and 'claim' not in x['entity_id']
                  and x['entity_id'] not in ('conversation.home_assistant', 'conversation.atlas_stream_test')]
        subs = await ha.wsc({'type': 'config_entries/subentries/list', 'entry_id': oll['entry_id']})
        if not subs:
            f = await ha.rest('POST', '/api/config/config_entries/subentries/flow', {'handler': [oll['entry_id'], 'conversation'], 'show_advanced_options': False})
            models = options_of(f, 'model')
            step('model listed (no download)', MODEL in models, models=models)
            data = {k: v for k, v in current(f).items() if v is not None}
            data.update({'name': 'Atlas rehearsal', 'model': MODEL, 'prompt': BEFORE_PROMPT, 'llm_hass_api': []})
            r = await ha.rest('POST', f"/api/config/config_entries/subentries/flow/{f['flow_id']}", data)
            step('question-only sub-entry created', r.get('type') == 'create_entry', result=r.get('type'))
            subs = await ha.wsc({'type': 'config_entries/subentries/list', 'entry_id': oll['entry_id']})
            await asyncio.sleep(3)
        sub = subs[0]
        states = await ha.rest('GET', '/api/states')
        reg = await ha.wsc({'type': 'config/entity_registry/list'})
        agent = next(e['entity_id'] for e in reg if e.get('config_subentry_id') == sub['subentry_id'] and e['entity_id'].startswith('conversation.'))
        pipes = (await ha.wsc({'type': 'assist_pipeline/pipeline/list'}))['pipelines']
        atl = [p for p in pipes if p['name'] == 'Atlas']
        if not atl:
            await ha.wsc({'type': 'assist_pipeline/pipeline/create', 'name': 'Atlas', 'language': 'en', 'conversation_engine': agent,
                          'conversation_language': 'en', 'stt_engine': None, 'stt_language': None, 'tts_engine': None, 'tts_language': None,
                          'tts_voice': None, 'wake_word_entity': None, 'wake_word_id': None, 'prefer_local_intents': True})
            pipes = (await ha.wsc({'type': 'assist_pipeline/pipeline/list'}))['pipelines']
            atl = [p for p in pipes if p['name'] == 'Atlas']
        p = atl[0]

        async def open_reconf():
            return await ha.rest('POST', '/api/config/config_entries/subentries/flow',
                                 {'handler': [oll['entry_id'], 'conversation'], 'show_advanced_options': False, 'source': 'reconfigure',
                                  'subentry_id': sub['subentry_id']})

        async def reconf(cur, prompt, apis):
            data = {k: v for k, v in cur.items() if v is not None}
            data.update({'prompt': prompt, 'llm_hass_api': apis})
            f = await open_reconf()
            r = await ha.rest('POST', f"/api/config/config_entries/subentries/flow/{f['flow_id']}", data)
            await asyncio.sleep(5)
            back = current(await open_reconf())
            diff = [k for k in data if json.dumps(back.get(k), sort_keys=True) != json.dumps(data[k], sort_keys=True)]
            return r, back, diff

        # ---- reset to the live starting shape if an earlier run stopped part-way (test copy only) ----
        cur0 = current(await open_reconf())
        if cur0.get('llm_hass_api') or cur0.get('prompt') != BEFORE_PROMPT:
            await reconf(cur0, BEFORE_PROMPT, [])
        if p['conversation_engine'] != agent or p['prefer_local_intents'] is not True:
            upd = {k: v for k, v in p.items() if k != 'id'}
            upd.update({'conversation_engine': agent, 'prefer_local_intents': True})
            await ha.wsc({'type': 'assist_pipeline/pipeline/update', 'pipeline_id': p['id'], **upd})
        if (atlas.get('options') or {}).get('guarded_agent') or any('claim' in x['entity_id'] and x['state'] != 'unavailable'
                                                                      for x in await ha.rest('GET', '/api/states') if x['entity_id'].startswith('conversation.')):
            f = await ha.rest('POST', '/api/config/config_entries/options/flow', {'handler': atlas['entry_id']})
            await ha.rest('POST', f"/api/config/config_entries/options/flow/{f['flow_id']}", {'guarded_agent': ''})
            await asyncio.sleep(4)
        pipes = (await ha.wsc({'type': 'assist_pipeline/pipeline/list'}))['pipelines']
        p = next(x for x in pipes if x['id'] == p['id'])
        step('one Atlas pipeline on the question-only agent, prefer-local on', p['conversation_engine'] == agent and p['prefer_local_intents'] is True,
             pipeline=p)
        # ---- before-images ----
        before_agent = current(await open_reconf())
        before_pipe = dict(p)
        before_others = {x['id']: x for x in pipes if x['id'] != p['id']}
        before_exp = await ha.wsc({'type': 'homeassistant/expose_entity/list'})
        step('before: question-only agent', not before_agent.get('llm_hass_api'), llm_hass_api=before_agent.get('llm_hass_api'))
        # ---- Pipeline step (guard first) ----
        users = [x['name'] for x in pipes if x['conversation_engine'] == agent and x['id'] != p['id']]
        step('no other pipeline uses the agent', not users, users=users)
        f = await ha.rest('POST', '/api/config/config_entries/options/flow', {'handler': atlas['entry_id']})
        r = await ha.rest('POST', f"/api/config/config_entries/options/flow/{f['flow_id']}", {'guarded_agent': agent})
        step('guarded_agent option set', r.get('type') == 'create_entry', result=r.get('type'))
        await asyncio.sleep(4)
        guarded = next((x['entity_id'] for x in await ha.rest('GET', '/api/states') if x['entity_id'].startswith('conversation.') and 'claim' in x['entity_id']), None)
        step('guarded entity appeared', guarded, guarded=guarded)
        step('exposure unchanged after the guarded entity', await ha.wsc({'type': 'homeassistant/expose_entity/list'}) == before_exp)
        upd = {k: v for k, v in p.items() if k != 'id'}
        upd.update({'conversation_engine': guarded, 'prefer_local_intents': False})
        await ha.wsc({'type': 'assist_pipeline/pipeline/update', 'pipeline_id': p['id'], **upd})
        pipes2 = (await ha.wsc({'type': 'assist_pipeline/pipeline/list'}))['pipelines']
        p2 = next(x for x in pipes2 if x['id'] == p['id'])
        others2 = {x['id']: x for x in pipes2 if x['id'] != p['id']}
        step('pipeline on the guarded agent, prefer-local off, others unchanged', p2['conversation_engine'] == guarded and p2['prefer_local_intents'] is False
             and others2 == before_others)
        # ---- Agent step (tools) ----
        apis = options_of(await open_reconf(), 'llm_hass_api')
        step('atlas_household LLM API offered', 'atlas_household' in apis, apis=apis)
        r, back, diff = await reconf(before_agent, golive, ['atlas_household'])
        step('agent has the Atlas tools and the go-live prompt; every field read back', r.get('reason') == 'reconfigure_successful' and not diff
             and back.get('llm_hass_api') == ['atlas_household'] and back.get('prompt') == golive, result=r.get('reason'), differing=diff)
        # ---- turns through the guarded agent ----
        t1 = await ha.rest('POST', '/api/conversation/process', {'text': 'turn the bed light to half', 'language': 'en', 'agent_id': guarded})
        sp1 = t1['response']['speech']['plain']['speech']
        bed = await ha.rest('GET', '/api/states/light.bed_light')
        step('fast-path level turn', (sp1.startswith('Done') or 'already on at 50%' in sp1) and bed['state'] == 'on' and bed['attributes'].get('brightness') in (127, 128),
             speech=sp1, brightness=bed['attributes'].get('brightness'))
        t2 = await ha.rest('POST', '/api/conversation/process', {'text': 'could you get the bed light off for me', 'language': 'en', 'agent_id': guarded})
        sp2 = t2['response']['speech']['plain']['speech']
        bed2 = await ha.rest('GET', '/api/states/light.bed_light')
        step('model-path turn answered (Gemma with the Atlas tools, via the guard)', bool(sp2.strip()), speech=sp2[:200], bed=bed2['state'])
        # ---- Rollback: tools off first ----
        r, back, diff = await reconf(before_agent, before_agent.get('prompt') or BEFORE_PROMPT, [x for x in (before_agent.get('llm_hass_api') or []) if x])
        step('rollback 1: agent options back (no tools)', r.get('reason') == 'reconfigure_successful' and not back.get('llm_hass_api')
             and back.get('prompt') == before_agent.get('prompt'), differing=diff)
        upd = {k: v for k, v in before_pipe.items() if k != 'id'}
        await ha.wsc({'type': 'assist_pipeline/pipeline/update', 'pipeline_id': p['id'], **upd})
        p3 = next(x for x in (await ha.wsc({'type': 'assist_pipeline/pipeline/list'}))['pipelines'] if x['id'] == p['id'])
        step('rollback 2: pipeline equal to its before-image', p3 == before_pipe, after=p3)
        f = await ha.rest('POST', '/api/config/config_entries/options/flow', {'handler': atlas['entry_id']})
        r = await ha.rest('POST', f"/api/config/config_entries/options/flow/{f['flow_id']}", {'guarded_agent': ''})
        await asyncio.sleep(4)
        still = [x['entity_id'] for x in await ha.rest('GET', '/api/states') if x['entity_id'].startswith('conversation.') and 'claim' in x['entity_id']
                 and x['state'] != 'unavailable']
        step('rollback 3: guarded agent cleared', r.get('type') == 'create_entry' and not still, still=still)
        step('exposure unchanged at the end', await ha.wsc({'type': 'homeassistant/expose_entity/list'}) == before_exp)
        report['result'] = 'REHEARSAL_PASS'
        if ha.ws:
            await ha.ws.close()
    print(json.dumps(report, indent=1, default=str))


asyncio.run(main(sys.argv[1]))
