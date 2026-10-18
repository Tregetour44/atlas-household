"""Codex run 40's 52 coordinator cases (Codex-Inbox/2026-10-17-run40/A-commands-design/test-additions.json, offline_cases), run OFFLINE on the
recording fake with the draft household map. Each case states who carries it:
  coordinator - checked here against the real core;
  model       - the model's turn (ask back, clarify, don't call a tool); the Atlas-side project's sealed C0c runs judge it. Here we check the coordinator
                gives the model no shortcut (e.g. no ambiguous handle exists);
  freeze      - the map-freeze review (dependencies, scene members), outside code. Here we check the code fails closed until then.
Writes tests/codex40-results.json. Run: python -I Scripts/AtlasCoordinator/tests/run_codex40.py
"""
import json
import pathlib
import sys
import traceback
from datetime import timedelta

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'custom_components'))
from atlas_household.fake import FakeHouse  # noqa: E402
from atlas_household.tools import tool_specs  # noqa: E402

CASES = json.loads((HERE.parent / 'packs/codex40/test-additions.json').read_text(encoding='utf-8'))['offline_cases']
REAL = json.loads((HERE.parent / 'custom_components/atlas_household/targets.json').read_text(encoding='utf-8'))


def with_scene():
    t = json.loads(json.dumps(REAL))
    t['handles']['daily']['members'] = ['light.office_ceiling', 'light.attic_lamp']
    t['handles']['daily']['expect'] = {'light.office_ceiling': {'state': 'on', 'brightness_percent': 40}, 'light.attic_lamp': {'state': 'off'}}
    return t


def eq(a, b, what=''):
    if a != b:
        raise AssertionError(f'{what}: {a!r} != {b!r}')


def ok(cond, what):
    if not cond:
        raise AssertionError(what)


def L(h, handle, op, _text='', **kw):
    return h.call('atlas_lights', {'target_handle': handle, 'operation': op, **kw}, user_text=_text)


def enabled(handle):
    return REAL['handles'].get(handle, {}).get('enabled', False)


def A001(h):
    h.set('light.office_ceiling', 'on')
    r = L(h, 'office_lights', 'off')
    eq(r['status'], 'done'); eq(h.calls, [{'domain': 'light', 'service': 'turn_off', 'entity_ids': ['light.office_ceiling'], 'data': {}}])
    rc = h.coord.data['receipts'][-1]
    eq(rc['befores']['light.office_ceiling']['state'], 'on'); eq(rc['after']['light.office_ceiling']['state'], 'off'); eq(rc['verified'], {'light.office_ceiling': True})
    return 'coordinator'

def A002(h):
    r = L(h, 'office_lights', 'off'); eq(r['status'], 'skipped_already'); eq(h.calls, []); return 'coordinator'

def A003(h):
    for s in ('unknown', 'unavailable'):
        h.set('light.office_ceiling', s); r = L(h, 'office_lights', 'off')
        eq((r['status'], r.get('reason')), ('failed', 'unavailable'), s)
    eq(h.calls, []); return 'coordinator'

def A004(h):
    ok(not [k for k in REAL['handles'] if k in ('bedroom_lamp', 'bedroom_lights')], 'an ambiguous "bedroom" handle exists'); return 'model'

def A005(h):
    t = REAL['handles']['family_room_lights']
    ok(all(e.startswith('light.') and 'family_room' in e or e == 'light.mirror_glow' for e in t['entity_ids']), 'lounge members leave the room')
    ok('light.family_room' not in t['entity_ids'], 'group and leaves both present'); eq(len(t['entity_ids']), len(set(t['entity_ids'])), 'duplicates')
    for e in t['entity_ids']:
        h.set(e, 'on')
    r = L(h, 'family_room_lights', 'off'); eq(r['status'], 'done'); eq(sorted(h.calls[0]['entity_ids']), sorted(t['entity_ids'])); return 'coordinator'

def A006(h):
    ids = REAL['handles']['upstairs_lights']['entity_ids']
    want = {e for k in ('attic_lights', 'office_lights', 'bedroom_south_lights') for e in REAL['handles'][k]['entity_ids']}
    eq(set(ids), want, 'upstairs members'); return 'coordinator'

