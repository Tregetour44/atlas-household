"""The coordinator on the TEST COPY (Docker atlas-ha-test, 127.0.0.1:18123, HA's demo devices only), through HA's real LLM API path:
the registered "atlas_household" API, its tools, HA's chat log and HA's own service calls and states. Never the household HA.
Steps: copy the integration into the test copy, restart the container, create the entry with targets.demo.json (if absent), then run the
scenarios via the test-only service atlas_household.test_call. Includes a real timer firing, a container restart over a due timer, and a reload.
The test-copy token is read from the gitignored devha-config/.atlas-test-token inside this script and never printed.
Writes tests/testcopy-results.json. Run: python -I Scripts/AtlasCoordinator/tests/run_testcopy.py
"""
import json
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'custom_components'))
from atlas_household.tools import api_prompt, tool_specs  # noqa: E402

BASE = 'http://127.0.0.1:18123'
TOKEN = (ROOT / 'devha-config/.atlas-test-token').read_text().strip()
DEMO_FILE = HERE / 'fixtures/targets.demo.json'      # never shipped in the package; the installer below copies it into the test copy only
DEMO = json.loads(DEMO_FILE.read_text(encoding='utf-8'))
assert BASE.startswith('http://127.0.0.1:'), 'test copy only'


def http(method, path, body=None, ok=(200, 201)):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        if r.status not in ok:
            raise RuntimeError(f'{method} {path}: {r.status}')
        return json.loads(r.read() or b'null')


def state(e):
    return http('GET', f'/api/states/{e}')


def call(tool, args=None, text='', conv='tc-1', new_turn=True, last_reply=None):
    body = {'tool': tool, 'args': args or {}, 'user_text': text, 'conversation_id': conv, 'new_turn': new_turn}
    if last_reply:
        body['last_reply'] = last_reply
    return http('POST', '/api/services/atlas_household/test_call?return_response', body)['service_response']['result']


def store(tick=False):
    return http('POST', '/api/services/atlas_household/test_state?return_response', {'tick': tick})['service_response']


