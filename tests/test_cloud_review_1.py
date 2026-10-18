"""Cloud review 1 (independent review of main at ccbacb4). Each class is one finding in REVIEW.md (id in the class docstring).
Every test here FAILS on ccbacb4 and passes with patches/0001-0004 applied; the ordinary-turn controls pass on both.
No test weakens a rule: the controls re-assert existing behaviour next to each fix."""
import asyncio
import pathlib
import sys
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'custom_components'))
import atlas_household  # noqa: E402
from atlas_household.core import Coordinator, guard_reply  # noqa: E402
from atlas_household.fake import SYDNEY, FakeHouse, MemoryStore  # noqa: E402

HAVENT = "I haven't changed anything."
CANT = "I can't confirm all of that."
PKG = ROOT / 'custom_components' / 'atlas_household'


# ---------------------------------------------------------------- never-list ----------------------------------------------------------------
class M2_NeverWordsGaps(unittest.TestCase):
    """M2: never-list subjects the whole-turn refusal misses, so a mixed request is partly done."""
    MISSED = ['office light on and open the garages', 'office light on and close both garages', 'office light on and slide the deadbolt',
              'office light on and engage the latch', 'office light on and padlock the shed', 'office light on and silence the siren',
              'office light on and make the house secure', 'office light on and switch to off-peak', 'office light on and check the electricity price',
              'office light on and turn off the mains', 'office light on and stop the Tesla charging', 'office light on and pause the Fronius',
              'office light on and set the SolarEdge', 'office light on and buzz me in', 'office light on and check the kWh today',
              'office light on and use the peak rate']

    def test_missed_never_subjects_refuse_the_whole_turn(self):
        for text in self.MISSED:
            h = FakeHouse()
            r = h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, user_text=text)
            self.assertEqual((r['status'], r.get('reason')), ('denied', 'never_list'), text)
            self.assertEqual(h.calls, [], text)

    def test_control_ordinary_turns_still_work(self):
        for text in ('turn on the garage light', 'open the blinds to let the light in', 'turn the main lights on', 'lights on in the workshop',
                     'turn on the office light at peak brightness please', 'office lights on'):
            h = FakeHouse()
            self.assertEqual(h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'}, user_text=text)['status'], 'done', text)


class M3_CancelInMixedTurn(unittest.TestCase):
    """M3: atlas_cancel is not in ACTING, so 'cancel that and unlock the front door' cancels the timer (the turn is partly done)."""
    def test_cancel_is_refused_in_a_never_list_turn(self):
        h = FakeHouse()
        s = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, user_text='office lights off in 10 minutes')
        self.assertEqual(s['status'], 'scheduled')
        r = h.call('atlas_cancel', {}, user_text='cancel that and unlock the front door')
        self.assertEqual((r['status'], r.get('reason')), ('denied', 'never_list'))
        self.assertEqual([t['state'] for t in h.coord.data['tasks']], ['pending'])

    def test_control_plain_cancel_and_list_still_work(self):
        h = FakeHouse()
        h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 10}, user_text='office lights off in 10 minutes')
        self.assertEqual(h.call('atlas_scheduled', {}, user_text="what's scheduled, and is the alarm on?")['status'], 'scheduled_list')   # read-only
        self.assertEqual(h.call('atlas_cancel', {}, user_text='cancel that')['status'], 'cancelled')


class M4_MapCoverNames(unittest.TestCase):
    """M4: the map's never-list (FORBIDDEN) misses garage/carport/driveway/shed/door covers when the reviewed class is a blind class."""
    def load(self, e, cls):
        Coordinator({'handles': {'x': {'kind': 'blind', 'label': 'x', 'entity_ids': [e]}}, 'reviewed_covers': {e: cls}}, None, MemoryStore(), None, SYDNEY)

    def test_door_like_cover_names_rejected(self):
        for e, cls in (('cover.garage', 'shutter'), ('cover.garage_roller', 'shutter'), ('cover.carport_door', 'shutter'),
                       ('cover.driveway', 'awning'), ('cover.shed_door', 'shutter'), ('cover.laundry_door', 'curtain')):
            with self.assertRaises(ValueError, msg=e):
                self.load(e, cls)

    def test_control_blinds_still_load(self):
        for e in ('cover.blind_motor', 'cover.family_room_door_blind', 'cover.office_roller_blind', 'cover.hall_window'):
            self.load(e, 'shade')


