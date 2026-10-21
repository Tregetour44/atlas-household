"""turn.run_turn: the order the household hears (fast timer path, model, guard, one nudge). A scripted model stands in for Atlas."""
import pathlib
import sys
import unittest
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'custom_components'))
from atlas_household.fake import SYDNEY, FakeHouse  # noqa: E402
from atlas_household.turn import NUDGE, run_turn  # noqa: E402

PM = datetime(2026, 10, 18, 13, 0, tzinfo=SYDNEY)


class Turn(unittest.TestCase):
    def run_turn(self, h, text, script, **kw):
        asked = []

        async def ask(t):
            asked.append(t)
            step = script[len(asked) - 1]
            if callable(step):
                return await step()
            return step
        out = h.loop.run_until_complete(run_turn(h.coord, text, 'conv-1', ask, **kw))
        return out, asked

    def test_fast_path_never_asks_the_model(self):
        h = FakeHouse(start=PM)
        out, asked = self.run_turn(h, 'turn the office lights off in 10 minutes', [])
        self.assertEqual((out['path'], asked), ('fast', []))
        self.assertTrue(out['reply'].startswith('Timer set'), out['reply'])
        self.assertEqual(h.calls, [])
        [(name, args, res)] = out['tool_results']
        self.assertEqual((name, args['target_handle'], res['status']), ('atlas_schedule', 'office_lights', 'scheduled'))
        self.assertIn('due_local', res)

    def test_fast_path_keeps_the_never_list(self):
        h = FakeHouse(start=PM)
        out, asked = self.run_turn(h, 'turn the office lights off in 10 minutes', [])
        self.assertEqual(out['statuses'], ['scheduled'])
        out2, asked2 = self.run_turn(h, 'turn the office lights off in 10 minutes and disarm the alarm', ["I can't do that."])
        self.assertEqual(out2['path'], 'model')          # not a whole-utterance timer match: the model and its tools handle it

    def test_claim_without_a_tool_is_nudged_once(self):
        h = FakeHouse(start=PM)
        out, asked = self.run_turn(h, 'get the office lights off for me', ["I've turned off the office lights.", "Sorry, I can't do that right now."])
        self.assertEqual((out['path'], asked), ('nudged', ['get the office lights off for me', NUDGE]))
        self.assertEqual((out['reply'], out['claims']), ("Sorry, I can't do that right now.", []))

    def test_nudge_then_tool_call_is_backed(self):
        h = FakeHouse(start=PM)
        h.set('light.office_ceiling', 'on')

        async def call_then_claim():
            await h.coord.call_tool('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, conversation_id='conv-1', user_text=NUDGE)
            return "Done: the office lights are off."
        out, asked = self.run_turn(h, 'get the office lights off for me', ["I've turned off the office lights.", call_then_claim])
        self.assertEqual((out['path'], out['claims'], out['reply']), ('nudged', [], "Done: the office lights are off."))
        self.assertEqual([(n, r['status']) for n, _a, r in out['tool_results']], [('atlas_lights', 'done')])

    def test_second_false_claim_is_still_guarded_and_never_a_third_ask(self):
        h = FakeHouse(start=PM)
        out, asked = self.run_turn(h, 'get the office lights off for me', ["I've turned off the office lights.", "Done!"])
        self.assertEqual(len(asked), 2)
        self.assertTrue(out['reply'].startswith("I haven't changed anything"), out['reply'])

    def test_backed_claim_passes_without_a_nudge(self):
        h = FakeHouse(start=PM)
        h.set('light.office_ceiling', 'on')

        async def call_then_claim():
            await h.coord.call_tool('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, conversation_id='conv-1', user_text='x')
            return "I've turned off the office lights."
        out, asked = self.run_turn(h, 'get the office lights off for me', [call_then_claim])
        self.assertEqual((out['path'], len(asked), out['claims']), ('model', 1, []))

    def test_another_tool_ran_means_no_nudge_and_no_false_nothing_changed(self):
        h = FakeHouse(start=PM)
        out, asked = self.run_turn(h, 'get the office lights off for me', ["Turned off the light"], other_tools=lambda: True)
        self.assertEqual((out['path'], len(asked)), ('model', 1))
        self.assertTrue(out['reply'].startswith("I can't confirm all of that"), out['reply'])

    def test_B16_01_no_nudge_on_a_never_list_turn(self):
        h = FakeHouse(start=PM)
        out, asked = self.run_turn(h, 'entry lights on and unlock the front door',
                                   ["I can turn the entry lights on for you. I cannot unlock the front door.", "Done: the entry lights are on."])
        self.assertEqual((out['path'], len(asked)), ('model', 1))          # guarded, never nudged
        self.assertNotIn('turn the entry lights on for you', out['reply'])
        self.assertEqual(h.calls, [])

    def test_B16_01_tool_during_nudge_uses_the_persons_words(self):
        # api.py derives user_text from the chat log and skips the nudge message: mirror that here
        h = FakeHouse(start=PM)

        async def nudged_call():
            r = await h.coord.call_tool('atlas_lights', {'target_handle': 'entry_lights', 'operation': 'on'}, conversation_id='conv-1',
                                        user_text='entry lights on and open the garage')
            return r
        r = h.loop.run_until_complete(nudged_call())
        self.assertEqual((r['status'], r.get('reason')), ('denied', 'never_list'))
        self.assertEqual(h.calls, [])                                      # the person's words still refuse the whole turn

    def test_B16_06_fast_path_error_is_said_honestly(self):
        h = FakeHouse(start=PM)

        async def boom(name, args):
            raise RuntimeError('backend gone')
        out = h.loop.run_until_complete(run_turn(h.coord, 'turn the office lights off in 10 minutes', 'conv-1', None, call_tool=boom))
        self.assertEqual((out['path'], out['reply']), ('fast', "Something went wrong, so I didn't set that timer."))

    def test_M8_lights_result_does_not_back_a_blind_claim(self):     # cloud review 1 M8, through run_turn
        h = FakeHouse(start=PM)
        h.set('light.office_ceiling', 'on')

        async def lights_then_overclaim():
            await h.coord.call_tool('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, conversation_id='conv-1', user_text='x')
            await h.coord.call_tool('atlas_blind', {'target_handle': 'sunroom_blind', 'operation': 'close'}, conversation_id='conv-1', user_text='x')
            return "I've turned off the office lights and closed the sunroom blind."
        out, asked = self.run_turn(h, 'office lights off and close the sunroom blind', [lights_then_overclaim])
        self.assertTrue(out['claims'], out)                              # the blind only got a question (needs_confirmation)
        self.assertNotIn('closed the sunroom blind', out['reply'])

    def test_plain_answer_passes(self):
        h = FakeHouse(start=PM)
        out, asked = self.run_turn(h, 'is the office light on?', ["The office light is off."])
        self.assertEqual((out['path'], out['reply'], len(asked)), ('model', "The office light is off.", 1))


if __name__ == '__main__':
    unittest.main()


class EmptyReply(unittest.TestCase):
    """C0g G12 (the Atlas-side project, 18 Oct): the model made a real change, then returned an empty reply. Never silence after a change."""
    run_turn = Turn.run_turn

    def test_g12_change_then_empty_reply_speaks_the_coordinators_summary(self):
        h = FakeHouse(start=PM)
        h.set('light.office_ceiling', 'on')
        seen = {}

        async def three_calls_then_nothing():
            c = h.coord.call_tool
            for args in ({'target_handle': 'office_lights', 'operation': 'brighten', 'brightness_percent': 80},
                         {'target_handle': 'office_lights', 'operation': 'brightness'},
                         {'target_handle': 'office_lights', 'operation': 'brightness', 'brightness_percent': 80}):
                seen.setdefault('res', []).append(await c('atlas_lights', args, conversation_id='conv-1', user_text='office lights a bit brighter'))
            return ''
        out, asked = self.run_turn(h, 'office lights a bit brighter', [three_calls_then_nothing])
        done = [r for r in seen['res'] if r['status'] == 'done']
        self.assertEqual([r['status'] == 'done' for r in seen['res']], [False, False, True], seen['res'])
        self.assertEqual(out['reply'], done[0]['summary'].strip())
        self.assertEqual((out['path'], asked), ('model', ['office lights a bit brighter']))

    def test_empty_reply_with_nothing_run(self):
        out, _ = self.run_turn(FakeHouse(start=PM), 'hmm', ['  '])
        self.assertEqual(out['reply'], "Sorry, I didn't catch that.")

    def test_empty_reply_after_only_a_refusal_says_why(self):
        h = FakeHouse(start=PM)

        async def refused_then_nothing():
            r = await h.coord.call_tool('atlas_lights', {'target_handle': 'office_lights', 'operation': 'dim', 'brightness_percent': 5},
                                        conversation_id='conv-1', user_text='dim the office')
            self.assertTrue(r.get('summary'), r)
            return ''
        out, _ = self.run_turn(h, 'dim the office', [refused_then_nothing])
        self.assertTrue(out['reply'] and out['reply'] != "Sorry, I didn't catch that.", out['reply'])
        self.assertEqual(h.calls, [])

    def test_a_non_empty_reply_is_untouched(self):
        out, _ = self.run_turn(FakeHouse(start=PM), 'hello', ['Hello.'])
        self.assertEqual(out['reply'], 'Hello.')
