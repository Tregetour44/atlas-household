"""The scene, blind and read-only fast paths (cloud robustness job, 21 Oct): strict whole utterances only, every coordinator check kept,
the which-blind rule taken from Coordinator._blind_scope alone, anything unclear on the model path. On the synthetic phase-2 rehearsal map
(tests/fixtures/targets.phase2-rehearsal.json: atlas-current/targets.synthetic-phase2.json with the live scene handles and synthetic
reviewed members, built by rehearsal/fixture.py)."""
import json
import pathlib
import sys
import unittest
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'custom_components'))
from atlas_household.fake import SYDNEY, FakeHouse  # noqa: E402
from atlas_household.fastpath import parse_blind, parse_scene  # noqa: E402
from atlas_household.readings import check_readings, parse_question  # noqa: E402
from atlas_household.turn import run_turn  # noqa: E402

MAP = json.loads((ROOT / 'tests' / 'fixtures' / 'targets.phase2-rehearsal.json').read_text(encoding='utf-8'))
EVENING = datetime(2026, 10, 21, 19, 30, tzinfo=SYDNEY)
SUN, WIN, DOOR = 'cover.blind_motor', 'cover.blind_motor_2', 'cover.blind_motor_3'


def house(targets=None):
    h = FakeHouse(targets=json.loads(json.dumps(targets or MAP)), start=EVENING)
    for e in (SUN, WIN, DOOR):
        h.set(e, 'open', position_percent=100)
    h.set('light.family_room_lamp', 'on', brightness_percent=60)
    h.backend.states['sensor.example_01'] = {'state': '64', 'attributes': {}, 'last_changed': 'r'}
    h.backend.states['sensor.example_11'] = {'state': '23.1', 'attributes': {}, 'last_changed': 'r'}
    h.backend.states['sensor.example_12'] = {'state': '22.4', 'attributes': {}, 'last_changed': 'r'}
    h.backend.states['weather.example_37'] = {'state': 'partlycloudy', 'attributes': {'temperature': 24.5}, 'last_changed': 'r'}
    h.calls.clear()
    return h


async def _no_model(_t):
    raise AssertionError('the model was asked')


def turn(h, text, model=_no_model):
    return h.loop.run_until_complete(run_turn(h.coord, text, 'conv-1', model))


class Scenes(unittest.TestCase):
    YES = {'good night': 'good_night', 'Good night.': 'good_night', 'goodnight, thanks atlas': 'good_night', 'hey atlas good night': 'good_night',
           'run good night': 'good_night', 'put good night on': 'good_night', 'good night scene': 'good_night', 'night night': 'good_night',
           'could you run good night please': 'good_night', 'ok atlas start good night': 'good_night', 'good night mode': 'good_night',
           'wind down': 'wind_down', "let's wind down": 'wind_down', 'time to wind down': 'wind_down', 'wind-down mode': 'wind_down',
           'could you put the wind down scene on': 'wind_down', 'wind down time': 'wind_down', 'activate wind down please': 'wind_down'}
    NO = ['good night at 10', 'run good night in half an hour', 'good night scene in 20 minutes', "don't run good night", 'is good night on?',
          'what does good night do', 'good night and close the blinds', 'good night, see you in the morning', 'good night and lock up',
          'run the deck party scene', 'daily', 'night', 'good', 'wind down the blinds', 'stop wind down', 'undo good night', 'good night?',
          'cancel wind down', 'did wind down run', 'good night everyone, turn off the lights']

    def test_whole_utterances_name_one_reviewed_scene(self):
        for text, want in self.YES.items():
            self.assertEqual(parse_scene(text, MAP['handles']), {'recipe_handle': want}, text)

    def test_anything_else_goes_to_the_model(self):
        for text in self.NO:
            self.assertIsNone(parse_scene(text, MAP['handles']), text)

    def test_unreviewed_or_disabled_scenes_are_never_fast(self):
        hs = json.loads(json.dumps(MAP['handles']))
        hs['good_night'].pop('expect')
        hs['wind_down']['enabled'] = False
        self.assertIsNone(parse_scene('good night', hs))
        self.assertIsNone(parse_scene('wind down', hs))

    def test_run_turn_runs_the_scene_through_the_coordinator(self):
        h = house()
        out = turn(h, 'good night')
        self.assertEqual((out['path'], out['tool'], out['statuses']), ('fast', 'atlas_scene', ['done']))
        self.assertTrue(out['reply'].startswith('Done: the Good Night scene'), out['reply'])
        self.assertEqual(h.state('light.family_room_lamp')['state'], 'off')