def wait_up(timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if any(s['domain'] == 'atlas_household' and 'test_call' in s['services'] for s in http('GET', '/api/services')):
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('test copy did not come up with atlas_household')


CODE_SHA = None


def install():
    global CODE_SHA
    import hashlib  # noqa: PLC0415
    pkg = ROOT / 'custom_components/atlas_household'
    CODE_SHA = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(pkg.glob('*.py')) + [pkg / 'manifest.json'])).hexdigest()
    dst = ROOT / 'devha-config/custom_components/atlas_household'
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(ROOT / 'custom_components/atlas_household', dst, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(DEMO_FILE, dst / 'targets.demo.json')
    st = ROOT / 'devha-config/custom_components/atlas_stream_test'      # TEST COPY ONLY streaming agent (R12-01 evidence)
    shutil.rmtree(st, ignore_errors=True)
    shutil.copytree(HERE / 'fixtures/atlas_stream_test', st, ignore=shutil.ignore_patterns('__pycache__'))
    subprocess.run(['docker', 'restart', 'atlas-ha-test'], check=True, capture_output=True)
    end = time.time() + 180
    while time.time() < end:
        try:
            http('GET', '/api/')
            break
        except Exception:
            time.sleep(2)
    entries = http('GET', '/api/config/config_entries/entry?domain=atlas_household')
    if not entries:
        flow = http('POST', '/api/config/config_entries/flow', {'handler': 'atlas_household'})
        res = http('POST', f"/api/config/config_entries/flow/{flow['flow_id']}", {'targets': 'targets.demo.json'})
        if res.get('type') != 'create_entry':
            raise RuntimeError(f'config flow: {res.get("type")}')
    if not http('GET', '/api/config/config_entries/entry?domain=atlas_stream_test'):
        flow = http('POST', '/api/config/config_entries/flow', {'handler': 'atlas_stream_test'})
        http('POST', f"/api/config/config_entries/flow/{flow['flow_id']}", {})
    wait_up()


def eq(a, b, what=''):
    if a != b:
        raise AssertionError(f'{what}: {a!r} != {b!r}')


def ok(c, what):
    if not c:
        raise AssertionError(what)


def S_format():
    st = store()
    eq(st['tools'], tool_specs(DEMO['handles'], DEMO.get('timer_blinds') is True), 'HA conversion of the tools == tools.py')
    eq(st['api_prompt'], api_prompt(DEMO['handles']), 'api prompt')


def S_lights():
    call('atlas_lights', {'target_handle': 'bed_light', 'operation': 'off'}, 'turn the bed light off')
    r = call('atlas_lights', {'target_handle': 'bed_light', 'operation': 'on'}, 'turn the bed light on')
    eq(r['status'], 'done'); eq(state('light.bed_light')['state'], 'on')
    eq(call('atlas_lights', {'target_handle': 'bed_light', 'operation': 'on'}, 'turn the bed light on')['status'], 'skipped_already')
    call('atlas_lights', {'target_handle': 'living_room_lights', 'operation': 'on'}, 'living room lights on')
    r = call('atlas_lights', {'target_handle': 'living_room_lights', 'operation': 'off'}, 'turn the living room lights off')
    eq(r['status'], 'done'); eq([state(e)['state'] for e in ('light.ceiling_lights', 'light.living_room_rgbww_lights')], ['off', 'off'])
    r = call('atlas_lights', {'target_handle': 'kitchen_lights', 'operation': 'brightness', 'brightness_percent': 50}, 'kitchen to half')
    eq(r['status'], 'done'); ok(abs(state('light.kitchen_lights')['attributes']['brightness'] / 2.55 - 50) <= 2, 'brightness 50')


def S_denials():
    before = {e: state(e)['last_changed'] for e in ('light.entrance_color_white_lights', 'light.office_rgbw_lights', 'cover.garage_door')}
    eq(call('atlas_lights', {'target_handle': 'entrance_lights', 'operation': 'off'}, 'entrance off')['reason'], 'bad_argument')   # disabled: not even offered
    eq(call('atlas_lights', {'target_handle': 'light.office_rgbw_lights', 'operation': 'off'}, 'office off')['reason'], 'bad_argument')
    eq(call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off', 'entity_id': 'cover.garage_door'}, 'office off')['reason'], 'bad_argument')
    eq(call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, 'turn the office off and open the garage door')['reason'], 'never_list')
    after = {e: state(e)['last_changed'] for e in before}
    eq(after, before, 'nothing changed')


def S_blind():
    st = state('cover.hall_window')
    target = 'close' if st['state'] == 'open' else 'open'
    r = call('atlas_blind', {'target_handle': 'hall_window', 'operation': target}, f'{target} the hall window')
    eq(r['status'], 'needs_confirmation')
    eq(call('atlas_confirm', {'confirmation': r['confirmation']}, new_turn=False)['reason'], 'no_plain_yes', 'same turn')
    eq(state('cover.hall_window')['last_changed'], st['last_changed'], 'not moved before the yes')
    eq(call('atlas_confirm', {'confirmation': r['confirmation']}, 'yes', last_reply='Anything else?')['reason'], 'question_not_asked')
    c = call('atlas_confirm', {'confirmation': r['confirmation']}, 'yes', last_reply=r['question'])
    eq(c['status'], 'done', c.get('summary')); eq(state('cover.hall_window')['state'], 'closed' if target == 'close' else 'open')
    eq(call('atlas_blind', {'target_handle': 'kitchen_window', 'operation': 'position', 'position_percent': 50}, 'kitchen window half')['reason'], 'not_supported')


def S_scene_undo():
    call('atlas_lights', {'target_handle': 'ceiling_lights', 'operation': 'off'}, 'ceiling off')
    call('atlas_lights', {'target_handle': 'bed_light', 'operation': 'on'}, 'bed light on')
    r = call('atlas_scene', {'recipe_handle': 'evening'}, 'evening scene')
    eq(r['status'], 'done', r.get('summary'))
    eq((state('light.ceiling_lights')['state'], state('light.bed_light')['state']), ('on', 'off'))
    eq(call('atlas_scene', {'recipe_handle': 'evening'}, 'evening scene')['status'], 'skipped_already')
    u = call('atlas_undo', {}, 'undo that')
    eq(u['status'], 'undone', u.get('summary')); eq((state('light.ceiling_lights')['state'], state('light.bed_light')['state']), ('off', 'on'))


def S_timer_fires():
    call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, 'office on')
    r = call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 1}, 'office off in a minute')
    eq(r['status'], 'scheduled')
    eq(call('atlas_scheduled', {}, "what's scheduled?")['tasks'][0]['task'], r['task'])
    time.sleep(66)
    task = next(t for t in store()['data']['tasks'] if t['id'] == r['task'])
    eq((task['state'], task.get('result')), ('ran', 'done'), 'fired by HA'); eq(state('light.office_rgbw_lights')['state'], 'off')