# ---------------------------------------------------------------- claim guard ----------------------------------------------------------------
class M5_GuardMissesCommonShapes(unittest.TestCase):
    """M5: false claims on common reply shapes that the guard passes through with no tool call."""
    def test_caught(self):
        for reply in ("Timer's set for 9 pm.", "Timer's been set: office lights off at 9 pm.", "Your lights will switch off in 10 minutes.",
                      "Office lights will turn off at 9 pm.", "Would you like me to close the blinds too, now that I've turned off the lights?",
                      "Is there anything else, now that I've switched off the lights?"):
            out, bad = guard_reply(reply, [])
            self.assertTrue(bad, f'not caught: {reply!r}')
            self.assertTrue(out.startswith(HAVENT), out)

    def test_control_honest_questions_pass(self):
        for reply in ("Shall I put the lights on?", "Would you like me to set a timer for 9 pm?", "Do you want the blinds closed now that it's dark?",
                      "Should I turn them off, since you're heading out?", "Now that the lights are on, shall I close the blinds?"):
            self.assertEqual(guard_reply(reply, []), (reply, []), reply)


class M6_TimerListBacksPastTimerClaims(unittest.TestCase):
    """M6: a timer LIST (scheduled_list) backs "I've set a timer" / "Timer set", so a timer the model never set passes as set."""
    def test_list_does_not_back_a_set(self):
        for reply in ("I've set a timer: office lights off at 9 pm.", "Timer set: office lights off at 9 pm.", "I've scheduled the attic lamp for 9 pm."):
            out, bad = guard_reply(reply, ['scheduled_list'])
            self.assertEqual(bad, ['scheduled'], reply)
            self.assertTrue(out.startswith(HAVENT), out)

    def test_control_list_still_backs_what_will_happen(self):
        for reply in ("You have one timer: the office lights will turn off at 9 pm.", "The office lights will turn off at 9 pm."):
            self.assertEqual(guard_reply(reply, ['scheduled_list']), (reply, []), reply)


class M7_GuardRewritesHonestTimerReplies(unittest.TestCase):
    """M7: honest, tool-backed timer and cancel replies are rewritten to "I can't confirm all of that." (and the true part dropped)."""
    def test_backed_replies_pass_unchanged(self):
        for reply, st in (("Done! The office lights will switch off at 9 pm.", 'scheduled'),
                          ("All set, the office lights will turn off in 10 minutes.", 'scheduled'),
                          ("I've set the office lights to turn off at 9 pm.", 'scheduled'),
                          ("Done, I've cancelled the timer.", 'cancelled'), ("I've stopped the 9 pm timer.", 'cancelled'),
                          ("I've turned off the timer.", 'cancelled'), ("Sorted, the timer is cancelled.", 'cancelled')):
            self.assertEqual(guard_reply(reply, [st]), (reply, []), reply)

    def test_control_same_replies_unbacked_are_caught(self):
        for reply in ("Done! The office lights will switch off at 9 pm.", "I've set the office lights to turn off at 9 pm.", "I've turned off the timer.",
                      "Done, I've cancelled the timer."):
            out, bad = guard_reply(reply, [])
            self.assertTrue(bad and out.startswith(HAVENT), reply)
        out, bad = guard_reply("Done.", ['denied'])
        self.assertTrue(bad and out.startswith(HAVENT), out)
        out, bad = guard_reply("I've turned off the office light.", ['scheduled'])        # a timer never backs a "done now" claim
        self.assertTrue(bad and out.startswith(CANT), out)


