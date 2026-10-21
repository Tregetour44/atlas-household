"""Optional narrow fixes for MINOR over-refusals (cloud robustness job, 21 Oct; GAPS.md G14-G17). Synthetic phase-2 rehearsal map."""
import json
import pathlib
import sys
import unittest
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'custom_components'))
from atlas_household.core import NEVER_WORDS  # noqa: E402
from atlas_household.fake import SYDNEY, FakeHouse  # noqa: E402

MAP = json.loads((ROOT / 'tests' / 'fixtures' / 'targets.phase2-rehearsal.json').read_text(encoding='utf-8'))
SUN, WIN, DOOR = 'cover.blind_motor', 'cover.blind_motor_2', 'cover.blind_motor_3'


def house():
    h = FakeHouse(targets=json.loads(json.dumps(MAP)), start=datetime(2026, 10, 21, 19, 30, tzinfo=SYDNEY))
    h.set(SUN, 'open', position_percent=100)
    h.calls.clear()
    return h


class G14_G15_NeverListWords(unittest.TestCase):
    def test_in_one_hour(self):
        for text in ['turn off the carport lights in one hour', 'carport lights on in one minute', 'carport lights off at one']:
            self.assertFalse(NEVER_WORDS.search(text), text)
        for text in ['carport lights off and close that one', 'carport lights off and the other one', 'turn the carport lights off, then one more thing, open it']:
            self.assertTrue(NEVER_WORDS.search(text), text)

    def test_the_blind_on_the_door(self):
        for text in ['close the blind on the family room door', 'open the blind on the door', 'put the blinds on the family room door down']:
            self.assertFalse(NEVER_WORDS.search(text), text)
        for text in ['close the blind on the door and open the door', 'close the blind and the door', 'open the blind on the garage door',
                     'close the blind on the door then lock the door']:
            self.assertTrue(NEVER_WORDS.search(text), text)


class G16_WhichBlindVocabulary(unittest.TestCase):
    def test_now_clear(self):
        h = house()
        cases = {'drop the sunroom blind': {SUN}, 'put the door blind at 80 per cent': {DOOR}, 'close the blinds everywhere': {SUN, WIN, DOOR},
                 'good night and close all the blinds': {SUN, WIN, DOOR}, 'close the sunroom blind and pause the TV': {SUN},
                 'sunroom blind halfway and the sunroom lights on': {SUN}}
        for text, want in cases.items():
            self.assertEqual(h.coord._blind_scope(text), want, text)

    def test_still_unclear(self):
        h = house()
        for text in ['close the sunroom blind at 9', 'close all the blinds in the bedroom', 'close the blinds and curtains in the bedroom',
                     'turn off the galley lights and close all the blinds', 'close the blind', 'drop the blinds', 'close all the blinds but the sunroom']:
            self.assertIsNone(h.coord._blind_scope(text), text)
        self.assertTrue(NEVER_WORDS.search('close all the blinds and the garage'))


class G17_PlainYesToAtlasQuestion(unittest.TestCase):
    Q = "I'm not sure which blind you mean. Would you like me to open the sunroom blind?"

    def call(self, h, words, op, last=Q, handle='sunroom_blind'):
        return h.call('atlas_blind', {'target_handle': handle, 'operation': op}, user_text=words, last_reply=last)

    def test_yes_moves_the_blind_asked_about(self):
        h = house()
        h.set(SUN, 'closed', position_percent=0)
        self.assertEqual(self.call(h, 'yes please', 'open')['status'], 'done')

    def test_anything_else_still_asks(self):
        h = house()
        h.set(SUN, 'closed', position_percent=0)
        self.assertEqual(self.call(h, 'yes', 'close')['reason'], 'which_blind')                       # the other direction
        self.assertEqual(self.call(h, 'yes', 'open', handle='family_room_blinds')['reason'], 'which_blind')   # another blind
        self.assertEqual(self.call(h, 'sure, and the others', 'open')['reason'], 'which_blind')       # not a plain yes
        self.assertEqual(self.call(h, 'yes', 'open', last='The sunroom blind is closed.')['reason'], 'which_blind')   # no question
        self.assertEqual(self.call(h, 'yes', 'open', last='Which one: the sunroom blind or the family room door blind?')['reason'], 'which_blind')
        self.assertEqual(h.calls, [])


class G20_EveryLightInTheHouse(unittest.TestCase):
    def test_in_the_house_covers_the_floors(self):
        h = house()
        for text in ['turn every light in the house off', 'all the lights in the house off', 'turn off all the lights in the home']:
            r = h.call('atlas_lights', {'target_handle': 'ground_floor_lights', 'operation': 'off'}, user_text=text)
            self.assertNotEqual(r['status'], 'needs_choice', text)
        for text in ['all the lights in the office off', 'every light in the galley off']:
            r = h.call('atlas_lights', {'target_handle': 'ground_floor_lights', 'operation': 'off'}, user_text=text)
            self.assertEqual(r['status'], 'needs_choice', text)


if __name__ == '__main__':
    unittest.main()
