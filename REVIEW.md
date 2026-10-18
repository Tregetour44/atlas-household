# Cloud review 1: Atlas coordinator at `main` (ccbacb4)

## Verdict: **REVISE**

0 blockers, 12 major, 4 minor. Every finding has a failing test in `tests/test_cloud_review_1.py` and a proposed patch in `patches/`. Nothing in `custom_components/` is changed on this branch. The patches are there for the owner's project to review and apply by hand.

## Suite counts

| Run | Result |
| --- | --- |
| `main` as exported (ccbacb4): `python -I -W ignore::ResourceWarning -m unittest discover -s tests` | **127 tests, OK** (0 failures, 0 skipped; tzdata was present, so the 6 DST tests ran) |
| ↳ Codex 40 runner (inside the suite) | 52 cases: 52 pass, 0 fail |
| ↳ Codex 41 runner (inside the suite) | 33 cases: 30 pass, 0 fail, 3 not checkable here (1 freeze, 2 container) |
| This branch, with the new tests and no patches | **154 tests: 137 pass, 17 fail** (16 failures + 1 error). All 17 are in `test_cloud_review_1.py`; its 10 control tests pass. |
| This branch with `patches/0001`–`0004` applied | **154 tests, OK**. The Codex 40 and 41 runner results don't change. |
| Docker test copy (`testcopy/`, `tests/run_testcopy.py`) | **NO DATA**. The docker CLI is installed but no daemon is running. Pulling the HA image would also need the network, which this review doesn't use. |

Apply the patches with `git am patches/*.patch`, or `git apply` each one in order, on ccbacb4. They build on each other.

## Major

**M1. Wiring: the claim-guarded agent platform is missing, so the guard runs nowhere.** In `__init__.py:113-114` and `:177-178`, setup and the options listener forward the entry to a `conversation` platform. `custom_components/atlas_household/conversation.py` is not in the export (config_flow.py:50 refers to it). Setting `guarded_agent` therefore makes setup fail. Even without the option, nothing ever calls `guard_reply`. `run_testcopy.py` `S_claim_guard` and `S_stream_guard` would fail on this copy.
*Patch 0004:* `guarded_platform_available()`. When the file is absent, setup doesn't forward the entry and raises a persistent notification, and the options flow refuses the option with `guard_not_installed`. The real fix is to ship the canonical `conversation.py` in the export. When it is updated, it should pass `evidence_since()` (see M8).
*Test:* `M1_GuardedAgentPlatform`.

**M2. Never-list: words the whole-turn refusal misses, so a mixed request is partly done.** `core.py:61-68`. All of these switch the office light on:
- lock hardware: "deadbolt", "latch", "padlock", "siren"
- securing: "make the house secure"
- plural garages: "open the garages"
- tariff and grid in other words: "off-peak", "peak rate", "electricity", "kWh", "mains"
- energy and EV brands: "Tesla", "Fronius", "SolarEdge"
- a door strike: "buzz me in"

*Patch 0001* adds these. Controls such as "garage light", "let the light in" and "peak brightness" still work.
*Test:* `M2_NeverWordsGaps`.

**M3. Never-list: `atlas_cancel` isn't checked.** `core.py:72`, `:564`. "Cancel that and unlock the front door" cancels the timer. A cancel changes what will happen (the guard already counts it as sent). *Patch 0001:* `NEVER_SCOPE = ACTING | {'atlas_cancel'}`. The read-only `atlas_scheduled` is unchanged. *Test:* `M3_CancelInMixedTurn`.

**M4. Map never-list: covers named like doors load.** `core.py:55-59`, `:424-429`. `FORBIDDEN` has `garage_door` but not `garage`. So `cover.garage`, `cover.garage_roller`, `cover.carport_door` and `cover.driveway` all load if the reviewer entered "shutter" or "awning", and roller garage doors often report the "shutter" class. *Patch 0001:* `COVER_FORBIDDEN` checks cover entity ids and still allows `..._door_blind` and `..._roller_blind`. *Test:* `M4_MapCoverNames`.

