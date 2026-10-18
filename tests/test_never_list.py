"""Codex 43 H2 regression tests: the whole-turn refusal and the map's never-list. Codex's 9 pclosets (Codex-Inbox/2026-10-18-run43/
safety-pclosets.json) plus variants. A mixed turn must be denied with ZERO backend calls; hazardous targets must be rejected at map load."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'custom_components'))
from atlas_household.core import Coordinator  # noqa: E402
from atlas_household.fake import SYDNEY, FakeHouse, MemoryStore  # noqa: E402

REAL = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'custom_components/atlas_household/targets.json').read_text(encoding='utf-8'))
MIXED = ['turn on the office light and change the energy settings', 'turn on the office light and disable solar',
         'turn on the office light and activate the door opener', 'office light on and set the battery reserve to 10',
         'office light on and disarm the alarm', 'office light on, then open the garage door', 'office light on and put the battery on self-use',
         'office light on and stop the feed-in', 'office light on and open the gate', 'office light on and unlock the front door',
         'office light on and switch the inverter to backup power', 'office light on and stop exporting to the grid',
         'office light on and arm the house', 'office light on and open the roller door', 'office light on and use the openers',
         # R12-05
         'office light on and open the garage', 'office light on and open the door', 'office light on, garage-door up', 'office light on and the frontdoor',
         'office light on and secure the house', 'office light on and arm security', 'office light on and set away mode', 'office light on and check the panels',
         'office light on and how much PV today',
         # R13-07
         'office light on and garage up', 'office light on and garage open', 'office light on and pop the garage open', 'office light on and open the roller',
         'office light on and set the house to away', 'office light on and arm everything', 'office light on and start the EV charger',
         'office light on and charge the car', 'office light on and plug in the ev', 'office light on and open the rollers', 'office light on and arm it all']


class WholeTurnRefusal(unittest.TestCase):
    def test_mixed_turns_refused_with_zero_calls(self):
        for text in MIXED:
            h = FakeHouse()
            r = h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, user_text=text)
            self.assertEqual((r['status'], r.get('reason')), ('denied', 'never_list'), text)
            self.assertEqual(h.calls, [], text)

    def test_ordinary_turns_still_work(self):
        for text in ('turn on the office light', 'carport lights on', 'dim the attic', 'lights on in the corridor please', 'open the family room door blind',
                     'close the corridor door blind halfway', 'turn on the carport downlights'):
            h = FakeHouse()
            self.assertEqual(h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, user_text=text)['status'], 'done', text)


class MapNeverList(unittest.TestCase):
    def load(self, handles, reviewed=None, test_only=False):
        Coordinator({'handles': handles, 'reviewed_covers': reviewed or {}, **({'test_only': True} if test_only else {})}, None, MemoryStore(), None, SYDNEY)

    def test_codex_targets_rejected(self):
        for kind, e in (('light', 'light.energy_controller'), ('blind', 'cover.front_door'), ('light', 'light.battery_indicator'), ('lock', 'lock.front')):
            with self.assertRaises(ValueError, msg=e):
                self.load({'x': {'kind': kind, 'label': 'x', 'entity_ids': [e]}}, {e: 'shade'})

    def test_cover_needs_review_and_a_blind_class(self):
        with self.assertRaises(ValueError):          # not on the reviewed list
            self.load({'x': {'kind': 'blind', 'label': 'x', 'entity_ids': ['cover.office_blind']}})
        for cls in ('carport', 'door', 'gate', 'window', None):
            with self.assertRaises(ValueError, msg=cls):
                self.load({'x': {'kind': 'blind', 'label': 'x', 'entity_ids': ['cover.office_blind']}}, {'cover.office_blind': cls})
        self.load({'x': {'kind': 'blind', 'label': 'x', 'entity_ids': ['cover.office_blind']}}, {'cover.office_blind': 'shade'})
        self.load({'x': {'kind': 'blind', 'label': 'x', 'entity_ids': ['cover.hall_window']}}, {'cover.hall_window': None}, test_only=True)

    def test_runtime_class_change_refused(self):
        h = FakeHouse()
        e = REAL['handles']['sunroom_blind']['entity_ids'][0]
        h.backend.states[e]['attributes']['device_class'] = 'carport'
        r = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'open'})
        self.assertEqual((r['status'], r['reason']), ('denied', 'not_reviewed_cover'))
        self.assertEqual(h.calls, [])

    def test_cover_names_real_rollers_load_doors_refused(self):     # cloud review 1 M4, adapted: a roller BLIND is a blind
        self.load({'x': {'kind': 'blind', 'label': 'x', 'entity_ids': ['cover.blind_motor']}},
                  {'cover.blind_motor': 'shade'})
        for e in ('cover.carport', 'cover.carport_roller', 'cover.roller_door', 'cover.carport_door', 'cover.driveway', 'cover.side_gate'):
            with self.assertRaises(ValueError, msg=e):
                self.load({'x': {'kind': 'blind', 'label': 'x', 'entity_ids': [e]}}, {e: 'shutter'})
        self.load({'x': {'kind': 'blind', 'label': 'x', 'entity_ids': ['cover.lounge_door_blind']}}, {'cover.lounge_door_blind': 'shade'})

    def test_undo_rechecks_the_class(self):          # [R12-13]
        h = FakeHouse()
        e = REAL['handles']['sunroom_blind']['entity_ids'][0]
        r = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'position', 'position_percent': 50})
        self.assertEqual(h.call('atlas_confirm', {'confirmation': r['confirmation']}, last_reply=r['question'], user_text='yes')['status'], 'done')
        sent = len(h.calls)
        h.backend.states[e]['attributes']['device_class'] = 'carport'
        u = h.call('atlas_undo', {})
        if u['status'] == 'needs_confirmation':
            u = h.call('atlas_confirm', {'confirmation': u['confirmation']}, last_reply=u['question'], user_text='yes')
        self.assertEqual((u['status'], u.get('reason')), ('denied', 'changed_since'))
        self.assertEqual(len(h.calls), sent)

    def test_map_reviews_exactly_its_blinds(self):
        blinds = {e for t in REAL['handles'].values() if t['kind'] == 'blind' for e in t['entity_ids']}
        self.assertEqual(set(REAL['reviewed_covers']), blinds)
        self.assertEqual(set(REAL['reviewed_covers'].values()), {'shade'})


if __name__ == '__main__':
    unittest.main()