def S_cancel():
    call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, 'office on')
    r = call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 1}, 'office off in a minute')
    eq(call('atlas_cancel', {}, 'cancel that')['task'], r['task'])
    time.sleep(66)
    eq(state('light.office_rgbw_lights')['state'], 'on', 'cancelled timer did not run')


def S_restart_missed():
    call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, 'office on')
    r = call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 1}, 'office off in a minute')
    subprocess.run(['docker', 'stop', 'atlas-ha-test'], check=True, capture_output=True)
    time.sleep(70)
    subprocess.run(['docker', 'start', 'atlas-ha-test'], check=True, capture_output=True)
    wait_up()
    task = next(t for t in store()['data']['tasks'] if t['id'] == r['task'])
    eq(task['state'], 'cancelled_missed', 'missed during restart')
    lst = call('atlas_scheduled', {}, "what's scheduled?")
    ok(any(m['task'] == r['task'] for m in lst.get('missed') or []), 'named as missed')


def S_at_in_order_across_restart():
    # Review F01 + F06: an "at HH:MM" timer and an "in N minutes" timer, then a container restart before either is due; both must still fire,
    # in time order, once HA is back (not cancelled as "changed by hand" by the restart's reset of last_changed).
    from datetime import datetime, timedelta
    from atlas_household.fake import SYDNEY       # Windows Python has no tzdata: SYDNEY falls back to fixed AEDT (right for Oct 2026)
    # Lights whose demo state survives a restart: the demo resets every light to its default (on, brightness 180 = 71%) when HA starts, and the
    # bed light to off, so a bed-light timer is (correctly) cancelled as "changed while Home Assistant was restarting". Put both at their defaults.
    for t in [t for t in store()['data']['tasks'] if t['state'] == 'pending']:      # clear leftovers from earlier runs
        call('atlas_cancel', {'task': t['id']}, 'cancel that')
    for h in ('office_lights', 'kitchen_lights'):
        call('atlas_lights', {'target_handle': h, 'operation': 'brightness', 'brightness_percent': 71}, f'{h} on')
    at = (datetime.now(SYDNEY) + timedelta(minutes=3)).strftime('%H:%M')
    a = call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': at}, f'office off at {at}')
    b = call('atlas_schedule', {'target_handle': 'kitchen_lights', 'operation': 'off', 'in_minutes': 4}, 'kitchen lights off in four minutes')
    eq((a['status'], b['status']), ('scheduled', 'scheduled'))
    subprocess.run(['docker', 'restart', 'atlas-ha-test'], check=True, capture_output=True)
    wait_up()
    time.sleep(10)
    st = store()
    ok(st['ready'], 'coordinator ready after start')
    eq(sorted(t['id'] for t in st['data']['tasks'] if t['state'] == 'pending'), sorted([a['task'], b['task']]), 'both still pending after the restart')
    end = time.time() + 300
    while time.time() < end:
        tasks = {t['id']: t for t in store()['data']['tasks']}
        if tasks[a['task']]['state'] != 'pending' and tasks[b['task']]['state'] != 'pending':
            break
        time.sleep(5)
    eq((tasks[a['task']]['state'], tasks[a['task']].get('result')), ('ran', 'done'), 'at-timer')
    eq((tasks[b['task']]['state'], tasks[b['task']].get('result')), ('ran', 'done'), 'in-timer')
    ok(tasks[a['task']]['closed_at'] < tasks[b['task']]['closed_at'], 'fired in time order')
    eq((state('light.office_rgbw_lights')['state'], state('light.kitchen_lights')['state']), ('off', 'off'))