**M5. Guard: common false claims pass with no tool call.** Each of these comes through unchanged:
- "Timer's set for 9 pm." (`core.py:143` only matches `timer (is |has been )?set`)
- "Your lights will switch off in 10 minutes." and "Office lights will turn off at 9 pm." (`:111` needs "the … lights will")
- "Would you like me to close the blinds too, now that I've turned off the lights?" (`:202`: any question is kept whole, so a claim stated as its premise passes)

*Patch 0002:* a wider timer pattern and `_WILL` subject, and a question is checked after "now that / since / after / as / because". Honest questions still pass.
*Test:* `M5_GuardMissesCommonShapes`.

**M6. Guard: a timer list backs "I've set a timer".** `core.py:150`. `scheduled_list` backs every `scheduled` claim, including past ones. So "what's scheduled?" followed by a false "Timer set: office lights off at 9 pm." passes. *Patch 0002:* splits the kinds. A past claim is backed only by `scheduled`; a future statement ("the lights will turn off at 9") is backed by `scheduled` or `scheduled_list` [R13-03]. *Test:* `M6_TimerListBacksPastTimerClaims`.

**M7. Guard: honest timer and cancel replies are rewritten. The guard then says something false.** Each of these, with a successful `scheduled` or `cancelled` result, becomes "I can't confirm all of that.", and the true part is dropped:
- "Done! The office lights will switch off at 9 pm."
- "All set, …"
- "I've set the office lights to turn off at 9 pm."
- "Done, I've cancelled the timer."
- "I've stopped the 9 pm timer." / "I've turned off the timer."

The causes: `core.py:129` makes "Done/All set" an `action` claim backed only by `done`/`undone`; `:101` `_DID` reads "set …" and "stopped/turned off the timer" as device actions. *Patch 0002:*
- an `ack` kind, backed by `done`, `undone`, `scheduled` or `cancelled`
- an action whose object is "the timer" counts as cancel or schedule
- "set X to turn off at 9" counts as `scheduled`

The same replies with no result are still caught.
*Test:* `M7_GuardRewritesHonestTimerReplies`.

**M8. Guard: the evidence is only a bag of statuses.** `core.py:194`, `:207`, `:1166`. In one turn the lights are `done` and the blind returns `needs_confirmation`. The reply "I've turned off the office lights and closed the office blind." then passes, so the blind's yes-gate is defeated in what the person hears. *Patch 0002:* `guard_reply` also accepts `(tool, status)` pairs from the new `Coordinator.evidence_since()`. A claim about a blind needs a blind result (`atlas_confirm`/`atlas_undo`), a scene needs `atlas_scene`, and lights need lights or a scene. Bare statuses behave as before, so all existing tests pass. *Test:* `M8_GuardEvidenceIsKindLevel`.

**M9. Timers: two timers due together, and the second is cancelled as "late".** `core.py:1093-1113`. `tick()` sends and reads back one timer at a time, re-reading `now` before each. A blind read-back takes up to 45 s, so "open the office blind at 9" plus "deck lights on at 9" gives `cancelled_missed: it would have run 40 s late`, although HA was up the whole time. *Patch 0003:* time this tick spent dispatching earlier timers is not counted as lateness; lateness before the tick started still is. The control test confirms that a timer really 31 s late is still cancelled. **Owner's call:** this reads A047 ("more than 30 s late") as being about HA stalls, not Atlas's own queue. The alternative is to send all due timers before any read-back.
*Test:* `M9_SameMinuteTimers`.

**M10. Undo reaches across conversations.** `core.py:1177-1188`. In the bedroom, "Undo that" undoes the kitchen's last action, with no question for lights. Cancel is already scoped per conversation [R4-04]. *Patch 0003:* undo with no receipt code takes the latest receipt from this conversation; a timer counts for the conversation that set it. Otherwise it returns `not_here`. *Test:* `M10_UndoCrossesConversations`.