class M8_GuardEvidenceIsKindLevel(unittest.TestCase):
    """M8: evidence is a bag of statuses, so a lights 'done' backs "...and closed the blinds" while the blind still waits for its yes."""
    def test_blind_claim_needs_blind_evidence(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        h.set('cover.blind_motor_4', 'open', position_percent=100)
        t0 = h.mono
        self.assertEqual(h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'}, turn='t9', user_text='office off, close the blind')['status'], 'done')
        self.assertEqual(h.call('atlas_blind', {'target_handle': 'office_blind', 'operation': 'close'}, turn='t9', user_text='office off, close the blind')['status'],
                         'needs_confirmation')
        ev = h.coord.evidence_since(t0, 'conv-1')
        out, bad = guard_reply("I've turned off the office lights and closed the office blind.", ev)
        self.assertTrue(bad, out)
        self.assertTrue(out.startswith(CANT), out)
        self.assertEqual(guard_reply("I've turned off the office lights.", ev), ("I've turned off the office lights.", []))

    def test_tool_level_backing(self):
        self.assertTrue(guard_reply("The Daily scene is now active.", [('atlas_lights', 'done')])[1])
        self.assertTrue(guard_reply("I've closed the office blind.", [('atlas_lights', 'done')])[1])
        for reply, ev in (("I've closed the office blind.", [('atlas_confirm', 'done')]), ("I've turned off the lights.", [('atlas_scene', 'done')]),
                          ("I've put the blind back.", [('atlas_confirm', 'undone')]), ("Done.", [('atlas_lights', 'done')])):
            self.assertEqual(guard_reply(reply, ev), (reply, []), reply)


class m3_GuardPhrasingGaps(unittest.TestCase):
    """m3: less common phrasings the guard misses (MINOR)."""
    def test_caught(self):
        for reply in ("I've flicked the lights off.", "I flipped the office lights on.", "I've got the lights off for you.", "Here you go, lights on.",
                      "The office lights should now be off.", "Not to worry I've turned the lights off.", "In 10 minutes, the office lights will turn off.",
                      "I'll turn the lights off when you go to bed."):
            out, bad = guard_reply(reply, [])
            self.assertTrue(bad, f'not caught: {reply!r}')
            self.assertTrue(out.startswith(HAVENT), out)

    def test_control_conditional_offers_still_pass(self):
        for reply in ("I'll close the blinds once you say yes.", "I'll turn it off when you confirm.", "I can close the blinds for you once you say yes.",
                      "I'll turn them off if you'd like.", "No need, the office light is already off."):
            self.assertEqual(guard_reply(reply, ['needs_confirmation']), (reply, []), reply)


# ---------------------------------------------------------------- timers, undo, scope ----------------------------------------------------------------
class M9_SameMinuteTimers(unittest.TestCase):
    """M9: two timers due together; the blind's read-back (blinds take tens of seconds) makes the second one "late", so it is cancelled
    although Home Assistant was up the whole time."""
    def house(self):
        h = FakeHouse()
        orig = h.backend.wait_for

        async def slow(eid, pred, timeout):          # a real blind takes ~40 s to travel and read back as asked
            if eid.startswith('cover.'):
                h.advance(seconds=40)
            return await orig(eid, pred, timeout)
        h.backend.wait_for = slow
        return h

    def test_both_run(self):
        h = self.house()
        q = h.call('atlas_schedule', {'target_handle': 'office_blind', 'operation': 'open', 'at_time': '21:00'}, user_text='open the office blind at 9 pm')
        self.assertEqual(h.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=q['question'])['status'], 'scheduled')
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'deck_lights', 'operation': 'on', 'at_time': '21:00'}, user_text='deck lights on at 9 pm')['status'],
                         'scheduled')
        h.advance(minutes=90)                         # 21:00 Sydney
        self.assertEqual([x['status'] for x in h.tick()], ['done', 'done'])
        self.assertEqual(h.state('light.flood_lamp')['state'], 'on')

    def test_control_really_late_is_still_cancelled(self):
        h = self.house()
        h.call('atlas_schedule', {'target_handle': 'deck_lights', 'operation': 'on', 'at_time': '21:00'}, user_text='deck lights on at 9 pm')
        h.advance(minutes=90, seconds=31)
        self.assertEqual([x['status'] for x in h.tick()], ['cancelled_missed'])
        self.assertEqual(h.calls, [])


class M10_UndoCrossesConversations(unittest.TestCase):
    """M10: "undo that" in one room undoes the latest action from ANY conversation (cancel is scoped per conversation [R4-04]; undo isn't)."""
    def test_undo_only_what_was_done_here(self):
        h = FakeHouse()
        h.call('atlas_lights', {'target_handle': 'family_room_lights', 'operation': 'on'}, conversation_id='kitchen', user_text='family room lights on')
        sent = len(h.calls)
        u = h.call('atlas_undo', {}, conversation_id='bedroom', user_text='undo that')
        self.assertNotEqual(u['status'], 'undone')
        self.assertEqual(len(h.calls), sent)
        self.assertEqual(h.state('light.family_room_lamp')['state'], 'on')

    def test_control_same_conversation_and_own_timer(self):
        h = FakeHouse()
        h.call('atlas_lights', {'target_handle': 'family_room_lights', 'operation': 'on'}, conversation_id='kitchen', user_text='family room lights on')
        self.assertEqual(h.call('atlas_undo', {}, conversation_id='kitchen', user_text='undo that')['status'], 'undone')
        h.call('atlas_schedule', {'target_handle': 'attic_lamp', 'operation': 'on', 'in_minutes': 1}, conversation_id='attic', user_text='attic lamp on in a minute')
        h.advance(minutes=1)
        self.assertEqual(h.tick()[0]['status'], 'done')
        self.assertEqual(h.call('atlas_undo', {}, conversation_id='attic', user_text='undo that')['status'], 'undone')


