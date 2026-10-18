"""Offline tests for the Atlas coordinator core and the recording fake. Nothing here contacts Home Assistant.
Run: python -I -m unittest discover -s Scripts/AtlasCoordinator/tests -v   (from the HomeAssistant folder)
"""
import json
import pathlib
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'custom_components'))
from atlas_household.core import Coordinator, STATUSES          # noqa: E402
from atlas_household.fake import FakeHouse, MemoryStore, SYDNEY  # noqa: E402
from atlas_household.tools import tool_specs, validate_args      # noqa: E402

REAL = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'custom_components/atlas_household/targets.json').read_text(encoding='utf-8'))


def scene_targets():
    """The real map plus a scene whose member states are known (as the freeze step will record them)."""
    t = json.loads(json.dumps(REAL))
    t['handles']['test_scene'] = {'kind': 'scene', 'group': 'scenes', 'entity_ids': ['scene.test_scene'], 'label': 'Test', 'risk': 'R1', 'enabled': True,
                                  'members': ['light.office_ceiling', 'light.attic_lamp'],
                                  'expect': {'light.office_ceiling': {'state': 'on', 'brightness_percent': 40}, 'light.attic_lamp': {'state': 'off'}}}
    return t


class Lights(unittest.TestCase):
    def setUp(self):
        self.h = FakeHouse()

    def test_off_done_and_verified(self):
        self.h.set('light.office_ceiling', 'on', brightness_percent=60)
        r = self.h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'})
        self.assertEqual(r['status'], 'done')
        self.assertEqual(self.h.calls, [{'domain': 'light', 'service': 'turn_off', 'entity_ids': ['light.office_ceiling'], 'data': {}}])
        self.assertEqual(self.h.state('light.office_ceiling')['state'], 'off')

    def test_already_sends_nothing(self):
        r = self.h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'})
        self.assertEqual(r['status'], 'skipped_already')
        self.assertEqual(self.h.calls, [])

    def test_room_partial_only_sends_needed(self):
        self.h.set('light.attic_lamp', 'on')
        r = self.h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'on'})
        self.assertEqual(r['status'], 'done')
        self.assertEqual(r['already'], 1)
        self.assertEqual(r['changed'], 3)
        self.assertNotIn('light.attic_lamp', self.h.calls[0]['entity_ids'])

    def test_brightness(self):
        self.h.set('light.attic_lamp', 'on', brightness_percent=30)
        r = self.h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'brightness', 'brightness_percent': 70})
        self.assertEqual(r['status'], 'done')
        self.assertEqual(self.h.calls[0]['data'], {'brightness_pct': 70})
        r2 = self.h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'brightness', 'brightness_percent': 71})
        self.assertEqual(r2['status'], 'skipped_already')

    def test_no_readback_is_not_done(self):
        self.h.no_readback.add('light.office_ceiling')
        r = self.h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'})
        self.assertEqual(r['status'], 'not_verified')
        self.assertNotIn('Done', r['summary'])

    def test_transport_error_one_attempt(self):
        self.h.raise_on_call = True
        r = self.h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'on'})
        self.assertEqual(r['status'], 'failed')
        self.assertEqual(len(self.h.calls), 1)

    def test_unavailable(self):
        self.h.set('light.office_ceiling', 'unavailable')
        r = self.h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'})
        self.assertEqual((r['status'], r['reason']), ('failed', 'unavailable'))
        self.assertEqual(self.h.calls, [])


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.h = FakeHouse()

    def test_entity_id_and_service_never_accepted(self):
        for args in ({'target_handle': 'light.office_ceiling', 'operation': 'on'}, {'target_handle': 'office_lights', 'operation': 'on', 'entity_id': 'light.x'},
                     {'target_handle': 'office_lights', 'operation': 'toggle'}, {'target_handle': 'office_lights', 'operation': 'on', 'service': 'light.turn_on'},
                     {'target_handle': 'office_lights', 'operation': 'on', 'brightness_percent': True}, {'target_handle': 'office_lights'}):
            r = self.h.call('atlas_lights', args)
            self.assertEqual(r['status'], 'denied', args)
        self.assertEqual(self.h.calls, [])

    def test_unknown_tool_and_media_and_ac(self):
        self.assertEqual(self.h.call('atlas_ac', {'target_handle': 'attic', 'operation': 'cool'})['status'], 'denied')
        self.assertEqual(self.h.call('atlas_media', {'target_handle': 'media_tv_set_tv_set', 'operation': 'pause'})['status'], 'denied')
        self.assertEqual(self.h.calls, [])

    def test_disabled_duplicate_scene(self):
        r = self.h.call('atlas_scene', {'recipe_handle': 'attic_home_ambience_attic_home_ambience'})
        self.assertEqual(r['status'], 'denied')

    def test_map_rejects_never_list(self):
        for bad in ({'kind': 'blind', 'entity_ids': ['cover.garage_door']}, {'kind': 'light', 'entity_ids': ['switch.export']},
                    {'kind': 'lock', 'entity_ids': ['lock.front']}, {'kind': 'light', 'entity_ids': ['light.battery_led']},
                    {'kind': 'blind', 'entity_ids': ['light.x']}):
            with self.assertRaises(ValueError):
                Coordinator({'handles': {'x': {'label': 'x', **bad}}}, None, MemoryStore(), None, SYDNEY)

    def test_real_map_domains(self):
        for h, t in REAL['handles'].items():
            for e in t['entity_ids']:
                self.assertTrue(e.split('.')[0] in ('light', 'scene', 'cover', 'media_player'), e)
        self.assertFalse([h for h, t in REAL['handles'].items() if t['kind'] == 'media' and t['enabled']])

    def test_every_status_is_known(self):
        self.assertEqual(set(STATUSES) >= {'done', 'skipped_already', 'needs_confirmation', 'denied', 'scheduled', 'cancelled'}, True)