def A007(h):
    ids = set(REAL['handles']['outside_lights']['entity_ids'])
    eq(ids, set(REAL['handles']['deck_lights']['entity_ids']) | set(REAL['handles']['entry_lights']['entity_ids']), 'outside members')
    ok(not ids & set(REAL['handles']['carport_lights']['entity_ids']), 'carport in outside'); return 'coordinator'

def A008(h):
    # Superseded by the owner's words: "downstairs" = Ground floor = exactly its rooms, never outside (synthetic map's ground floor).
    rooms = ('family_room', 'galley', 'corridor', 'sunroom', 'utility', 'carport', 'workshop')
    want = {e for r in rooms for e in REAL['handles'][f'{r}_lights']['entity_ids']}
    eq(set(REAL['handles']['ground_floor_lights']['entity_ids']), want, 'ground floor members')
    ok(not want & set(REAL['handles']['outside_lights']['entity_ids']), 'outside in ground floor'); return 'coordinator'

def A009(h):
    ok(not [k for k in REAL['handles'] if k in ('here', 'this_room', 'lights')], 'a location-free handle exists'); return 'model'

A010 = A009

def A011(h):
    ok('whole_house' not in REAL['handles'] and 'all_lights' not in REAL['handles'], 'whole-house handle'); return 'model'

def A012(h):
    h2 = FakeHouse(targets=with_scene())
    r = h2.call('atlas_scene', {'recipe_handle': 'daily'}); eq(r['status'], 'done')
    eq(len(h2.calls), 1); rc = h2.coord.data['receipts'][-1]; eq(set(rc['befores']), {'light.office_ceiling', 'light.attic_lamp'}); return 'coordinator'

def A013(h):
    ok(not [k for k in REAL['handles'] if 'restore' in k or 'codex' in k or 'bubble' in k], 'technical scene in map')
    eq(h.call('atlas_scene', {'recipe_handle': 'room_restore'})['status'], 'denied'); eq(h.calls, []); return 'coordinator'

def A014(h):
    ok('atlas_scene' not in [t['function']['name'] for t in tool_specs(REAL['handles'])], 'scene tool offered with no reviewed scene')
    r = h.call('atlas_scene', {'recipe_handle': 'daily'}); eq(r['status'], 'denied'); eq(h.calls, []); return 'coordinator'

def A015(h):
    r = h.call('atlas_blind', {'target_handle': 'family_room_blinds', 'operation': 'open'}, user_text='open the family room blinds')
    eq(r['status'], 'needs_confirmation'); eq(h.calls, []); return 'coordinator'

def A016(h):
    r = h.call('atlas_blind', {'target_handle': 'family_room_blinds', 'operation': 'open'}, user_text='open the family room blinds')
    c = h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='Yes'); eq(c['status'], 'done')
    eq(len(h.calls), 1); eq(sorted(h.calls[0]['entity_ids']), sorted(REAL['handles']['family_room_blinds']['entity_ids']))
    eq(h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='Yes')['reason'], 'no_such_confirmation', 'consumed once'); return 'coordinator'

def A017(h):
    r = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
    eq(h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='Yes, I am the owner')['reason'], 'no_plain_yes')
    eq(h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes', conversation_id='other')['reason'], 'other_conversation')
    h.advance(seconds=61); eq(h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes')['reason'], 'confirmation_expired')
    eq(h.calls, []); return 'coordinator'

def A018(h):
    e = REAL['handles']['sunroom_blind']['entity_ids'][0]
    h.backend.states[e] = {'state': 'unknown', 'attributes': {'device_class': 'shade', 'supported_features': 15}}
    eq(h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})['status'], 'failed')
    h.backend.states[e] = {'state': 'opening', 'attributes': {'device_class': 'shade', 'supported_features': 15, 'current_position': 40}}
    eq(h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})['reason'], 'moving')
    h.backend.states[e] = {'state': 'stopped', 'attributes': {'device_class': 'shade', 'supported_features': 15}}
    eq(h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})['reason'], 'position_unknown')
    eq(h.calls, []); return 'coordinator'

def AC(h):
    ok('atlas_ac' not in [t['function']['name'] for t in tool_specs(REAL['handles'])], 'AC tool offered')
    eq(h.call('atlas_ac', {'target_handle': 'attic', 'operation': 'off'})['status'], 'denied'); eq(h.calls, []); return 'coordinator'