class M11_FloorOverreach(unittest.TestCase):
    """M11: a floor-wide or whole-outside handle runs although the person named one room or one lamp (14 lights for "the family room lamp")."""
    def test_floor_handle_needs_floor_words(self):
        h = FakeHouse()
        r = h.call('atlas_lights', {'target_handle': 'ground_floor_lights', 'operation': 'on'}, user_text='turn on the family room lamp')
        self.assertEqual(r['status'], 'needs_choice')
        self.assertEqual(h.calls, [])
        r = h.call('atlas_schedule', {'target_handle': 'upstairs_lights', 'operation': 'off', 'in_minutes': 10}, user_text='office light off in 10 minutes')
        self.assertEqual(r['status'], 'needs_choice')
        self.assertEqual(h.coord.data['tasks'], [])
        r = h.call('atlas_lights', {'target_handle': 'outside_lights', 'operation': 'on'}, user_text='turn the deck lights on')
        self.assertEqual(r['status'], 'needs_choice')

    def test_control_scope_named(self):
        for handle, text in (('upstairs_lights', 'Turn upstairs lights off'), ('ground_floor_lights', 'turn off all the lights downstairs'),
                             ('ground_floor_lights', 'lights off on the ground floor'), ('outside_lights', 'outside lights off'),
                             ('ground_floor_lights', 'turn off all the lights'), ('office_lights', 'carport lights on')):
            h = FakeHouse()
            for e in h.targets['handles'][handle]['entity_ids']:
                h.set(e, 'on')
            self.assertEqual(h.call('atlas_lights', {'target_handle': handle, 'operation': 'off'}, user_text=text)['status'], 'done', text)


class m1_BlindMovedSinceQuestion(unittest.TestCase):
    """m1: the blind yes checks only last_changed; HA doesn't move it for a position-only change, so a blind moved by hand between the
    question and the yes is still moved (the schedule path already checks the snapshot too [R8-08])."""
    def test_position_change_without_state_change(self):
        h = FakeHouse()
        e = 'cover.blind_motor_4'
        h.set(e, 'open', position_percent=50)
        q = h.call('atlas_blind', {'target_handle': 'office_blind', 'operation': 'close'}, user_text='close the office blind')
        h.backend.states[e]['attributes']['current_position'] = 80          # HA keeps last_changed for an attribute-only change
        r = h.call('atlas_confirm', {'confirmation': q['confirmation']}, user_text='yes', last_reply=q['question'])
        self.assertEqual((r['status'], r.get('reason')), ('denied', 'changed_since_question'))
        self.assertEqual(h.calls, [])


class m2_UndoAfterFailedUndo(unittest.TestCase):
    """m2: an undo whose send failed (nothing sent) still marks the action undone, so it can't be retried within the 10 minutes."""
    def test_retry_after_transport_failure(self):
        h = FakeHouse()
        h.set('light.office_ceiling', 'on')
        h.call('atlas_lights', {'target_handle': 'office_lights', 'operation': 'off'})
        h.raise_on_call = True
        self.assertEqual(h.call('atlas_undo', {})['status'], 'failed')
        h.raise_on_call = False
        self.assertEqual(h.call('atlas_undo', {})['status'], 'undone')
        self.assertEqual(h.state('light.office_ceiling')['state'], 'on')


# ---------------------------------------------------------------- wiring ----------------------------------------------------------------
class M1_GuardedAgentPlatform(unittest.TestCase):
    """M1: __init__ forwards the entry to a 'conversation' platform (the claim-guarded agent) that this export doesn't ship, so setting the
    option fails at setup and the claim guard runs nowhere. Either ship conversation.py, or refuse the option (fail closed)."""
    def test_platform_shipped_or_option_refused(self):
        ships = (PKG / 'conversation.py').exists()
        check = getattr(atlas_household, 'guarded_platform_available', None)
        self.assertTrue(ships or (check is not None and check() is False),
                        'conversation platform missing and the guarded_agent option is not refused')