class Blinds(unittest.TestCase):
    def setUp(self):
        self.h = FakeHouse()

    def test_yes_then_moves(self):
        r = self.h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'}, user_text='open the sunroom blind')
        self.assertEqual(r['status'], 'needs_confirmation')
        self.assertEqual(r['question'], 'Open the sunroom blind?')
        self.assertEqual(self.h.calls, [])
        r2 = self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes')
        self.assertEqual(r2['status'], 'done')
        self.assertEqual(self.h.calls[0]['service'], 'open_cover')

    def test_model_cannot_confirm_without_plain_yes(self):
        r = self.h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
        for words in ('', 'open the sunroom blind', 'no', 'yes but not now', 'what?'):
            self.assertEqual(self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text=words)['status'], 'denied', words)
        self.assertEqual(self.h.calls, [])

    def test_expiry_other_conversation_and_restart(self):
        r = self.h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
        self.assertEqual(self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes', conversation_id='other')['reason'], 'other_conversation')
        self.h.advance(seconds=61)
        self.assertEqual(self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes')['reason'], 'confirmation_expired')
        r = self.h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
        self.h.restart(timedelta(seconds=5))
        self.assertEqual(self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes')['reason'], 'no_such_confirmation')
        self.assertEqual(self.h.calls, [])

    def test_yes_must_be_a_later_turn(self):
        r = self.h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'}, user_text='yes', turn='T1')
        self.assertEqual(self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes', turn='T1')['reason'], 'no_plain_yes')
        self.assertEqual(self.h.calls, [])
        self.assertEqual(self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes', turn='T2')['status'], 'done')

    def test_already_closed(self):
        r = self.h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'close'})
        self.assertEqual(r['status'], 'skipped_already')


class Timers(unittest.TestCase):
    def setUp(self):
        self.h = FakeHouse()
        self.h.set('light.office_ceiling', 'on')

    def test_schedule_list_run(self):
        r = self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 15})
        self.assertEqual(r['status'], 'scheduled')
        self.assertIn('7:45 pm', r['label'])
        self.assertEqual(self.h.call('atlas_scheduled', {})['tasks'][0]['task'], r['task'])
        self.h.advance(minutes=14)
        self.assertEqual(self.h.tick(), [])
        self.h.advance(minutes=1)
        out = self.h.tick()
        self.assertEqual(out[0]['status'], 'done')
        self.assertEqual(self.h.state('light.office_ceiling')['state'], 'off')
        self.assertEqual(self.h.call('atlas_scheduled', {})['tasks'], [])

    def test_at_time_and_limits(self):
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '19:50'})['status'], 'scheduled')
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'at_time': '07:00'})['status'], 'scheduled')   # tomorrow 7 am (24 h cap, 1151)
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 1441})['reason'], 'bad_argument')
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off'})['reason'], 'bad_argument')
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'open', 'in_minutes': 5})['reason'], 'not_allowed_in_schedule')   # a light can't 'open'
        others = ['attic_lamp', 'galley_lights', 'entry_lights', 'deck_lights', 'carport_lights', 'utility_lights', 'corridor_lights', 'sunroom_lights']
        for h in others:      # 2 + 8 distinct timers = 10 waiting
            self.assertEqual(self.h.call('atlas_schedule', {'target_handle': h, 'operation': 'off', 'in_minutes': 5})['status'], 'scheduled')
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'attic_lights', 'operation': 'off', 'in_minutes': 5})['reason'], 'too_many_pending')

    def test_cancel_that_and_choice(self):
        a = self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, conversation_id='A')
        b = self.h.call('atlas_schedule', {'target_handle': 'attic_lights', 'operation': 'on', 'in_minutes': 10}, conversation_id='A')
        self.assertEqual(self.h.call('atlas_cancel', {}, conversation_id='A')['status'], 'needs_choice')      # two could be "that" [RT073]
        c = self.h.call('atlas_cancel', {'task': b['task']}, conversation_id='A')
        self.assertEqual((c['status'], c['task']), ('cancelled', b['task']))
        self.h.call('atlas_schedule', {'target_handle': 'entry_lights', 'operation': 'on', 'in_minutes': 10}, conversation_id='B')
        self.assertEqual(self.h.call('atlas_cancel', {}, conversation_id='C')['status'], 'needs_choice')
        self.assertEqual(self.h.call('atlas_cancel', {'task': a['task']}, conversation_id='C')['status'], 'cancelled')
        self.assertEqual(self.h.call('atlas_cancel', {'task': a['task']})['reason'], 'not_pending')
        self.h.advance(minutes=10)
        self.assertEqual([x['status'] for x in self.h.tick()], ['done'])     # only entry; the cancelled ones never run
        self.assertEqual({e for c in self.h.calls for e in c['entity_ids']} & {'light.office_ceiling', 'light.attic_lamp'}, set())

    def test_missed_during_restart_cancelled_not_run_late(self):
        self.h = FakeHouse(targets=keep_targets())
        self.h.set('light.office_ceiling', 'on')
        r = self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        keep = self.h.call('atlas_schedule', {'target_handle': 'attic_lights', 'operation': 'on', 'in_minutes': 30})
        changed = self.h.restart(timedelta(minutes=10))
        self.assertEqual([(t['id'], t['state']) for t in changed], [(r['task'], 'cancelled_missed')])
        self.assertEqual(self.h.tick(), [])
        self.assertEqual(self.h.calls, [])
        self.assertEqual(self.h.coord.notices[0]['task'], r['task'])
        lst = self.h.call('atlas_scheduled', {})
        self.assertEqual([x['task'] for x in lst['tasks']], [keep['task']])
        self.assertEqual(lst['missed'][0]['task'], r['task'])

    def test_late_tick_cancelled(self):
        self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        self.h.advance(minutes=5, seconds=31)
        self.assertEqual(self.h.tick()[0]['status'], 'cancelled_missed')
        self.assertEqual(self.h.calls, [])

    def test_crash_mid_dispatch_never_replayed(self):
        r = self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        task = next(t for t in self.h.coord.data['tasks'] if t['id'] == r['task'])
        task['state'] = 'dispatching'
        self.h.loop.run_until_complete(self.h.store.save(self.h.coord.data))
        changed = self.h.restart(timedelta(seconds=1))
        self.assertEqual(changed[0]['state'], 'outcome_unknown')
        self.h.advance(minutes=10)
        self.assertEqual(self.h.tick(), [])
        self.assertEqual(self.h.calls, [])

    def test_cancel_racing_dispatch(self):
        r = self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        next(t for t in self.h.coord.data['tasks'] if t['id'] == r['task'])['state'] = 'dispatching'
        self.assertEqual(self.h.call('atlas_cancel', {'task': r['task']})['reason'], 'too_late')

    def test_cancel_wins_if_first(self):
        import asyncio
        r = self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        self.h.advance(minutes=5)
        async def both():
            return await asyncio.gather(self.h.coord.call_tool('atlas_cancel', {'task': r['task']}, conversation_id='conv-1'), self.h.coord.tick())
        c, t = self.h.loop.run_until_complete(both())
        self.assertEqual(c['status'], 'cancelled')
        self.assertEqual(t, [])
        self.assertEqual(self.h.calls, [])

    def test_blind_timers_follow_the_map_flag(self):
        # The household map enables them (the owner, 1151); a map without the flag doesn't (fail closed)
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 10})['status'], 'needs_confirmation')
        h2 = FakeHouse(targets={k: v for k, v in json.loads(json.dumps(REAL)).items() if k != 'timer_blinds'})
        self.assertEqual(h2.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 10})['reason'], 'bad_argument')
        # unreviewed scenes are not offered, so not schedulable either
        self.assertEqual(self.h.call('atlas_schedule', {'target_handle': 'daily', 'operation': 'on', 'in_minutes': 10})['reason'], 'bad_argument')

    def test_blind_timer_needs_yes_when_set(self):
        self.h = FakeHouse(targets={**json.loads(json.dumps(REAL)), 'timer_blinds': True})
        r = self.h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 10})
        self.assertEqual(r['status'], 'needs_confirmation')
        self.assertEqual(self.h.call('atlas_scheduled', {})['tasks'], [])
        s = self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes please')
        self.assertEqual(s['status'], 'scheduled')
        self.h.advance(minutes=10)
        self.assertEqual(self.h.tick()[0]['status'], 'done')
        self.assertEqual(self.h.calls[0]['service'], 'open_cover')

    def test_light_timer_runs_even_if_changed_meanwhile(self):     # 1151 am. 1
        self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        self.h.set('light.office_ceiling', 'off')
        self.h.set('light.office_ceiling', 'on')                      # e.g. another automation turned it back on
        self.h.advance(minutes=5)
        self.assertEqual(self.h.tick()[0]['status'], 'done')
        self.assertEqual(self.h.state('light.office_ceiling')['state'], 'off')

    def test_light_timer_skips_lights_already_right(self):
        self.h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        self.h.set('light.office_ceiling', 'off')                     # already off by the due time
        self.h.advance(minutes=5)
        self.assertEqual(self.h.tick()[0]['status'], 'skipped_already')
        self.assertEqual(self.h.calls, [])

    def test_timer_already_at_due(self):
        self.h.set('light.attic_lamp', 'off')
        self.h.call('atlas_schedule', {'target_handle': 'attic_lamp', 'operation': 'off', 'in_minutes': 5})
        self.h.advance(minutes=5)
        self.assertEqual(self.h.tick()[0]['status'], 'skipped_already')
        self.assertEqual(self.h.calls, [])