def S_claim_guard():
    # Wiring of the claim-guarded agent (within directive 0142). On the test copy the underlying agent is HA's built-in one, which can
    # switch the demo bed light itself without any atlas_ tool: the guard must rewrite its "Turned on…" claim, and pass a plain answer through.
    # (In the house the underlying agent is the Atlas model, whose only tools are the atlas_ ones.)
    entry = http('GET', '/api/config/config_entries/entry?domain=atlas_household')[0]
    flow = http('POST', '/api/config/config_entries/options/flow', {'handler': entry['entry_id']})
    res = http('POST', f"/api/config/config_entries/options/flow/{flow['flow_id']}", {'guarded_agent': 'conversation.home_assistant'})
    eq(res.get('type'), 'create_entry', 'options flow')
    wait_up()
    time.sleep(3)
    guarded = next(s['entity_id'] for s in http('GET', '/api/states') if s['entity_id'].startswith('conversation.') and 'claim' in s['entity_id'])
    # the bed light is already on, so HA's agent says "Turned on the light" but changes nothing
    call('atlas_lights', {'target_handle': 'bed_light', 'operation': 'on'}, 'bed light on')
    before = state('light.bed_light')['last_changed']
    r = http('POST', '/api/conversation/process', {'text': 'turn on the bed light', 'language': 'en', 'agent_id': guarded})
    sp = r['response']['speech']['plain']['speech']
    # HA's agent ran its own (non-atlas) intent tool this turn, so the guard can't say nothing changed: "I can't confirm all of that." [R13-06]
    ok(sp.startswith("I can't confirm all of that.") and 'Turned on' not in sp, f'claim not rewritten as expected: {sp!r}')
    eq((state('light.bed_light')['state'], state('light.bed_light')['last_changed']), ('on', before), 'nothing changed')
    r2 = http('POST', '/api/conversation/process', {'text': 'what time is it', 'language': 'en', 'agent_id': guarded})
    sp2 = r2['response']['speech']['plain']['speech']
    ok("haven't changed" not in sp2 and sp2, f'plain answer altered: {sp2!r}')
    flow = http('POST', '/api/config/config_entries/options/flow', {'handler': entry['entry_id']})
    http('POST', f"/api/config/config_entries/options/flow/{flow['flow_id']}", {'guarded_agent': ''})      # back to no guarded agent
    wait_up()


def S_stream_guard():
    # R12-01/03/09/10 on HA 2026.8. A pipeline-shaped turn (chat log opened WITH a delta listener, then conversation.async_converse) to a
    # STREAMING agent with a false claim (tests/fixtures/atlas_stream_test): unguarded, the listener sees the claim (what streaming TTS would
    # speak); claim-guarded, it sees nothing, the speech is rewritten, and the chat log holds the rewritten text, not the original.
    entry = http('GET', '/api/config/config_entries/entry?domain=atlas_household')[0]
    agent = 'conversation.atlas_stream_test'
    ok(state(agent), 'stream test agent missing')
    t = call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 30}, 'office off in half an hour')
    eq(t['status'], 'scheduled')

    def options(value):
        flow = http('POST', '/api/config/config_entries/options/flow', {'handler': entry['entry_id']})
        return http('POST', f"/api/config/config_entries/options/flow/{flow['flow_id']}", {'guarded_agent': value})

    eq(options('conversation.nope').get('errors'), {'guarded_agent': 'not_a_conversation_agent'}, 'missing agent refused')
    eq(options(agent).get('type'), 'create_entry', 'options flow')
    time.sleep(3)
    guarded = next(s['entity_id'] for s in http('GET', '/api/states') if s['entity_id'].startswith('conversation.') and 'claim' in s['entity_id'])
    eq(options(guarded).get('errors'), {'guarded_agent': 'points_at_itself'}, 'self-reference refused')
    task = next(x for x in store()['data']['tasks'] if x['id'] == t['task'])
    eq(task['state'], 'pending', 'an options change keeps pending timers (no reload)')

    def probe(agent_id, cid):
        text = 'turn the bed light off in 30 minutes' if cid.endswith('fast') else 'living room lights off'
        return http('POST', '/api/services/atlas_stream_test/probe?return_response',
                    {'text': text, 'conversation_id': cid, 'agent_id': agent_id})['service_response']

    raw = probe(agent, 'tc-stream-raw')
    ok(''.join(raw['deltas']).startswith('I have turned off'), f'control: the harness did not see the stream: {raw!r}')
    n_before = len([x for x in store()['data']['log'] if x.get('label') == 'nudged once' and x.get('conversation') == 'tc-stream-guarded'])
    g = probe(guarded, 'tc-stream-guarded')
    eq(g['deltas'], [], 'deltas reached the listener before the guard (streaming TTS would speak them)')
    ok(g['speech'].startswith("I haven't changed anything") and 'turned off' not in g['speech'], f'speech not rewritten: {g!r}')
    ok('cannot manage the battery settings' in g['speech'], f'honest part lost: {g!r}')
    eq(g['history'][-1:], [g['speech']], 'chat log keeps the rewritten reply')
    eq(len(g['history']), 1, 'the history keeps only what was said (the unspoken first reply and the nudge are dropped) [B16-02]')
    nudges = [x for x in store()['data']['log'] if x.get('event') == 'claim_guard' and x.get('label') == 'nudged once'
              and x.get('conversation') == 'tc-stream-guarded']
    eq(len(nudges) - n_before, 1, 'the model was nudged exactly once this run (coordinator log)')
    # the deterministic timer path: scheduled by the coordinator itself; the (stream) model is not asked at all
    f = probe(guarded, 'tc-stream-fast')
    ok(f['speech'].startswith('Timer set'), f'fast timer path not taken: {f!r}')
    eq(f['deltas'], [], 'no model output streamed')
    ok(not any('turned off the living room' in h for h in f['history']), f'the model was asked: {f!r}')
    pend = [x for x in store()['data']['tasks'] if x['state'] == 'pending' and x['handle'] == 'bed_light']
    eq(len(pend), 1, 'one bed-light timer pending')
    ok(not any('turned off' in h for h in g['history']), f'original claim left in history: {g!r}')
    eq(options('').get('type'), 'create_entry', 'back to no guarded agent')
    eq(call('atlas_cancel', {}, 'cancel that')['task'], t['task'])
    for x in [x for x in store()['data']['tasks'] if x['state'] == 'pending']:      # the fast-path timer too
        call('atlas_cancel', {'task': x['id']}, 'cancel that one')