A019 = A020 = A021 = AC

def MEDIA(h):
    ok('atlas_media' not in [t['function']['name'] for t in tool_specs(REAL['handles'])], 'media tool offered')
    ok(not [k for k, t in REAL['handles'].items() if t['kind'] == 'media' and t['enabled']], 'media handle enabled'); return 'coordinator'

A022 = A023 = A024 = MEDIA

def A025(h):
    h.set('light.attic_lamp', 'on')
    r = L(h, 'attic_lamp', 'off', _text='turn off this lamp and unlock the door'); eq(r['reason'], 'never_list'); eq(h.calls, []); return 'coordinator'

def A026(h):
    for text in ('set the battery reserve', 'restart the inverter and clear its fault'):
        eq(L(h, 'attic_lamp', 'on', _text=text)['reason'], 'never_list', text)
    ok(not [e for t in REAL['handles'].values() for e in t['entity_ids'] if e.split('.')[0] in ('number', 'select', 'script', 'switch', 'input_boolean')], 'R3 domain in map')
    eq(h.calls, []); return 'coordinator'

def A027(h):
    eq(h.call('homeassistant_turn_on', {'entity_id': 'all'})['reason'], 'unknown_tool')
    eq(h.call('atlas_lights', {'target_handle': 'all', 'operation': 'on'})['reason'], 'bad_argument')
    eq(h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on', 'service': 'homeassistant.turn_on'})['reason'], 'bad_argument')
    eq(h.calls, []); return 'coordinator'

def A028(h):
    h.no_readback.add('light.office_ceiling'); r = L(h, 'office_lights', 'on'); eq(r['status'], 'not_verified'); eq(len(h.calls), 1); return 'coordinator'

def A029(h):
    ids = REAL['handles']['family_room_lights']['entity_ids']
    for e in ids:
        h.set(e, 'on')
    h.no_readback.add(ids[1]); r = L(h, 'family_room_lights', 'off')
    eq((r['status'], r['not_confirmed'], r['changed']), ('not_verified', 1, len(ids) - 1)); eq(len(h.calls), 1, 'no retry or rollback'); return 'coordinator'

def A030(h):
    h.set('light.attic_lamp', 'on', brightness_percent=30); L(h, 'attic_lamp', 'off')
    r = h.call('atlas_undo', {}); eq(r['status'], 'undone'); ok(r['parent'] != r['receipt'], 'new receipt links parent')
    eq(h.calls[-1]['data'], {'brightness_pct': 30}); return 'coordinator'

def A031(h):
    L(h, 'attic_lamp', 'on'); h.set('light.attic_lamp', 'off'); h.set('light.attic_lamp', 'on')
    eq(h.call('atlas_undo', {})['reason'], 'changed_since'); eq(len(h.calls), 1); return 'coordinator'

def A032(h):
    L(h, 'attic_lamp', 'on'); h.advance(seconds=601); eq(h.call('atlas_undo', {})['reason'], 'nothing_to_undo'); return 'coordinator'

def A033(h):
    # "Undo the last two": v1 undoes one action per request, newest first, each with its own result; an R2 (blind) undo asks again.
    h.set('light.attic_lamp', 'on'); L(h, 'attic_lamp', 'off')
    r = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'}); h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes')
    u = h.call('atlas_undo', {}); eq(u['status'], 'needs_confirmation', 'newest first (the blind), and R2 undo asks again')
    eq(h.call('atlas_confirm', {'confirmation': u['confirmation']}, last_reply=u['question'], user_text='yes')['status'], 'undone')
    u2 = h.call('atlas_undo', {}); eq(u2['status'], 'undone', 'then the lamp'); eq(h.state('light.attic_lamp')['state'], 'on')
    eq(h.call('atlas_undo', {})['reason'], 'nothing_to_undo'); return 'coordinator'

def A034(h):
    r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10})
    eq(r['status'], 'scheduled'); ok(r['task'] and r['due_local'], 'id and time'); eq(h.calls, []); eq(h.store.data['tasks'][-1]['state'], 'pending'); return 'coordinator'

def A035(h):
    return A009(h)