class Undo(unittest.TestCase):
    def setUp(self):
        self.h = FakeHouse()

    def test_undo_restores_brightness(self):
        self.h.set('light.attic_lamp', 'on', brightness_percent=30)
        self.h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'off'})
        r = self.h.call('atlas_undo', {})
        self.assertEqual(r['status'], 'undone')
        self.assertEqual(self.h.calls[-1], {'domain': 'light', 'service': 'turn_on', 'entity_ids': ['light.attic_lamp'], 'data': {'brightness_pct': 30}})
        self.assertEqual(self.h.call('atlas_undo', {})['reason'], 'nothing_to_undo')

    def test_undo_window(self):
        self.h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'})
        self.h.advance(seconds=601)
        self.assertEqual(self.h.call('atlas_undo', {})['reason'], 'nothing_to_undo')

    def test_undo_blocked_if_changed_since(self):
        self.h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'})
        self.h.set('light.attic_lamp', 'off')
        r = self.h.call('atlas_undo', {})
        self.assertEqual(r['reason'], 'changed_since')
        self.assertEqual(len(self.h.calls), 1)

    def test_undo_blind_and_partial_group(self):
        r = self.h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'position', 'position_percent': 50})
        self.h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes')
        u = self.h.call('atlas_undo', {})
        self.assertEqual(u['status'], 'needs_confirmation')
        self.assertEqual(self.h.call('atlas_confirm', {'confirmation': u['confirmation']}, last_reply=u['question'], user_text='yes')['status'], 'undone')
        self.assertEqual(self.h.state(REAL['handles']['sunroom_blind']['entity_ids'][0])['attributes']['current_position'], 0)
        self.h.set('light.attic_lamp', 'on')
        self.h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'on'})
        self.h.set('light.attic_downlight_left', 'off')       # someone changed one since
        u = self.h.call('atlas_undo', {})
        self.assertEqual((u['status'], u['restored'], u['left_alone']), ('undone', 2, 1))
        self.assertEqual(self.h.state('light.attic_lamp')['state'], 'on')    # it was already on: not touched by the action, so not by undo