class Blinds(unittest.TestCase):
    def parse(self, text, h=None):
        h = h or house()
        return parse_blind(text, h.coord.handles, h.coord._blind_scope)

    def test_named_plural_and_all(self):
        cases = {'close the sunroom blind': [('sunroom_blind', 'close', None)], 'sunroom blind down': [('sunroom_blind', 'close', None)],
                 'pull the window blind down': [('family_room_window_blind', 'close', None)], 'door blind up': [('family_room_door_blind', 'open', None)],
                 'raise the sunroom blind': [('sunroom_blind', 'open', None)], 'close the blind in the sunroom': [('sunroom_blind', 'close', None)],
                 'close the family room blinds': [('family_room_blinds', 'close', None)],
                 'open the family room window and door blinds': [('family_room_blinds', 'open', None)],
                 'close the sunroom blind to 30%': [('sunroom_blind', 'position', 30)], 'set the door blind to forty percent': [('family_room_door_blind', 'position', 40)],
                 'window blind 75% open': [('family_room_window_blind', 'position', 75)], 'sunroom blind halfway': [('sunroom_blind', 'position', 50)],
                 'set the sunroom blind to 100%': [('sunroom_blind', 'open', None)], 'sunroom blind to 0%': [('sunroom_blind', 'close', None)],
                 'close all the blinds': [('family_room_blinds', 'close', None), ('sunroom_blind', 'close', None)],
                 'hey atlas open every blind': [('family_room_blinds', 'open', None), ('sunroom_blind', 'open', None)],
                 'close the sunroom and family room blinds': [('family_room_blinds', 'close', None), ('sunroom_blind', 'close', None)]}
        for text, want in cases.items():
            got = self.parse(text)
            self.assertEqual([(a['target_handle'], a['operation'], a.get('position_percent')) for a in got or []], want, text)

    def test_unclear_or_anything_else_goes_to_the_model(self):
        for text in ['close the blind', 'close the blinds', 'close both blinds', 'close the family room blind', 'close the living room one', 'shut it',
                     'close them all', 'close the blinds except the sunroom', 'close all the blinds but not the sunroom one', 'only close the door blind',
                     'close the sunroom blind at 9', 'close the sunroom blind in 10 minutes', 'close the sunroom blind tonight', 'close the sunroom blind a bit',
                     'lower the sunroom blind a little more', 'open the sunroom blind by 10%', 'sunroom blind 30% closed', 'is the sunroom blind closed',
                     "don't close the sunroom blind", 'close the sunroom blind and turn off the lights', 'close the sunroom blind and open the window blind',
                     'close the sunroom blind then open it at 1 pm', 'close the garage', 'close the garage door blind', 'close the door blind and the garage',
                     'too much sun in the sunroom', 'draw the sunroom blind', 'close the office blind', 'close the sunroom blind?', 'open the sunroom blind back up',
                     'close the sunroom blind 9', 'leave the sunroom blind open', 'keep the window blind closed', 'close all the blinds and lock up',
                     'good night and close all the blinds', 'turn the sunroom blind off']:
            self.assertIsNone(self.parse(text), text)

    def test_never_with_the_yes_question_map(self):
        h = FakeHouse(start=EVENING)                    # targets.json: blind_confirm on (a yes each time): the blind path never runs
        out = h.loop.run_until_complete(run_turn(h.coord, 'close the sunroom blind', 'conv-1', lambda _t: _model_says('Close it?')))
        self.assertEqual(out['path'], 'model')

    def test_run_turn_all_the_blinds_two_calls_both_summaries(self):
        h = house()
        h.set(SUN, 'closed', position_percent=0)
        out = turn(h, 'close all the blinds')
        self.assertEqual((out['path'], [r['status'] for _n, _a, r in out['tool_results']]), ('fast', ['done', 'skipped_already']))
        self.assertEqual(out['reply'], "Done: Family room blinds closed. Checked. Sunroom Blind is already closed. I didn't change anything.")
        self.assertEqual({e: h.state(e)['attributes']['current_position'] for e in (SUN, WIN, DOOR)}, {SUN: 0, WIN: 0, DOOR: 0})

    def test_the_coordinator_checks_still_run(self):
        h = house()
        h.backend.states[SUN]['attributes']['device_class'] = 'garage'          # no longer the reviewed class: refused, said as such
        out = turn(h, 'close the sunroom blind')
        self.assertEqual((out['path'], out['statuses']), ('fast', ['denied']))
        self.assertEqual(h.calls, [])

    def test_which_blind_question_names_only_enabled_blinds(self):
        h = house()
        r = h.call('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'close'}, user_text='close the blind')
        self.assertEqual(r['reason'], 'which_blind')
        self.assertNotIn('office', r['summary'])
        self.assertEqual(h.coord._blind_scope('close all the blinds'), {SUN, WIN, DOOR})       # the office blind is not enabled


async def _model_says(text):
    return text


class Readings(unittest.TestCase):
    R = MAP['readings']

    def test_questions(self):
        cases = {"what's the battery at?": ('battery', None), 'hows the battery holding up': ('battery', None), 'How full is the battery?': ('battery', None),
                 'battery level?': ('battery', None), 'how warm is it inside?': ('inside', None), "what's the temperature inside": ('inside', None),
                 'whats the temp': ('outside', None), "What's the weather doing?": ('outside', None), 'how hot is it outside': ('outside', None),
                 'how warm is the attic': ('room', 'the attic'), "what's the temp in bedroom south": ('room', 'Bedroom South')}
        for text, want in cases.items():
            self.assertEqual(parse_question(text, self.R), want, text)

    def test_anything_else_goes_to_the_model(self):
        for text in ['whats the weather like tomorrow', 'will the battery last the night', 'is the battery charging', 'should i run the ac',
                     'is the credit safe?', 'how much solar did we make today', "what's the battery at and turn off the lights", 'charge the battery',
                     'how warm is the garage', 'is it hot outside', 'how is the home', 'what kwh is that equal to', 'why is the battery low',
                     "what's the temperature in the kitchen", 'set the battery to 50%', 'how warm was it yesterday']:
            self.assertIsNone(parse_question(text, self.R), text)

    def test_answers_from_fresh_states_and_unavailable_is_said(self):
        h = house()
        self.assertEqual(turn(h, "what's the battery at?")['reply'], 'The home battery is at 64%.')
        self.assertEqual(turn(h, 'how warm is it inside')['reply'], 'Inside, the attic is 23.1 degrees and Bedroom South is 22.4 degrees.')
        self.assertEqual(turn(h, 'whats the temp')['reply'], "It's 24.5 degrees outside and partly cloudy.")
        self.assertEqual(turn(h, 'how warm is the attic')['reply'], 'The attic is 23.1 degrees.')
        h.backend.states['sensor.example_01']['state'] = 'unavailable'
        out = turn(h, 'battery?')
        self.assertEqual((out['path'], out['reply'], out['tool_results']), ('fast', "The battery reading isn't available right now.", []))
        self.assertEqual(h.calls, [])

    def test_a_map_without_readings_never_answers_here(self):
        m = json.loads(json.dumps(MAP))
        m.pop('readings')
        h = house(m)
        out = h.loop.run_until_complete(run_turn(h.coord, "what's the battery at?", 'conv-1', lambda _t: _model_says('It is at 64%.')))
        self.assertEqual(out['path'], 'model')

    def test_readings_are_read_only_domains(self):
        for bad in ({'battery': {'entity_id': 'light.office_ceiling'}}, {'battery': {'entity_id': 'lock.front_door'}}, {'outside': {'entity_id': 'sensor.x'}},
                    {'inside': [{'entity_id': 'sensor.x'}]}, {'credit': {'entity_id': 'sensor.x'}}, {'battery': {'entity_id': 'cover.blind_motor'}}):
            with self.assertRaises(ValueError, msg=bad):
                check_readings(bad)


class Switches(unittest.TestCase):
    def test_fast_paths_can_be_turned_off_in_the_map(self):
        m = json.loads(json.dumps(MAP))
        m['fast_paths'] = ['timer', 'level']
        h = house(m)
        for text in ('good night', 'close the sunroom blind', "what's the battery at?"):
            out = h.loop.run_until_complete(run_turn(h.coord, text, 'conv-1', lambda _t: _model_says('Sorry, I can only do lights.')))
            self.assertEqual(out['path'], 'model', text)
        with self.assertRaises(ValueError):
            house({**m, 'fast_paths': ['timer', 'everything']})


if __name__ == '__main__':
    unittest.main()