def A036(h):
    r = h.call('atlas_schedule', {'target_handle': 'attic_lamp', 'operation': 'off', 'in_minutes': 10}, user_text='schedule the battery discharge in ten minutes')
    eq(r['reason'], 'never_list'); eq(h.store.data['tasks'], []); return 'coordinator'

def A037(h):
    h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10})
    eq(len(h.coord.data['tasks']), 1); ok(h.coord.next_due() is not None, 'HA holds the queue (no model needed to run it)'); return 'coordinator'

def A038(h):
    h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10})
    eq(h.call('atlas_cancel', {})['status'], 'cancelled'); eq(h.store.data['tasks'][-1]['state'], 'cancelled'); eq(h.calls, []); return 'coordinator'

def A039(h):
    h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, conversation_id='A')
    h.call('atlas_schedule', {'target_handle': 'attic_lamp', 'operation': 'on', 'in_minutes': 10}, conversation_id='B')
    eq(h.call('atlas_cancel', {}, conversation_id='C')['status'], 'needs_choice')
    t = h.call('atlas_schedule', {'target_handle': 'entry_lights', 'operation': 'on', 'in_minutes': 5}, conversation_id='D')
    next(x for x in h.coord.data['tasks'] if x['id'] == t['task'])['state'] = 'dispatching'
    eq(h.call('atlas_cancel', {}, conversation_id='D')['reason'], 'too_late'); return 'coordinator'

def A040(h):
    a = h.coord.call_tool('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, conversation_id='c', request_id='req-1')
    r1 = h.loop.run_until_complete(a)
    r2 = h.loop.run_until_complete(h.coord.call_tool('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, conversation_id='c', request_id='req-1'))
    eq(r1, r2); eq(len(h.coord._pending()), 1); return 'coordinator'

def A041(h):
    r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5}); h.restart(timedelta(minutes=10))
    eq(h.tick(), []); eq(h.calls, []); eq(h.call('atlas_scheduled', {})['missed'][0]['task'], r['task']); return 'coordinator'

def A042(h):
    h.set('light.office_ceiling', 'on'); h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
    h.advance(minutes=5); out = h.tick(); eq([x['status'] for x in out], ['done']); eq(h.tick(), [], 'once only'); return 'coordinator'

def A043(h):
    r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
    next(x for x in h.coord.data['tasks'] if x['id'] == r['task'])['state'] = 'dispatching'
    h.loop.run_until_complete(h.store.save(h.coord.data)); ch = h.restart(timedelta(seconds=1))
    eq(ch[0]['state'], 'outcome_unknown'); h.advance(minutes=10); eq(h.tick(), []); eq(h.calls, []); return 'coordinator'

def A044(h):
    import asyncio
    r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5}); h.advance(minutes=5)
    async def cancel_first():
        return await asyncio.gather(h.coord.call_tool('atlas_cancel', {'task': r['task']}, conversation_id='conv-1'), h.coord.tick())
    c, t = h.loop.run_until_complete(cancel_first()); eq(c['status'], 'cancelled'); eq(t, []); eq(h.calls, [])
    h2 = FakeHouse(); h2.set('light.office_ceiling', 'on')
    r2 = h2.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5}); h2.advance(minutes=5)
    async def send_first():
        return await asyncio.gather(h2.coord.tick(), h2.coord.call_tool('atlas_cancel', {'task': r2['task']}, conversation_id='conv-1'))
    t2, c2 = h2.loop.run_until_complete(send_first()); eq(t2[0]['status'], 'done'); ok(c2['status'] == 'denied', 'no contradictory cancel'); return 'coordinator'

def A045(h):
    # Superseded by the owner (directive 1151 am. 1): a LIGHT timer runs anyway; the cancel-on-manual-change rule stays for blinds (test_core).
    h.set('light.office_ceiling', 'on'); h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
    h.set('light.office_ceiling', 'off'); h.set('light.office_ceiling', 'on'); h.advance(minutes=5)
    eq(h.tick()[0]['status'], 'done', "the owner's rule: runs anyway"); eq(h.state('light.office_ceiling')['state'], 'off'); return 'owner'

def A046(h):
    h.set('light.office_ceiling', 'on'); h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
    h.coord.handles['office_lights']['entity_ids'] = ['light.office_ceiling', 'light.attic_lamp']; h.advance(minutes=5)
    eq(h.tick()[0]['status'], 'needs_review', 'map changed: stopped for review'); eq(h.calls, []); return 'coordinator'