class Scenes(unittest.TestCase):
    def test_scene_expect_already_done_undo(self):
        h = FakeHouse(targets=scene_targets())
        r = h.call('atlas_scene', {'recipe_handle': 'test_scene'})
        self.assertEqual(r['status'], 'done')
        self.assertEqual(h.state('light.office_ceiling')['state'], 'on')
        self.assertEqual(h.call('atlas_scene', {'recipe_handle': 'test_scene'})['status'], 'skipped_already')
        self.assertEqual(h.call('atlas_undo', {})['status'], 'undone')
        self.assertEqual(h.state('light.office_ceiling')['state'], 'off')

    def test_unreviewed_scene_not_offered_and_denied(self):
        h = FakeHouse()
        r = h.call('atlas_scene', {'recipe_handle': 'lights_out'})
        self.assertEqual((r['status'], r['reason']), ('denied', 'bad_argument'))
        self.assertNotIn('atlas_scene', [t['function']['name'] for t in h.tools])     # no reviewed scene: no scene tool at all
        self.assertEqual(h.calls, [])

    def test_colour_scene(self):
        t = scene_targets()
        t['handles']['test_scene']['expect'] = {'light.office_ceiling': {'state': 'on', 'brightness_percent': 40, 'color_temp_kelvin': 2700},
                                                'light.attic_lamp': {'state': 'on', 'hs_color': [300.0, 80.0]}}
        h = FakeHouse(targets=t)
        h.set('light.office_ceiling', 'on', brightness_percent=40)
        h.backend.states['light.office_ceiling']['attributes'].update(color_temp_kelvin=6500, color_mode='color_temp')
        h.set('light.attic_lamp', 'on')
        h.backend.states['light.attic_lamp']['attributes'].update(hs_color=[30.0, 80.0], color_mode='hs')
        r = h.call('atlas_scene', {'recipe_handle': 'test_scene'})
        self.assertEqual(r['status'], 'done')       # not a false "already": the colours differed
        self.assertEqual(h.call('atlas_scene', {'recipe_handle': 'test_scene'})['status'], 'skipped_already')
        u = h.call('atlas_undo', {})
        self.assertEqual(u['status'], 'undone')
        self.assertEqual(h.state('light.office_ceiling')['attributes']['color_temp_kelvin'], 6500)
        self.assertEqual(h.state('light.attic_lamp')['attributes']['hs_color'], [30.0, 80.0])


def keep_targets():
    """The real map with the owner's possible choice: timers still to come survive a restart if the device is unchanged."""
    t = json.loads(json.dumps(REAL))
    t['restart_policy'] = 'keep_if_unchanged'
    return t


def h_tools():
    return tool_specs(REAL['handles'])