def S_nudge_keeps_the_persons_words():
    # B16-01 through HA's real LLM API path: after the person's never-list turn, the claim guard's nudge message is added to the chat log,
    # and a tool the model calls then must still be checked against the PERSON's words (api.py skips the nudge), so the turn is refused.
    nudge = next(line.split('"')[1] for line in (ROOT / 'custom_components/atlas_household/turn.py').read_text(encoding='utf-8').splitlines()
                 if line.startswith('NUDGE = '))
    conv = 'tc-nudge-words'
    call('atlas_scheduled', {}, 'kitchen lights on and unlock the front door', conv=conv)          # the person's turn (a harmless read)
    r = call('atlas_lights', {'target_handle': 'kitchen_lights', 'operation': 'on'}, nudge, conv=conv)   # the nudge, then a tool call
    eq((r['status'], r.get('reason')), ('denied', 'never_list'), 'a tool call during the nudge is judged on the person\'s words')


def S_reload_cancels():
    r = call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5}, 'office off in five')
    entry = http('GET', '/api/config/config_entries/entry?domain=atlas_household')[0]
    http('POST', f"/api/config/config_entries/entry/{entry['entry_id']}/reload")
    wait_up()
    task = next(t for t in store()['data']['tasks'] if t['id'] == r['task'])
    eq(task['state'], 'cancelled', 'reload/disable cancels pending timers')


def main():
    install()
    rows, bad = [], 0
    only = set(sys.argv[1:])       # optional: scenario names to run (default all)
    for name, fn in [(k, v) for k, v in globals().items() if k.startswith('S_') and (not only or k[2:] in only)]:
        t0 = time.time()
        try:
            fn()
            rows.append({'scenario': name[2:], 'result': 'PASS', 'seconds': round(time.time() - t0, 1)})
        except Exception as ex:
            bad += 1
            rows.append({'scenario': name[2:], 'result': 'FAIL', 'detail': f'{type(ex).__name__}: {ex}'})
    code = CODE_SHA
    out = {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'where': 'atlas-ha-test (Docker, demo devices only)', 'map': DEMO['version'], 'code_sha256': code,
           'pass': len(rows) - bad, 'fail': bad, 'rows': rows}
    (HERE / 'testcopy-results.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(out, indent=1))
    return bad


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