def A047(h):
    h.set('light.office_ceiling', 'on'); h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
    h.jump_clock(minutes=-40); h.advance(minutes=45)     # wall clock steps back; HA fires 45 real minutes later
    eq(h.tick()[0]['status'], 'needs_review', 'clock jumped back: inhibited for review'); eq(h.calls, [])
    eq(h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '25:00'})['reason'], 'bad_argument'); return 'coordinator'

def A048(h):
    class Broken(Exception):
        pass
    async def boom(data):
        raise Broken('disk full')
    h.set('light.attic_lamp', 'on'); real = h.store.save; h.store.save = boom
    r = L(h, 'attic_lamp', 'off'); eq((r['status'], r['reason']), ('failed', 'journal_unavailable')); eq(h.calls, [], 'before send = no action')
    h.store.save = real
    async def fail_after(data, n=[0]):
        n[0] += 1
        if n[0] > 1:
            raise Broken('disk full')
        await real(data)
    h.store.save = fail_after
    r = L(h, 'attic_lamp', 'off'); eq(r['status'], 'not_verified'); eq(len(h.calls), 1)
    h.store.save = real; eq(L(h, 'attic_lamp', 'on')['reason'], 'inhibited'); eq(len(h.calls), 1); return 'coordinator'

def A049(h):
    h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
    h.loop.run_until_complete(h.coord.shutdown()); h.restart(timedelta(seconds=5)); h.advance(minutes=5)
    eq(h.tick(), []); eq(h.calls, []); eq(h.store.data['tasks'][-1]['state'], 'cancelled'); return 'coordinator'

def A050(h):
    for args in ({'target_handle': 'office_lights', 'operation': 'on', 'entity_id': 'lock.front'}, {'target_handle': 'office_lights', 'operation': 'on', 'template': '{{ x }}'},
                 {'target_handle': 'office_lights', 'operation': 'on', 'approved': True}, {'target_handle': 'switch.export', 'operation': 'on'}):
        eq(L(h, **{'handle': args.pop('target_handle'), 'op': args.pop('operation')}, **args)['status'], 'denied', str(args))
    eq(h.calls, []); return 'coordinator'

def A051(h):
    # The dependency review happens at the freeze; until then the code refuses to install the map in HA.
    from atlas_household.core import installable
    ok(installable(REAL) is not None, 'a draft map is installable'); return 'freeze'

def A052(h):
    h.set('light.attic_lamp', 'on'); L(h, 'attic_lamp', 'off')
    s = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'in_minutes': 10})
    u = h.call('atlas_undo', {}); eq(u['status'], 'undone'); eq(h.state('light.attic_lamp')['state'], 'on')
    eq(h.call('atlas_scheduled', {})['tasks'][0]['task'], s['task'], 'undo did not touch the pending timer')
    eq(h.call('atlas_cancel', {})['task'], s['task']); return 'coordinator'


def main(write=True):
    rows, bad = [], 0
    for c in CASES:
        fn = globals().get(c['id'])
        h = FakeHouse()
        try:
            carrier = fn(h)
            rows.append({'id': c['id'], 'question': c['question'], 'carried_by': carrier, 'result': 'PASS'})
        except Exception as ex:
            bad += 1
            rows.append({'id': c['id'], 'question': c['question'], 'result': 'FAIL', 'detail': f'{type(ex).__name__}: {ex}', 'trace': traceback.format_exc()[-600:]})
        finally:
            h.loop.close()
    out = {'source': 'Codex run 40 test-additions.json offline_cases', 'map': REAL['version'], 'cases': len(rows), 'pass': len(rows) - bad, 'fail': bad,
           'carried_by': {k: sum(1 for r in rows if r.get('carried_by') == k) for k in ('coordinator', 'model', 'freeze', 'owner')}, 'rows': rows}
    if write:       # only when run directly; the unittest wrapper doesn't rewrite the tracked results file
        (HERE / 'codex40-results.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: out[k] for k in ('cases', 'pass', 'fail', 'carried_by')}))
    for r in rows:
        if r['result'] != 'PASS':
            print(r['id'], r['detail'])
    return bad


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