class ReviewFixes(unittest.TestCase):
    """Independent review R1 (5e12ec0) findings F01-F07, F12."""

    def test_F01_at_and_in_timers_order_by_time(self):
        h = FakeHouse()                                   # 19:30 Sydney
        h.set('light.office_ceiling', 'on')
        h.set('light.attic_lamp', 'on')
        a = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '19:35'})
        b = h.call('atlas_schedule', {'target_handle': 'attic_lamp', 'operation': 'off', 'in_minutes': 10})
        self.assertEqual(h.coord.next_due(), min(datetime.fromisoformat(t['due_at']) for t in h.coord.data['tasks']))
        self.assertEqual(h.coord.next_due().isoformat(), next(t['due_at'] for t in h.coord.data['tasks'] if t['id'] == a['task']))
        self.assertEqual(a['due_local'], '7:35 pm')
        h.advance(minutes=5)
        self.assertEqual([(x['task'], x['status']) for x in h.tick()], [(a['task'], 'done')])
        h.advance(minutes=5)
        self.assertEqual([(x['task'], x['status']) for x in h.tick()], [(b['task'], 'done')])

    def test_F02_partial_already_names_the_unavailable(self):
        h = FakeHouse()
        h.set('light.attic_lamp', 'unavailable')
        r = h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'off'})
        self.assertEqual(r['status'], 'skipped_already')
        self.assertIn("aren't available", r['summary'])
        self.assertEqual(r['unavailable'], 1)

    def test_F03_yes_answers_the_question_asked(self):
        h = FakeHouse()
        q1 = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
        q2 = h.call('atlas_blind', {'target_handle': 'family_room_window_blind', 'operation': 'open'})
        self.assertEqual(h.call('atlas_confirm', {'confirmation': q1['confirmation']}, user_text='yes', last_reply=q2['question'])['reason'], 'no_such_confirmation')
        q3 = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
        self.assertEqual(h.call('atlas_confirm', {'confirmation': q3['confirmation']}, user_text='ok', last_reply='Sure, anything else?')['reason'], 'question_not_asked')
        self.assertEqual(h.calls, [])
        self.assertEqual(h.call('atlas_confirm', {'confirmation': q3['confirmation']}, user_text='ok', last_reply=f"Sure. {q3['question']}")['status'], 'done')
        self.assertEqual(h.calls[0]['entity_ids'], REAL['handles']['sunroom_blind']['entity_ids'])
        self.assertTrue(q2)

    def test_F04_demo_map_not_in_package_and_drafts_not_installable(self):
        from atlas_household.core import installable
        pkg = pathlib.Path(__file__).resolve().parents[1] / 'custom_components/atlas_household'
        self.assertEqual(sorted(p.name for p in pkg.glob('targets*.json')), ['targets.json'])
        self.assertIsNotNone(installable(REAL))
        self.assertIsNone(installable({**REAL, 'version': 'frozen-1'}))
        demo = json.loads((pathlib.Path(__file__).parent / 'fixtures/targets.demo.json').read_text(encoding='utf-8'))
        self.assertIsNone(installable(demo))
        src = (pkg / '__init__.py').read_text(encoding='utf-8')
        self.assertIn("hass.config.location_name != TEST_COPY_NAME", src)
        self.assertIn("hass.services.async_remove(DOMAIN, svc)", src)

    def test_F06_timer_survives_restart_and_runs(self):
        h = FakeHouse(targets=keep_targets())
        h.set('light.office_ceiling', 'on')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 20})
        h.restart(timedelta(minutes=2))                  # resets every last_changed, as HA does
        self.assertEqual(h.rebased, [])
        self.assertEqual([x['task'] for x in h.call('atlas_scheduled', {})['tasks']], [r['task']])
        h.advance(minutes=18)
        self.assertEqual(h.tick()[0]['status'], 'done')

    def test_F06_changed_during_restart_cancelled(self):
        h = FakeHouse(targets=keep_targets())
        h.set('light.office_ceiling', 'on')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 20})
        h.backend.states['light.office_ceiling']['state'] = 'off'          # switched at the wall while HA was down
        h.restart(timedelta(minutes=2))
        self.assertEqual([(t['id'], t['state']) for t in h.rebased], [(r['task'], 'cancelled_changed')])

    def test_F06_no_undo_across_restart(self):
        h = FakeHouse()
        h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'})
        h.restart(timedelta(seconds=30))
        self.assertEqual(h.call('atlas_undo', {})['reason'], 'restarted')

    def test_F10_wall_clock_jump_back(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        h.jump_clock(minutes=-40)                         # wall clock steps back 40 min
        h.advance(minutes=45)                             # HA fires when the wall clock reaches the due time: 45 min of real time
        self.assertEqual(h.tick()[0]['status'], 'needs_review')      # the clock changed: stopped for a check (Codex 41 RT084)
        self.assertEqual(h.calls, [])

    def test_F12_open_without_position_is_unknown(self):
        h = FakeHouse()
        e = REAL['handles']['sunroom_blind']['entity_ids'][0]
        h.backend.states[e] = {'state': 'open', 'attributes': {'device_class': 'shade', 'supported_features': 15}}
        self.assertEqual(h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'close'})['reason'], 'position_unknown')
        h.backend.states[e] = {'state': 'open', 'attributes': {'device_class': 'shade', 'supported_features': 3}}     # open/close only: state is the position
        self.assertEqual(h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'close'})['status'], 'needs_confirmation')

    def test_own_change_does_not_cancel_the_next_timer(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        a = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        b = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'in_minutes': 10})
        h.advance(minutes=5)
        self.assertEqual([(x['task'], x['status']) for x in h.tick()], [(a['task'], 'done')])
        h.advance(minutes=5)
        self.assertEqual([(x['task'], x['status']) for x in h.tick()], [(b['task'], 'done')])
        self.assertEqual(h.state('light.office_ceiling')['state'], 'on')

    def test_N01_undo_restores_effect(self):
        h = FakeHouse()
        h.set('light.attic_lamp', 'on', brightness_percent=1)
        h.backend.states['light.attic_lamp']['attributes'].update(effect='candle', color_mode='color_temp', color_temp_kelvin=2200)
        h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'off'})
        u = h.call('atlas_undo', {})
        self.assertEqual(u['status'], 'undone')
        self.assertEqual(h.calls[-1]['data'], {'brightness_pct': 1, 'color_temp_kelvin': 2200, 'effect': 'candle'})
        self.assertEqual(h.state('light.attic_lamp')['attributes']['effect'], 'candle')

    def test_N01_effect_not_restored_is_not_undone(self):
        h = FakeHouse()
        h.set('light.attic_lamp', 'on')
        h.backend.states['light.attic_lamp']['attributes'].update(effect='candle')
        h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'off'})
        real = h.backend.call
        async def no_effect(domain, service, ids, data):
            await real(domain, service, ids, {k: v for k, v in data.items() if k != 'effect'})
            for e in ids:
                h.backend.states[e]['attributes']['effect'] = None
        h.backend.call = no_effect
        self.assertEqual(h.call('atlas_undo', {})['status'], 'not_verified')

    def test_R3_01_undo_turns_off_a_scene_started_effect(self):
        t = scene_targets()
        t['handles']['test_scene']['expect'] = {'light.office_ceiling': {'state': 'on', 'effect': 'prism'}, 'light.attic_lamp': {'state': 'off'}}
        h = FakeHouse(targets=t)
        h.set('light.office_ceiling', 'on', brightness_percent=80)
        self.assertEqual(h.call('atlas_scene', {'recipe_handle': 'test_scene'})['status'], 'done')
        self.assertEqual(h.state('light.office_ceiling')['attributes']['effect'], 'prism')
        u = h.call('atlas_undo', {})
        self.assertEqual(u['status'], 'undone')
        self.assertIn({'domain': 'light', 'service': 'turn_on', 'entity_ids': ['light.office_ceiling'], 'data': {'brightness_pct': 80, 'effect': 'off'}}, h.calls)

    def test_R3_01_effect_left_running_is_not_undone(self):
        t = scene_targets()
        t['handles']['test_scene']['expect'] = {'light.office_ceiling': {'state': 'on', 'effect': 'prism'}, 'light.attic_lamp': {'state': 'off'}}
        h = FakeHouse(targets=t)
        h.set('light.office_ceiling', 'on', brightness_percent=80)
        h.call('atlas_scene', {'recipe_handle': 'test_scene'})
        real = h.backend.call
        async def ignores_effect(domain, service, ids, data):     # a device that won't stop its effect
            await real(domain, service, ids, {k: v for k, v in data.items() if k != 'effect'})
        h.backend.call = ignores_effect
        self.assertEqual(h.call('atlas_undo', {})['status'], 'not_verified')     # prism keeps running: never "undone"

    def test_R3_02_mid_fade_read_back_is_not_a_hand_change(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on', brightness_percent=80)
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10})
        h.backend.states['light.office_ceiling']['attributes']['brightness'] = round(79 * 2.55)    # 1% drift as the light settles
        h.advance(minutes=10)
        self.assertEqual(h.tick()[0]['status'], 'done')

    def test_R3_04_unavailable_after_restart_says_so(self):
        h = FakeHouse(targets=keep_targets())
        h.set('light.office_ceiling', 'on')
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 20})
        h.backend.states['light.office_ceiling']['state'] = 'unavailable'
        h.restart(timedelta(minutes=1))
        self.assertEqual(h.rebased[0]['reason'], 'it could not be re-checked after the restart')

    def test_RT_default_restart_cancels_waiting_timers(self):
        h = FakeHouse()                                   # default policy: cancel_pending (Codex 40/41)
        h.set('light.office_ceiling', 'on')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 20})
        h.restart(timedelta(minutes=1))
        self.assertEqual([(x['id'], x['state']) for x in h.rebased], [(r['task'], 'cancelled')])
        h.advance(minutes=20)
        self.assertEqual(h.tick(), [])
        self.assertEqual(h.calls, [])

    def test_RT034_scene_with_changed_contents_refused(self):
        t = scene_targets()
        h = FakeHouse(targets=t)
        h.backend.states['scene.test_scene']['attributes']['entity_id'] = ['light.office_ceiling', 'light.attic_lamp', 'input_boolean.inverter_helper']
        r = h.call('atlas_scene', {'recipe_handle': 'test_scene'})
        self.assertEqual((r['status'], r['reason']), ('denied', 'scene_changed'))
        h.backend.states['scene.test_scene']['attributes'].pop('entity_id')       # contents not readable and not frozen offline
        self.assertEqual(h.call('atlas_scene', {'recipe_handle': 'test_scene'})['reason'], 'scene_changed')
        self.assertEqual(h.calls, [])

    def test_RT076_identical_timer_asks(self):
        h = FakeHouse()
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, request_id='a')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, request_id='b')
        self.assertEqual(r['status'], 'needs_choice')
        self.assertEqual(len(h.coord._pending()), 1)

    def test_RT095_undo_at_exactly_600s_refused(self):
        h = FakeHouse()
        h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'})
        h.advance(seconds=599)
        self.assertEqual(h.call('atlas_undo', {})['status'], 'undone')
        h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'off'})
        h.advance(seconds=600)
        self.assertEqual(h.call('atlas_undo', {})['reason'], 'nothing_to_undo')

    def test_RT114_yes_to_two_questions_asks(self):
        h = FakeHouse()
        q1 = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
        q2 = h.call('atlas_blind', {'target_handle': 'family_room_blinds', 'operation': 'open'})
        r = h.call('atlas_confirm', {'confirmation': q2['confirmation']}, user_text='yes', last_reply=f"{q1['question']} And: {q2['question']}")
        self.assertEqual(r['status'], 'needs_choice')
        self.assertEqual(h.calls, [])

    def test_R4_01_unconfirmed_timer_is_reported(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        h.no_readback.add('light.office_ceiling')
        h.advance(minutes=5)
        self.assertEqual(h.tick()[0]['status'], 'not_verified')
        self.assertEqual([(n['kind'], n['task']) for n in h.coord.notices], [('ran_not_confirmed', r['task'])])
        lst = h.call('atlas_scheduled', {})
        self.assertEqual(lst['missed'][0]['task'], r['task'])
        self.assertIn("couldn't be confirmed", lst['missed'][0]['what_happened'])

    def test_R5_01_notice_says_what_happened(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        real = h.store.save
        n = [0]

        async def fails_at_due(data):
            n[0] += 1
            if n[0] == 2:          # the 'dispatching' save works; the receipt save before the send fails
                raise OSError('disk full')
            await real(data)
        h.advance(minutes=5)
        h.store.save = fails_at_due
        out = h.tick()
        h.store.save = real
        self.assertEqual(h.calls, [])
        self.assertEqual([(x['kind'], x['task']) for x in h.coord.notices], [('did_not_run', r['task'])])
        self.assertTrue(h.state('light.office_ceiling')['state'] == 'on')
        self.assertTrue(out)

    def test_R6_01_save_fails_before_timer_send(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        real = h.store.save

        async def full(data):
            raise OSError('disk full')
        h.advance(minutes=5)
        h.store.save = full
        out = h.tick()
        h.store.save = real
        self.assertEqual(out[0]['status'], 'cancelled_missed')
        self.assertEqual(h.calls, [])
        self.assertEqual([(n['kind'], n['task']) for n in h.coord.notices], [('did_not_run', r['task'])])
        self.assertTrue(h.coord.inhibited)
        self.assertIn('did not run', h.call('atlas_scheduled', {})['missed'][0]['what_happened'])
        self.assertEqual(h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'})['reason'], 'inhibited')

    def test_R5_01_unreachable_device(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        h.raise_on_call = True
        h.advance(minutes=5)
        h.tick()
        self.assertEqual(h.coord.notices[-1]['kind'], 'could_not_reach')
        h.raise_on_call = False
        self.assertIn("couldn't reach the device", h.call('atlas_scheduled', {})['missed'][0]['what_happened'])

    def test_R4_03_same_light_different_times_allowed(self):
        h = FakeHouse()
        for op, m in (('on', 5), ('off', 10), ('on', 20)):
            self.assertEqual(h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': op, 'in_minutes': m})['status'], 'scheduled')
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'in_minutes': 20})['status'], 'needs_choice')

    def test_R4_04_cancel_that_never_reaches_another_conversation(self):
        h = FakeHouse()
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5}, conversation_id='A')
        self.assertEqual(h.call('atlas_cancel', {}, conversation_id='B')['status'], 'needs_choice')
        self.assertEqual(len(h.coord._pending()), 1)
        self.assertEqual(h.call('atlas_cancel', {}, conversation_id='A')['status'], 'cancelled')

    def test_R4_05_frozen_offline_flag_must_be_true(self):
        t = scene_targets()
        t['handles']['test_scene']['contents_frozen_offline'] = 'false'
        h = FakeHouse(targets=t)
        h.backend.states['scene.test_scene']['attributes'].pop('entity_id')
        self.assertEqual(h.call('atlas_scene', {'recipe_handle': 'test_scene'})['reason'], 'scene_changed')
        t['handles']['test_scene']['contents_frozen_offline'] = True
        h2 = FakeHouse(targets=t)
        h2.backend.states['scene.test_scene']['attributes'].pop('entity_id')
        self.assertEqual(h2.call('atlas_scene', {'recipe_handle': 'test_scene'})['status'], 'done')

    def test_1151_dim_and_brighten_by_20(self):
        h = FakeHouse()
        h.set('light.attic_lamp', 'on', brightness_percent=60)
        h.set('light.attic_downlight_left', 'on', brightness_percent=10)
        h.set('light.attic_downlight_middle', 'on', brightness_percent=100)
        r = h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'dim'})
        self.assertEqual(r['status'], 'done')
        self.assertEqual(r['levels'], {'light.attic_lamp': 40, 'light.attic_downlight_left': 1, 'light.attic_downlight_middle': 80})
        self.assertEqual(h.state('light.attic_downlight_right')['state'], 'off')          # dimming leaves off lights alone
        r2 = h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'brighten'})
        self.assertEqual((r2['status'], r2['levels']), ('done', {'light.attic_lamp': 60}))
        self.assertIn('to 60%', r2['summary'])
        h.set('light.office_ceiling', 'on', brightness_percent=100)
        self.assertEqual(h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'brighten'})['status'], 'skipped_already')
        self.assertEqual(h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'dim', 'brightness_percent': 5})['reason'], 'bad_argument')
        u = h.call('atlas_undo', {})
        self.assertEqual(u['status'], 'undone')
        self.assertEqual(round(h.state('light.attic_lamp')['attributes']['brightness'] / 2.55), 40)

    def test_1151_brighten_off_light_turns_on_at_20(self):
        h = FakeHouse()
        r = h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'brighten'})
        self.assertEqual((r['status'], r['levels']), ('done', {'light.office_ceiling': 20}))

    def test_1151_blind_timer_yes_bound_to_plan(self):
        h = FakeHouse()
        q = h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'at_time': '21:00'})
        self.assertEqual(q['status'], 'needs_confirmation')
        self.assertIn('9:00 pm', q['question'])
        h.set(REAL['handles']['sunroom_blind']['entity_ids'][0], 'open', position_percent=40)    # someone moved it before the yes
        r = h.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=q['question'])
        self.assertEqual(r['reason'], 'changed_since_question')
        self.assertEqual(h.coord._pending(), [])

    def test_1151_blind_timer_runs_and_rechecks_at_fire_time(self):
        h = FakeHouse()
        q = h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 120})
        s = h.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=q['question'])
        self.assertEqual(s['status'], 'scheduled')
        h.advance(minutes=120)
        self.assertEqual(h.tick()[0]['status'], 'done')
        q2 = h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'close', 'in_minutes': 60})
        h.call('atlas_confirm', {'confirmation': q2['confirmation']}, user_text='yes', last_reply=q2['question'])
        h.set(REAL['handles']['sunroom_blind']['entity_ids'][0], 'open', position_percent=50)     # moved by hand meanwhile
        h.advance(minutes=60)
        self.assertEqual(h.tick()[0]['status'], 'cancelled_changed')
        self.assertTrue(any(n['kind'] == 'cancelled_changed' for n in h.coord.notices))

    def test_1151_reviewed_scene_timer(self):
        h = FakeHouse(targets=scene_targets())
        r = h.call('atlas_schedule', {'target_handle': 'test_scene', 'operation': 'on', 'in_minutes': 30})
        self.assertEqual(r['status'], 'scheduled')
        h.advance(minutes=30)
        self.assertEqual(h.tick()[0]['status'], 'done')

    def test_R8_01_tomorrow_is_said_and_this_minute_asks(self):
        h = FakeHouse()                                     # 19:30 Sydney
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'at_time': '07:00'})
        self.assertIn('7:00 am tomorrow', r['summary'])
        self.assertEqual(r['due_local'], '7:00 am tomorrow')
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'at_time': '19:30'})['status'], 'needs_choice')
        h.advance(seconds=20)
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'on', 'at_time': '19:30'})['reason'], 'ambiguous_time')
        q = h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'at_time': '06:30'})
        self.assertIn('6:30 am tomorrow', q['question'])
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '19:45'})['due_local'], '7:45 pm')

    def test_R8_02_dim_names_unavailable_and_onoff_lights(self):
        h = FakeHouse()
        h.set('light.attic_lamp', 'on', brightness_percent=60)
        h.set('light.attic_downlight_left', 'unavailable')
        h.set('light.attic_downlight_middle', 'on')
        h.backend.states['light.attic_downlight_middle']['attributes'].update(brightness=None, supported_color_modes=['onoff'])
        r = h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'dim'})
        self.assertEqual(r['status'], 'done')
        self.assertIn("can only switch on or off", r['summary'])
        self.assertIn("available right now", r['summary'])
        self.assertEqual((r['unavailable'], r['not_dimmable']), (1, 1))      # R9-07: counts kept on a done result
        h2 = FakeHouse()
        h2.set('light.office_ceiling', 'on')
        h2.backend.states['light.office_ceiling']['attributes'].update(brightness=None, supported_color_modes=['onoff'])
        s = h2.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'dim'})
        self.assertEqual((s['status'], s['reason']), ('denied', 'not_supported'))     # R9-01: refused, never "already"
        self.assertIn('can only switch on or off', s['summary'])
        self.assertNotIn('lowest level', s['summary'])

    def test_R8_04_partial_send_is_recorded_and_undoable(self):
        h = FakeHouse()
        h.set('light.attic_lamp', 'on', brightness_percent=60)
        h.set('light.attic_downlight_left', 'on', brightness_percent=30)
        real, n = h.backend.call, [0]

        async def second_fails(*a):
            n[0] += 1
            if n[0] == 2:
                raise ConnectionError('lost')
            await real(*a)
        h.backend.call = second_fails
        r = h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'dim'})
        h.backend.call = real
        self.assertEqual(r['status'], 'failed')
        self.assertIn('1 changed and checked', r['summary'])
        self.assertEqual(h.call('atlas_undo', {})['status'], 'undone')

    def test_R8_05_brighten_raises_lit_lights_only(self):
        h = FakeHouse()
        h.set('light.attic_lamp', 'on', brightness_percent=40)
        r = h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'brighten'})
        self.assertEqual(r['levels'], {'light.attic_lamp': 60})
        self.assertEqual(h.state('light.attic_downlight_left')['state'], 'off')
        self.assertIn('off and left off', r['summary'])        # R9-01: never called "already"
        r2 = h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'brighten'})     # a dark room turns on at 20%
        self.assertEqual(r2['levels'], {'light.office_ceiling': 20})

    def test_R8_06_no_blind_timer_question_when_unavailable_or_moving(self):
        h = FakeHouse()
        e = REAL['handles']['sunroom_blind']['entity_ids'][0]
        h.backend.states[e] = {'state': 'unavailable', 'attributes': {'device_class': 'shade', 'supported_features': 15}}
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 30})['reason'], 'unavailable')
        h.backend.states[e] = {'state': 'opening', 'attributes': {'device_class': 'shade', 'supported_features': 15, 'current_position': 40}}
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 30})['reason'], 'moving')

    def test_R8_07_yes_keeps_the_time_asked(self):
        h = FakeHouse()
        q = h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 30})
        h.advance(seconds=50)
        s = h.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=q['question'])
        self.assertEqual(s['status'], 'scheduled')
        due = datetime.fromisoformat(h.coord.data['tasks'][0]['due_at'])
        self.assertEqual(due, h.clock - timedelta(seconds=50) + timedelta(minutes=30))

    def test_R8_08_hand_move_keeping_open_is_seen_at_the_yes(self):
        h = FakeHouse()
        e = REAL['handles']['sunroom_blind']['entity_ids'][0]
        h.backend.states[e] = {'state': 'open', 'attributes': {'device_class': 'shade', 'supported_features': 15, 'current_position': 100}, 'last_changed': 'r1'}
        q = h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'close', 'in_minutes': 30})
        h.backend.states[e]['attributes']['current_position'] = 60          # still "open", same last_changed
        r = h.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=q['question'])
        self.assertEqual(r['reason'], 'changed_since_question')

    def test_R8_09_due_itself_refuses_past_24h(self):
        h = FakeHouse()
        due, err = h.coord._due({'in_minutes': 1441})
        self.assertIsNone(due)
        self.assertEqual(err['reason'], 'too_far')
        self.assertIsNotNone(h.coord._due({'in_minutes': 1440})[0])

    def test_RT_unknown_restart_policy_rejected(self):
        with self.assertRaises(ValueError):
            FakeHouse(targets={**REAL, 'restart_policy': 'replay'})

    def test_R3_05_schedule_description_without_scenes(self):
        d = next(s for s in h_tools() if s['function']['name'] == 'atlas_schedule')['function']['description']
        self.assertNotIn('scene', d)

    def test_N02_hand_change_survives_an_atlas_command_blind(self):
        # The hand-change rule now applies to BLINDS only (1151 am. 1); the N02 property (an Atlas command must not hide an earlier hand
        # change) is kept for them.
        h = FakeHouse()
        e = REAL['handles']['sunroom_blind']['entity_ids'][0]
        q = h.call('atlas_schedule', {'target_handle': 'sunroom_blind', 'operation': 'open', 'in_minutes': 30}, conversation_id='A')
        h.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=q['question'], conversation_id='A')
        h.set(e, 'open', position_percent=40)                       # by hand
        q2 = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'close'}, conversation_id='B')
        h.call('atlas_confirm', {'confirmation': q2['confirmation']}, user_text='yes', last_reply=q2['question'], conversation_id='B')
        h.advance(minutes=30)
        self.assertEqual(h.tick()[0]['status'], 'cancelled_changed')

    def test_N07_hand_dimming_no_longer_cancels_a_light_timer(self):     # 1151 am. 1
        h = FakeHouse()
        h.set('light.office_ceiling', 'on', brightness_percent=60)
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10})
        h.backend.states['light.office_ceiling']['attributes']['brightness'] = round(20 * 2.55)
        h.advance(minutes=10)
        self.assertEqual(h.tick()[0]['status'], 'done')

    def test_N03_timer_without_snapshot_cancelled_at_restart(self):
        h = FakeHouse(targets=keep_targets())
        h.set('light.office_ceiling', 'on')
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 20})
        t = next(x for x in h.coord.data['tasks'] if x['id'] == r['task'])
        del t['snaps']
        h.loop.run_until_complete(h.store.save(h.coord.data))
        h.restart(timedelta(minutes=1))
        self.assertEqual([(x['id'], x['state']) for x in h.rebased], [(r['task'], 'needs_review')])

    def test_N04_clock_back_then_restart(self):
        h = FakeHouse(targets=keep_targets())
        h.set('light.office_ceiling', 'on')
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10})
        h.jump_clock(minutes=-40)
        h.restart(timedelta(minutes=1))
        self.assertEqual(h.rebased[0]['reason'], 'the clock changed')

    def test_N05_plain_lateness_says_late(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 5})
        h.advance(minutes=6)
        r = h.tick()[0]
        self.assertEqual(r['status'], 'cancelled_missed')
        self.assertIn('late', r['reason'])
        self.assertNotIn('clock', r['reason'])

    def test_F15_request_cache_per_conversation(self):
        h = FakeHouse()
        a = h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'}, request_id='x', conversation_id='A')
        b = h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, request_id='x', conversation_id='B')
        self.assertEqual((a['handle'], b['handle']), ('attic_lamp', 'office_lights'))