**M11. Over-reach: floor groups run for one room or one lamp.** `core.py:547-568` has no check of scope against the words. `ground_floor_lights` runs for "turn on the family room lamp" (14 lights), `outside_lights` for "deck lights on" (adds Entry), and `upstairs_lights` can be scheduled for "office light off in 10 minutes". *Patch 0003:* a multi-light handle with a floor, or with no area, needs its floor words (or "upstairs", "downstairs", "outside" and similar) or "all the lights". Otherwise the result is `needs_choice`. RT001 and RT042 are unchanged. *Test:* `M11_FloorOverreach`.

**M12. Wiring: no conversation means no words, so the word checks pass vacuously.** `api.py:61-62`. With no chat log, `user_text` is `''`, so the never-list check (and M11's check) has nothing to test. HA's MCP server exposes any registered LLM API to outside clients without a chat log, and scripts can do the same. *Patch 0004:* `AtlasTool` refuses acting tools when there's no chat log (`no_conversation`); `atlas_scheduled` still works. *Test:* `M12_NoConversationNoWords` (HA stubbed).

## Minor

**m1. The blind yes is bound only to `last_changed`.** `core.py:868`, `:899`. HA doesn't move `last_changed` for a position-only change (50% → 80% open), so a blind moved by hand between the question and the yes is still moved. The schedule path already compares snapshots [R8-08]. *Patch 0003:* `preview_snaps` plus `_same`. *Test:* `m1_BlindMovedSinceQuestion`.

**m2. A failed undo can't be retried.** `core.py:1228-1230`. When the undo's send fails with nothing sent, the original is still marked undone, so "undo that" now says there's nothing to undo. *Patch 0003:* the original is marked undone only when something was sent. *Test:* `m2_UndoAfterFailedUndo`.

**m3. Guard phrasing gaps.** These pass unflagged:
- "I've flicked/flipped the lights off"
- "I've got the lights off"
- "Here you go, lights on."
- "should now be off"
- unpunctuated "Not to worry I've turned…"
- "In 10 minutes, the lights will turn off."
- "I'll turn the lights off when you go to bed." (`_COND` excused every "when you …")

*Patch 0002* covers each one. *Test:* `m3_GuardPhrasingGaps`.

**m4. HA context shared between concurrent calls.** `api.py:22`, `__init__.py:30-35`, `:50-54`. `HABackend.context` is one attribute. When one call finishes, it resets the context to None while another call is still sending, so the logbook attributes that call to nobody. *Patch 0004:* a per-task `ContextVar`. *Test:* `m4_BackendContextShared` (HA stubbed).

## Checked and holding (no finding)

- **DST (Australia/Sydney):** I compared `_due()` against an independent oracle for 28,080 (now, HH:MM) pairs every 37 minutes across both 2026/27 change weekends. There were 0 wrong due times, and no "too far" while an occurrence within 24 h existed. Skipped and doubled times are asked back. `test_dst` passes.
- **24 h cap:** checked at schedule and at confirm. Restart: past-due timers become `cancelled_missed`, future ones `cancelled` with a notice (`cancel_pending`), and `dispatching` becomes `outcome_unknown`. Nothing is replayed.
- **Exactly once:** the `pending → dispatching` save happens before the send, and cancel and tick share the lock.
- **Light and scene timers vs blind timers:** light and scene timers run anyway and skip lights already set; blind timers re-check revision and snapshot.
- **Scenes:** only reviewed light members, with live contents checked. Blind device class is re-checked at confirm, at the timer and at undo.

## Noted, not filed

- "Okay, the lights are off." reads the same as a status answer, so it is left alone, consistent with the existing `test_no_claim`.
- "Before I put the blind down, can you confirm?" is rewritten. Every fix I tried would also excuse "Before I turned off the lights, …", so I left it.
- Undo with an explicit receipt code from another conversation is still allowed.
- A `send_failed` receipt still counts as `failed_sent` for the guard. That's conservative: an exception from the transport doesn't prove nothing was sent.
- The new `ack` kind can appear in `guard_reply`'s returned kinds.
