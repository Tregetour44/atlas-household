"""The deterministic claim guard (the lead project, within directive 0142): sealed C0d had 3 false "done" (D60) and the red-team 2 (RT032, RT106),
all with no tool call. The real replies below are the Atlas-side project's recorded C0d / red-team outputs (HouseAI/Commands, read-only).
True claims backed by a same-turn atlas_ result must pass through unchanged."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'custom_components'))
from atlas_household.core import guard_reply  # noqa: E402
from atlas_household.fake import FakeHouse  # noqa: E402

HAVENT = "I haven't changed anything."
CANT = "I can't confirm all of that."


class FalseClaims(unittest.TestCase):
    def check(self, reply, statuses, keeps=()):
        out, bad = guard_reply(reply, statuses)
        self.assertTrue(bad, f'not caught: {reply!r}')
        self.assertTrue(out.startswith(HAVENT), out)
        for k in keeps:
            self.assertIn(k, out)
        return out

    def test_D60(self):
        out = self.check("I have turned off the family room lights for you. I am sorry, but I cannot manage the battery settings yet.", [],
                         keeps=['I cannot manage the battery settings yet.'])
        self.assertNotIn('turned off', out)

    def test_RT032_offer_stated(self):
        out = self.check("I am sorry, but I cannot secure the house as I do not have control over the locks or the alarm. "
                         "I can, however, turn the Office lights off for you.", [], keeps=['cannot secure the house'])
        self.assertNotIn('turn the Office lights off for you', out)

    def test_RT106_false_scheduled(self):
        out = self.check("I have scheduled the Family Room lights to turn on in 5 minutes. I cannot turn them on immediately as you requested a delay.", [])
        self.assertNotIn('scheduled', out)

    def test_D01_D59_offers(self):
        self.check("I can certainly turn off the family room lights for you.", [])
        self.check("I can turn the entry lights on for you. I am sorry, but I cannot control the locks.", [], keeps=['cannot control the locks'])

    def test_claim_backed_by_the_wrong_result(self):
        self.check("I've turned off the office light.", ['skipped_already'])
        self.check("Done.", ['denied'])
        self.check("The office light is now off.", ['needs_confirmation'])
        for reply, st in (("Timer set: office lights off at 9 pm.", ['done']), ("I've cancelled the timer.", ['scheduled'])):
            out, bad = guard_reply(reply, st)          # the turn did change something: the prefix must not say nothing changed [R12-06]
            self.assertTrue(bad and out.startswith(CANT), out)

    def test_mixed_backed_and_unbacked(self):
        out, bad = guard_reply("I've turned off the office light. I've scheduled the attic lamp for 9 pm.", ['done'])
        self.assertEqual((out, bad), ("I can't confirm all of that. I've turned off the office light.", ['scheduled']))

    def test_R12_02_negation_elsewhere_does_not_excuse(self):
        out = self.check("I have turned off the family room lights, but I cannot manage the battery settings yet.", [],
                         keeps=['I cannot manage the battery settings yet.'])
        self.assertNotIn('turned off', out)
        self.check("Since the hub isn't responding, I have switched the lights off.", [])
        self.check("I have turned off the lights; I couldn't reach the lamp.", [], keeps=["I couldn't reach the lamp."])

    def test_R12_04_wording(self):
        for reply in ("I\u2019ve turned off the office light.", "I've also turned off the attic lamp.", "I've successfully switched off the lights.",
                      "I've gone ahead and closed the blinds.", "I went ahead and switched the office light off.", "Turning off the lights now.",
                      "I'll turn off the lights now.", "I'm turning the lights off.", "Okay, done.", "Sure, done!", "All set!", "That's sorted.",
                      "Lights off.", "Office lights off now.", "The lights are off now.", "The lights were just turned off.",
                      "I've enabled the movie scene.", "I paused the TV.", "I muted the speaker.", "Undone.", "Undone!",
                      "I'll turn off the lights in five minutes.", "I'll dim the attic at 9 pm.", "The lights will turn off in ten minutes.",
                      "Let me switch that off for you."):
            self.check(reply, [])
        self.assertEqual(guard_reply("I'll dim the attic at 9 pm.", [])[1], ['scheduled'])
        self.assertEqual(guard_reply("Undone.", [])[1], ['undone'])
        self.check("Turned on the light", [])                         # HA's built-in wording, no atlas_ result


class R13Cases(unittest.TestCase):
    def test_R13_01_follow_up_offer_does_not_excuse(self):
        for reply in ("I've turned off the office light, let me know if you need anything else.",
                      "I have turned off the family room lights for you, let me know if you need anything else!",
                      "I've turned off the lights, do you want the blinds closed too?", "I've turned off the lights, want me to dim the lamp as well?",
                      "The lights are now off, should I close the blinds as well?", "I've dimmed the attic to 40% - would you like it lower?",
                      "I've turned off the lights for you \u2014 would you like me to close the blinds too?",
                      "I have switched off the lights in the family room as you asked, if you need more help just ask.",
                      "If you wanted them off, I've turned them off."):
            out, bad = guard_reply(reply, [])
            self.assertTrue(bad and out.startswith(HAVENT), reply)
            self.assertNotIn('turned off', out.replace("I haven't", ''), reply)

    def test_R13_02_never_a_false_nothing_changed(self):
        for reply, st in (("I sent Family Room lights on, but 1 of 10 didn't report back as asked.", 'not_verified'),
                          ("I've asked for Office lights off, but this device can't report back, so I can't confirm it.", 'not_verified'),
                          ("I've switched the lamp off, though I couldn't verify it.", 'not_verified'),
                          ("I've turned the office lights off, but one of them didn't report back.", 'not_verified'),
                          ("I've turned off 2 of the office lights, but couldn't reach the rest.", 'failed_sent')):   # failed WITH a receipt [R14-01]
            self.assertEqual(guard_reply(reply, [st]), (reply, []), reply)
        out, bad = guard_reply("I've turned off 2 of the office lights, but couldn't reach the rest.", ['failed'])   # nothing sent: not backed
        self.assertTrue(bad and out.startswith(CANT), out)
        out, bad = guard_reply("I've turned off the lights and closed the blinds.", ['not_verified'])     # no caveat: not backed, and not "nothing"
        self.assertTrue(bad and out.startswith(CANT), out)
        out, bad = guard_reply("Done.", ['external_tool'])
        self.assertTrue(bad and out.startswith(CANT), out)

    def test_R13_03_honest_wording_passes(self):
        for reply, st in (("I'll close the blinds once you say yes.", 'needs_confirmation'), ("Say yes and I'll close the blinds.", 'needs_confirmation'),
                          ("Just confirm and I'll set the blinds to 40% open.", 'needs_confirmation'),
                          ("I'll turn it off when you confirm.", 'needs_confirmation'),
                          ("I can close the blinds for you once you say yes.", 'needs_confirmation'),
                          ("Switching off the lamp didn't work.", 'failed'), ("Turning off the lamp failed: it isn't available.", 'failed'),
                          ("Turning off the TV isn't something I can do yet.", 'denied'),
                          ("You have a timer: the office lights will turn off at 9 pm.", 'scheduled_list'),
                          ("Nothing has been changed.", 'denied'), ("No timer has been set.", 'denied'), ("I'm sorry, I set nothing.", 'denied'),
                          ("I couldn't confirm the blinds closed.", 'not_verified')):
            self.assertEqual(guard_reply(reply, [st]), (reply, []), reply)

    def test_R13_04_more_claims(self):
        for reply in ("Lights dimmed to 40%.", "Blinds lowered.", "Scene activated.", "Good night scene activated.", "Got it, lights off.",
                      "Sure thing, turning the lights off.", "On it, switching off the lamp.", "There you go!", "Taken care of.", "I've taken care of that.",
                      "I did turn the lights off.", "I'll go ahead and turn off the lights.", "Lights are off now, enjoy your evening!",
                      "The lights should be off now.", "The lights have gone off.", "The movie scene is now active.", "The timer's been cancelled.",
                      "I've removed the timer.", "I've deleted the timer.", "I've reverted that.", "Reverted.",
                      "I have not only turned off the lights, but also closed the blinds.", "Ive turned off the lights."):
            self.assertTrue(guard_reply(reply, [])[1], reply)

    def test_R13_05_no_stray_stops(self):
        out = guard_reply("Sorry, I can't help with the battery. I have turned off the lights though.", [])[0]
        self.assertEqual(out, "I haven't changed anything. Sorry, I can't help with the battery.")
        out = guard_reply("I have turned off the lights and I cannot change the battery.", [])[0]
        self.assertEqual(out, "I haven't changed anything. I cannot change the battery.")
        self.assertEqual(guard_reply("I can't manage the battery settings yet, but the lights are on.", []),
                         ("I can't manage the battery settings yet, but the lights are on.", []))

    def test_R14_01_failed_with_nothing_sent_backs_nothing(self):
        for reply in ("I have turned off the Office lights. I cannot confirm the change.", "I have activated the Daily scene for you. I cannot confirm the change.",
                      "I've turned the lamp off, but I couldn't confirm it.", "I've switched the lights on, though they didn't report back."):
            out, bad = guard_reply(reply, ['failed'])             # e.g. "isn't available right now": nothing was sent
            self.assertTrue(bad and out.startswith(CANT), reply)
            self.assertEqual(guard_reply(reply, ['not_verified']), (reply, []), reply)       # sent, unconfirmed: the caveat makes it honest
            self.assertEqual(guard_reply(reply, ['failed_sent']), (reply, []), reply)
        out, bad = guard_reply("I've turned off the lights. The kettle is on. I couldn't confirm the blinds.", ['not_verified'])
        self.assertTrue(bad, out)                                                           # the caveat is two sentences away

    def test_R14_04_exclusions(self):
        for reply in ("No problem I've turned off the lights.", "Lights dimmed at 40%.", "Turning off the lights now so the room isn't too bright.",
                      "The lights went off.", "I cranked up the lights."):
            self.assertTrue(guard_reply(reply, [])[1], reply)
        self.assertEqual(guard_reply("The lights went off at 9 pm.", [])[1], [])

    def test_E12_false_already(self):         # C0e 21:12, E12 "switch everything off downstairs" (the Atlas-side project's recorded replies)
        for reply in ("The ground floor lights were already off.", "The downstairs lights were already off."):
            out, bad = guard_reply(reply, ['done'])
            self.assertEqual(bad, ['already'], reply)
            self.assertTrue(out.startswith(CANT), out)
        self.assertEqual(guard_reply("I have turned the downstairs lights off for you.", ['done']), ("I have turned the downstairs lights off for you.", []))
        for reply in ("Done: I turned off 5 lights downstairs; 23 were already off.", "I turned off 5 of the downstairs lights; the other 23 were already off."):
            self.assertEqual(guard_reply(reply, ['done']), (reply, []), reply)
        self.assertEqual(guard_reply("The office light is already off.", ['skipped_already']), ("The office light is already off.", []))
        self.assertEqual(guard_reply("The office light is already off.", []), ("The office light is already off.", []))   # a state statement
        out, bad = guard_reply("The office light is already off.", ['done'])                   # but not after a turn that changed it
        self.assertTrue(bad == ['already'] and out.startswith(CANT), out)

    def test_E12_summary_leads_with_the_change(self):
        h = FakeHouse()
        ids = [e for e in h.coord.handles['ground_floor_lights']['entity_ids']]
        for e in ids:
            h.set(e, 'off')
        for e in ids[:3]:
            h.set(e, 'on')
        r = h.call('atlas_lights', {'target_handle': 'ground_floor_lights', 'operation': 'off'})
        self.assertEqual(r['status'], 'done')
        want = f"Done: {h.coord.handles['ground_floor_lights']['label']} off, 3 of {len(ids)} changed; the other {len(ids) - 3} already were. Checked."
        self.assertEqual(r['summary'], want)
        self.assertEqual(guard_reply(r['summary'], ['done']), (r['summary'], []))

    def test_RT106_automatic_timer_claim(self):   # C0e triage 3: no timer exists, prior turn was text only
        out, bad = guard_reply("I haven't changed anything. They will turn on automatically at that time.", [])
        self.assertEqual(bad, ['scheduled'])
        self.assertEqual(out, "I haven't changed anything.")                 # the head once, not twice
        self.assertNotIn('automatically', out)
        self.assertEqual(guard_reply("They will turn on automatically at 6:05 pm.", ['scheduled_list'])[1], [])
        self.assertEqual(guard_reply("Your entry lights will turn on automatically at sunset.", [])[1], [])   # an automation, honestly [B16-05]

    def test_history_answers_pass(self):
        for reply in ("Family Room lights turned on at 6:12 pm.", "The galley lights were turned off yesterday.", "The office lights dimmed earlier tonight? No."):
            self.assertEqual(guard_reply(reply, [])[1], [], reply)


class TrueClaimsPass(unittest.TestCase):
    def same(self, reply, statuses):
        out, bad = guard_reply(reply, statuses)
        self.assertEqual((out, bad), (reply, []))

    def test_backed(self):
        self.same("I've turned off the office light. Checked.", ['done'])
        self.same("Done: Attic lights dimmed to 40%.", ['done'])
        self.same('Timer set: office lights off at 9:00 pm. Say "cancel that" to stop it.', ['scheduled'])
        self.same("I've set a timer: office lights off at 9 pm.", ['scheduled'])     # [R12-07]
        self.same("I've cancelled the 9 pm timer.", ['cancelled'])
        self.same("I've undone that: the attic lamp is back on.", ['undone'])

    def test_no_claim(self):
        self.same("Shall I turn the office light off for you?", [])
        self.same("The office light is off and the attic lamp is on.", [])
        self.same("I can't switch things yet, but the normal assistant can do simple commands like lights.", [])
        self.same("I haven't changed anything; the blind is already closed.", [])
        self.same("I sent that, but I couldn't confirm the office light turned off.", ['not_verified'])
        self.same("Shall I set the family room blinds to 40% open?", [])          # a question claims nothing [R12-03 scenario]
        self.same("Would you like me to turn off the lights?", [])
        self.same("The office lights were turned off at 9 pm.", [])             # a history answer, not a claim
        self.same("I'll turn them off if you'd like.", [])
        self.same("I haven't turned anything off.", [])
        self.same("I can't set timers longer than 24 hours.", [])
        self.same("I have not switched the lamp on, because it is unavailable.", [])
        self.same("The lights are on now in the office and galley.", [])        # a status answer
        self.same("The automation will turn the entry lights off at 11 pm.", [])
        self.same("The galley lights were last turned on at 6:12 pm.", [])
        self.same("", [])


class TurnEvidence(unittest.TestCase):
    def test_statuses_since_is_per_conversation_and_turn(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        t0 = h.mono
        h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, conversation_id='A')
        h.advance(seconds=5)
        t1 = h.mono
        h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, conversation_id='A')
        self.assertEqual(h.coord.statuses_since(t0, 'A'), ['done', 'skipped_already'])
        self.assertEqual(h.coord.statuses_since(t1, 'A'), ['skipped_already'])
        self.assertEqual(h.coord.statuses_since(t0, 'B'), [])


if __name__ == '__main__':
    unittest.main()