class Persistence(unittest.TestCase):
    def test_log_and_30_days(self):
        h = FakeHouse()
        h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'})
        self.assertTrue(any(x['event'] == 'tool' and x['status'] == 'done' for x in h.store.data['log']))
        h.advance(days=31)
        h.call('atlas_scheduled', {})
        self.assertEqual([x for x in h.store.data['log'] if x['label'] == 'atlas_lights'], [])
        self.assertEqual(h.store.data['receipts'], [])

    def test_receipt_durable_before_send(self):
        h = FakeHouse()
        seen = []
        orig = h.backend.call
        async def spy(*a):
            seen.append([r['phase'] for r in h.store.data['receipts']])
            await orig(*a)
        h.backend.call = spy
        h.call('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'})
        self.assertEqual(seen, [['sending']])


class Schemas(unittest.TestCase):
    def test_ha_tool_format(self):
        specs = tool_specs(REAL['handles'])
        names = [s['function']['name'] for s in specs]
        self.assertEqual(names, ['atlas_lights', 'atlas_blind', 'atlas_confirm', 'atlas_schedule', 'atlas_scheduled', 'atlas_cancel', 'atlas_undo'])
        self.assertIn('atlas_scene', [s['function']['name'] for s in tool_specs(scene_targets()['handles'])])
        for s in specs:
            self.assertEqual(s['type'], 'function')
            self.assertEqual(s['function']['parameters']['type'], 'object')
            json.dumps(s)
        enum = specs[0]['function']['parameters']['properties']['target_handle']['enum']
        self.assertIn('upstairs_lights', enum)
        self.assertFalse([e for e in enum if '.' in e])

    def test_validate(self):
        self.assertIsNone(validate_args('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'on'}, REAL['handles']))
        self.assertIsNotNone(validate_args('atlas_lights', {'target_handle': 'attic_lamp', 'operation': 'off', 'brightness_percent': 5}, REAL['handles']))
        self.assertIsNotNone(validate_args('atlas_schedule', {'target_handle': 'attic_lamp', 'operation': 'on', 'at_time': '7pm'}, REAL['handles']))


if __name__ == '__main__':
    unittest.main()