def _ha_stubs(calls):
    """Just enough of homeassistant and voluptuous to import api.py and run Runtime.call offline (no Home Assistant here)."""
    class Context:
        def __init__(self, user_id=None, parent_id=None, id=None):
            self.user_id, self.parent_id, self.id = user_id, parent_id, id

    class _Any:
        def __init__(self, *a, **k):
            pass

        def __call__(self, *a, **k):
            return self

    mods = {n: types.ModuleType(n) for n in ('homeassistant', 'homeassistant.core', 'homeassistant.helpers', 'homeassistant.helpers.llm',
                                             'homeassistant.helpers.event', 'voluptuous', 'homeassistant.components',
                                             'homeassistant.components.conversation', 'homeassistant.components.conversation.chat_log')}
    chat_log = mods['homeassistant.components.conversation.chat_log']
    chat_log.AssistantContent, chat_log.UserContent = type('AssistantContent', (), {}), type('UserContent', (), {})
    chat_log.current_chat_log = types.SimpleNamespace(get=lambda: None)       # no chat: HA's MCP server, a script, the developer tools
    mods['homeassistant.core'].Context, mods['homeassistant.core'].HomeAssistant = Context, object
    llm = mods['homeassistant.helpers.llm']
    llm.Tool, llm.API, llm.APIInstance, llm.ToolInput, llm.LLMContext = object, object, _Any, _Any, _Any
    mods['homeassistant.helpers'].llm, mods['homeassistant.helpers'].event = llm, mods['homeassistant.helpers.event']
    mods['homeassistant.helpers.event'].async_track_point_in_utc_time = lambda *a: (lambda: None)
    for n in ('Schema', 'Required', 'Optional', 'In', 'All', 'Range'):
        setattr(mods['voluptuous'], n, _Any)

    class Services:
        async def async_call(self, domain, service, data, blocking=True, context=None):
            calls.append(getattr(context, 'user_id', None))

    class Hass:
        services = Services()
    return mods, Hass()


class m4_BackendContextShared(unittest.TestCase):
    """m4: HABackend.context is one attribute shared by every concurrent tool call (and the timer callback); a call that finishes resets it
    to None while another is still sending, so that call's service is attributed to nobody (or to the other person)."""
    def test_concurrent_calls_keep_their_own_context(self):
        calls = []
        mods, hass = _ha_stubs(calls)
        with mock.patch.dict(sys.modules, mods):
            sys.modules.pop('atlas_household.api', None)
            try:
                from atlas_household.api import HABackend
                backend = HABackend(hass)

                class Coord:
                    ready = False

                    def next_due(self):
                        return None

                    async def call_tool(self, tool, args, **kw):
                        await asyncio.sleep(args['delay'])
                        await backend.call('light', 'turn_on', ['light.x'], {})
                        return {'status': 'done'}

                rt = atlas_household.Runtime(hass, Coord(), backend)

                def ctx(user):
                    return types.SimpleNamespace(context=types.SimpleNamespace(user_id=user, id='p-' + user))

                async def both():
                    await asyncio.gather(rt.call('atlas_lights', {'delay': 0.05}, 'A', '', None, None, ctx('alice')),
                                         rt.call('atlas_lights', {'delay': 0.01}, 'B', '', None, None, ctx('bob')))
                asyncio.run(both())
            finally:
                sys.modules.pop('atlas_household.api', None)
        self.assertEqual(sorted(calls, key=str), ['alice', 'bob'])


class M12_NoConversationNoWords(unittest.TestCase):
    """M12: a tool call with no chat log (HA's MCP server exposes any registered LLM API to outside clients; scripts can call it too) reaches
    the coordinator with user_text '', so the whole-turn never-list check and every other check of the person's words pass vacuously."""
    def test_acting_tool_without_a_conversation_is_refused(self):
        mods, hass = _ha_stubs([])
        with mock.patch.dict(sys.modules, mods):
            sys.modules.pop('atlas_household.api', None)
            try:
                from atlas_household.api import AtlasTool
                seen = []

                class Runtime:
                    async def call(self, *a, **k):
                        seen.append(a)
                        return {'status': 'done'}

                def run(name, args):
                    tool = AtlasTool(Runtime(), name, 'd', {}, [])
                    return asyncio.run(tool.async_call(hass, types.SimpleNamespace(tool_name=name, tool_args=args, id='x'), types.SimpleNamespace()))
                r = run('atlas_lights', {'target_handle': 'office_lights', 'operation': 'on'})
                listed = run('atlas_scheduled', {})
            finally:
                sys.modules.pop('atlas_household.api', None)
        self.assertEqual((r['status'], r.get('reason')), ('denied', 'no_conversation'))
        self.assertEqual(len(seen), 1)                 # only the read-only list went through
        self.assertEqual(listed['status'], 'done')


if __name__ == '__main__':
    unittest.main()
