# Cloud review 2: Atlas coordinator at `main` (f47f949)

## Verdict: **REVISE**

6 major, 3 minor and 1 known (R17-01, held). Review 1 is mostly holding: 13 of its 16 findings are fixed or adapted as the owner decided, and 3 are only partly fixed (M5, M8, M11). The new generated pack (`tests/test_cloud_review_2_generated.py`, 4,435 cases, fixed seed, about 10 s) found these gaps:
- never-list words that still let a mixed turn run
- never-list names in the map itself (handle names and labels)
- a pronoun route around review 1's blind-evidence fix (M8)
- common reply shapes the guard misses
- "all the lights …" reaching the wrong floor
- zero-padded times read as pm

Every finding has a failing test and a patch in `patches/`. With `patches/0001`–`0005` applied in order (`git am patches/*.patch` on f47f949), the full suite passes. Nothing in `custom_components/` is changed on this branch.

## Suite counts

| Run | Result |
| --- | --- |
| `main` as exported (f47f949): `python -I -W ignore::ResourceWarning -m unittest discover -s tests` | **170 tests, OK** in 78 s (0 failures, 0 skipped). tzdata is present, so `test_dst` ran. |
| ↳ Codex 40 runner (inside the suite) | 52 cases: 52 pass, 0 fail |
| ↳ Codex 41 runner (inside the suite) | 33 cases: 30 pass, 0 fail, 3 not checkable here (1 freeze, 2 container) |
| This branch: main plus `test_cloud_review_2_generated.py`, no patches | **185 tests: 177 pass, 8 fail.** All 8 are in the new module. Its 7 others pass: the controls, the absolute, relative and list/cancel/restart timer families, the fast path's names, and the case total. |
| This branch with `patches/0001`–`0005` applied | **185 tests, OK** in 88 s. The Codex 40/41 runner results don't change, and `test_guard_own_summaries` still passes. |
| The generated pack alone, patched, with seeds 1, 777 and 424242 | 0 failures for each seed (a check that the patches aren't fitted to the fixed seed) |
| Docker test copy (`testcopy/`, `tests/run_testcopy.py`) | **NO DATA.** The docker CLI is installed, but no daemon is running (`/var/run/docker.sock` is missing). |

`hypothesis` wasn't installed. I installed it with pip (that was the only network use), but the pack uses a seeded generator with its own greedy shrinker. That way it runs in the owner's offline `python -I` suite with no new dependency. To print the case counts and the minimised failures, run `python -I tests/test_cloud_review_2_generated.py --report`.

## Review 1: fix status (M1–M12, m1–m4)

| Id | Status | Evidence on f47f949 |
| --- | --- | --- |
| M1 guarded platform missing | **Fixed** | `conversation.py` ships. `__init__.py:22` `guarded_platform_available()`; `:120`, `:187` forward only when the platform exists. `config_flow.py:53` refuses the option otherwise. The agent passes `(tool, status)` evidence (`conversation.py`, `out.get('evidence')`; `turn.py:44-48`). Test `M1_GuardedAgentPlatform` passes. |
| M2 never-list gaps | **Fixed for its 16 cases**, but the category is still open → **N1** | `core.py:72-75` adds review 1's words. `M2_NeverWordsGaps` passes. Other wordings for the same subjects still run (N1). |
| M3 cancel in a never-list turn | **Fixed** | `core.py:85` `NEVER_SCOPE = ACTING \| {'atlas_cancel'}`, used at `:640` and in `api.py:75`. The generated pack ran 105 cancel cases mixed with forbidden intents; each was refused whenever the words were caught. |
| M4 door-like cover names | **Fixed (adapted)** | `core.py:62` `COVER_FORBIDDEN`. `…_roller_blind` and `…_door_blind` are deliberately allowed. `M4_MapCoverNames` passes. The same names in handles or labels are a separate route → **N2**. |
| M5 common shapes missed | **Partly fixed** → **G2** | Review 1's six shapes are caught. But `_WILL` (`core.py:125`) needs `\b` before "lights", so "In 10 minutes, the family room downlights will turn off." and "The family room downlights will switch off in 10 minutes." still pass with no tool call. |
| M6 a list backs "I've set a timer" | **Fixed** | `core.py:175-176`: `scheduled` versus `scheduled:future`. 0 failures among the generated `timer_past` cases backed only by a list. |
| M7 honest timer/cancel replies rewritten | **Fixed with bare statuses.** Under `(tool, status)` evidence two shapes are still rewritten = **R17-01 (known)** | `core.py:144-147` `ack` kind; `:223-226` timer object. "All set, the office lights will turn off in 10 minutes." with `('atlas_schedule','scheduled')` → "I can't confirm all of that." (8 generated cases, all "All set, …" / "All done, …"). |
| M8 evidence was only a bag of statuses | **Partly fixed** → **G1** | `core.py:181-184`, `:232-245`, `evidence_since` `:1273`. A claim that names the blind needs a blind result. A blind spoken of by pronoun ("I've closed it.") is checked against no thing at all, so a lights result backs it. |
| M9 same-tick timers "late" | **Adapted as decided** (same-tick dispatch isn't late) | `core.py:1188`, `:1195-1198`, `:1207`. `M9_SameMinuteTimers` passes, including the control that a timer really 31 s late is cancelled. See "Checked, not filed" for one remark. |
| M10 undo across conversations | **Fixed** | `core.py:1296-1298` `not_here`. A timer's receipt belongs to the conversation that set it (`ctx` in `tick`, `:1232`). |
| M11 floor groups for one room | **Partly fixed** → **S1** | `core.py:677-687`. A room on its own now asks. But `ALL_LIGHTS` (`:683`) short-circuits, so "turn off all the lights upstairs" runs `ground_floor_lights`, and "all the lights in my office" runs any floor group. |
| M12 no conversation means no words | **Fixed** | `api.py:75-77` refuses `NEVER_SCOPE` tools with no chat log (`no_conversation`). `atlas_scheduled` still works. |
| m1 blind yes bound only to `last_changed` | **Fixed** | `core.py:962` `preview_snaps`; `:993-995` compares revision and snapshot. |
| m2 a failed undo can't be retried | **Fixed** | `core.py:1344`: the original is marked undone only if something was sent. |
| m3 guard phrasing gaps | **Fixed for its list** (the downlights subject → G2) | `core.py:115-116`, `:127`, `:148-151`, `:196-198`. `m3_GuardPhrasingGaps` passes. |
| m4 shared HA context | **Fixed** | `api.py:24-34` per-task `ContextVar`. |

## Generated pack: results on f47f949

The pack has 4,435 cases. Each failing case is shrunk greedily: drop the prefix, suffix, case change, extra evidence, acknowledgement word or adverb, switch to the simplest allowed command, and use " and ". Each line below is the smallest still-failing form.

| Family | Cases | Failing (minimal, distinct) | Invariant |
| --- | ---: | ---: | --- |
| never-list mixing | 1,100 | 22 phrases | refuse the whole turn; nothing sent, queued or cancelled (lights, dim, brightness, scene, blind, timers, cancel, undo, confirm) |
| never-list aliases (map names) | 87 | 58 | a handle or label on the never-list never loads |
| never-list controls | 120 | 0 | ordinary turns with near-miss words still act |
| never-list minor words | 9 | 8 | brands and units |
| claim-guard pairs | 1,135 | 102 | never let an unbacked claim through; never rewrite a backed reply; never "I haven't changed anything." after a send; the rewrite holds no claim |
| claim guard, known R17-01 | 25 | 8 | as above (held) |
| claim guard, minor shapes | 15 | 15 | less common claims are caught |
| timers, absolute (`at_time` against an oracle that enumerates real instants; DST weekends 2026-10-04 and 2027-04-04) | 700 | **0** | correct due time and label; DST-skipped or doubled times asked back; "now" asked; 24 h cap |
| timers, spoken (fast path: bare hours, am/pm, `h.mm`, noon, midnight, 24-hour) | 450 | 9 | the scheduled time is what was said |
| timers, relative (minutes, hours, "half an hour", "an hour and a half"; fires at the due second, not one second early; a light changed by hand still runs or skips; cap > 24 h refused by schema and fast path) | 266 | **0** | |
| timers, list / cancel / restart | 120 | **0** | list count; "cancel that" scoped per conversation and asks when ambiguous; restart cancels with a notice; nothing replays |
| over-reach: floors | 260 | 21 | a floor or outside group runs only for its own scope |
| over-reach: controls / fast-path names | 60 / 88 | 0 / 0 | |

## New findings

Line numbers are on f47f949. Each test named here is in `tests/test_cloud_review_2_generated.py`.

### Major

**N1. Never-list: other wordings of lock, alarm, opener, EV-charging, battery, export and tariff requests still let a mixed turn run.** `core.py:64-76` (`NEVER_WORDS`).

These turns are partly done: each switched the office light on, and the same happens with every other allowed tool. Minimal examples, each after "turn on the office light and …":
- **lock:** "unbolt the door", "relock the door", "secure the doors"
- **alarm:** "arm stay mode", "arm night mode", "arm the perimeter", "set the house to armed"
- **opener:** "roll up the garage", "open the carport", "open the shed", "trigger the door strike", "hit the door release", "let me in"
- **energy:** "stop charging", "set home storage to backup", "sell power back", "restart the power-wall"
- **solar:** "clean the photovoltaics", "how are the rooftop panels doing"
- **tariff:** "use the time-of-use rate", "check the shoulder rate", "read the smart meter"

*Test:* `NeverListMixing.test_mixed_turns_are_refused_whole`. The control `test_control_allowed_alone_still_acts` covers "garage light", "security lights", "door blind", "roller blind", "let the light in", "armchair lamp" and "peak brightness".
*Patch 0001.*

**N2. Never-list via aliases: a handle name or label on the never-list loads.** `core.py:475-509`: `_check_targets` checks `FORBIDDEN` and `COVER_FORBIDDEN` against entity ids only (`:504`, `:506-508`).

Each of these loads:
- `{'garage_door': {'kind': 'blind', 'label': 'Relay three', 'entity_ids': ['cover.blind_motor_9']}}` with the cover reviewed as `shutter`
- a light handle `relay_three` labelled "Gate opener" (`light.relay_3`: a relay exposed as a light can drive a gate)
- the same with "Front door lock", "Alarm siren", "Battery", "Inverter", "Solar export", "Tariff switch", "Deadbolt", "Roller door", "Car charger", "Powerwall", "Door strike", and "Garage" for a blind

The model sees these labels in the API prompt (`tools.py:120-131`). The README promises the never-list holds "in the map or in the person's words", and the code comment at `core.py:54` says "whatever the map says".

*Test:* `NeverListMixing.test_map_aliases_on_the_never_list_do_not_load`.
*Patch 0001* checks the handle name, the label and any `aliases` against `NEVER_WORDS`, and a blind's names against `COVER_FORBIDDEN`. The whole synthetic map and the demo map still load. A light labelled "Garage" is still allowed, because it is the garage light.

**G1. Guard: a blind spoken of by pronoun is backed by a lights result, so the blind's yes-gate is defeated in what the person hears.** `core.py:232-245`. `_backing` takes the "things" a claim is about only from nouns (`:235`). "I've closed it." names no thing, so any result fits.

The turn: the office lights are `done`, and the office blind returns `needs_confirmation`. These replies pass unchanged:
- "I've closed it."
- "I've turned off the office lights. I've lowered it."
- "The office lights are off. Got it, I've opened it."

This is the M8 scenario by another route. Minimal form: `"I've closed it."` with `[('atlas_lights', 'done')]`.

*Test:* `ClaimGuardPairs.test_pairs` (38 minimal pronoun cases). The honest control is the same replies with `('atlas_confirm', 'done')`.
*Patch 0002* adds `_BLIND_PRONOUN`: only a blind is opened, closed, lowered or raised. A past-tense verb of that kind with "it", "them", "that", "those" or "both" makes the claim about a blind.

**G2. Guard: common reply shapes pass with no tool result (M5 partly fixed).** Each minimal example passes unchanged with `[]` or with an unrelated result:

| Shape | Minimal example | Cause |
| --- | --- | --- |
| "has/have **now** been …" | "The lights have now been switched on." / "The office blind has now been closed." / "The Galley Cooking scene has now been activated." | `core.py:141` allows nothing between `has` and `been` |
| "they'll" / "it'll" | "They'll switch off at 9 pm." / "It'll turn off in 10 minutes." | `_WILL`, `core.py:125`, only has "it/they will" |
| "will **be** off at …" | "The office lights will be off at 9 pm." | `_WILL` verbs: no "be on/off" |
| downlights as the subject | "In 10 minutes, the family room downlights will turn off." | `\b(?:lights?…)` in `_WILL` can't match inside "downlights" |
| the queue's state | "The lights are set to turn off at 9 pm." / "The office lights are scheduled to turn off at 9 pm." | no pattern |
| verbless timer acknowledged | "Got it, office lights off at 9 pm." | the verbless pattern (`:152`) needs the end of the sentence after on/off |
| cancel | "That's cancelled." / "Cancelled the 9 pm timer." | `core.py:169-170` needs "I've cancelled", "timer cancelled" or "cancelled the timer" |
| scene | "I've run the Galley Cooking scene." / "Galley Cooking scene running." | `_DID` has "ran", not "run"; the verbless states have no active/running |

*Test:* `ClaimGuardPairs.test_pairs`.
*Patch 0002.* A future statement such as "set/scheduled to …" or "Got it, lights off at 9 pm" is a `scheduled:future` claim, so a timer list still backs it [R13-03]. A bare "Office lights off at 9 pm." is deliberately left alone: the coordinator's own `needs_choice` summary ("Which one? Office lights off at 7:40 pm; …") reads the same, and `test_guard_own_summaries` caught my first attempt.

**S1. Over-reach: "all the lights …" runs a floor or outside group for another floor or for one room (M11 partly fixed).** `core.py:683`: `if ALL_LIGHTS.search(text): return True` comes before any check of what else the words name, and `:84`'s look-ahead only excuses "in/on/at the" directly after "lights".

Minimal examples (`atlas_lights`; `atlas_schedule` behaves the same):
- "turn off all the lights upstairs" → `ground_floor_lights` (14 lights) or `outside_lights`
- "turn off all the lights downstairs" → `upstairs_lights`
- "turn off all the lights in my office", "all lights off in the office please", "every light in my office off", "turn off all the lights in office" → any floor group

*Test:* `OverReach.test_floor_groups_need_their_own_scope`. The control `test_control_scope_named_runs` and review 1's `M11_FloorOverreach` still pass: "turn off all the lights" still runs a floor group.
*Patch 0004:* the group's own scope words come first. "All the lights" then covers it only when the words name no other floor or outside group and no room (a handle's `area`).

**T1. Timers: a zero-padded time is read as a bare hour and flipped to pm, so the timer fires at a time nobody asked for.** `fastpath.py:85` (`_clock`): `elif h <= 12:` treats "04:00" like "4".
- "turn the office lights off at **00:00**" asked at 04:48 → scheduled for **12:00 noon**
- "turn off the attic lamp at **04:00**" at 04:56 → 4:00 pm
- "office lights on at 01:45" at 06:30 → 1:45 pm

This path never asks the model. The reply does state the wrong time ("Timer set: … at 12:00 pm"), so the person can cancel. But the stated invariant is that the scheduled time is correct.

*Test:* `Timers.test_spoken_times_through_the_fast_path` (9 cases).
*Patch 0005:* a leading zero means a 24-hour time as written. Bare hours ("at 7", "at 11", "at 12:30") keep their next-occurrence rule.

### Minor

**G3. Guard: "I've started a 10-minute timer for the office lights." is misread.** With `('atlas_schedule','scheduled')` it is rewritten to "I can't confirm all of that.". With `('atlas_lights','done')` it passes as a lights claim. Cause: `_TIMER_OBJECT` (`core.py:186`) doesn't allow "-" in the words before "timer", so the claim stays an `action`. Same family as R17-01 (a rewrite to "can't confirm", not a false statement). *Test:* `ClaimGuardPairs.test_pairs` (`timer_past`, 5 cases). *Patch 0002.*

**m-1. Never-list: energy and lock brands and units.** "the Sonnen", "the Victron", "the Redback", "the Selectronic", "the Growatt", "Amber Electric", "the Yale", "the Nuki" pass. "set export to 5 kW" is already caught, by "export". `core.py:75`. A brand list can't be complete; this adds the common AU ones. *Test:* `MinorPhrasings.test_minor_never_words_brands_and_units`. *Patch 0001.*

**m-2. Guard: less common phrasings.** These 15 pass with no tool result:
- "I've lit the lamp.", "I've drawn the blinds.", "I've pulled down the office blind.", "I've rolled the blind down.", "I've toggled the office light.", "I've cut the lights.", "I've dropped the blind."
- "The office blind is now down.", "The blind is closing now."
- "The office light's off now.", "The blind's closed now."
- "I'm cancelling the timer."
- "I've run the Galley Cooking scene.", "Galley Cooking scene running."
- "The office lights are now switched off."

`core.py:114-155`. *Test:* `MinorPhrasings.test_less_common_claims_are_caught`. *Patch 0002.*

### Known (held; don't re-file)

**R17-01. Under `(tool, status)` evidence, an acknowledgement in the same clause as a timer statement is rewritten.** "All set, the office lights will turn off in 10 minutes." and "All done, the lights will switch off at 9 pm." with `('atlas_schedule','scheduled')` → "I can't confirm all of that." The `ack` claim is checked against the lights' tools because the clause names lights (`core.py:243-245`). "Done! …" as its own sentence passes.

*Test:* `ClaimGuardPairs.test_known_R17_01_ack_with_a_thing_backed_by_a_timer` (25 cases, 8 minimal failures).
*Proposed fix, patch 0003 (known):* the timer's result backs the acknowledgement only when every thing named in the clause is inside the timer statement. "All set, the lights are off and the timer is set." still needs a lights result. One residual case stays rewritten: "All set, the timer for the office lights is set." That errs on the safe side.

## Patches

Apply in order on f47f949. They stack: 0002 assumes 0001.

| Patch | Fixes | Tests that prove it |
| --- | --- | --- |
| `0001-Never-list-…` | N1, N2, m-1 | `NeverListMixing.*`, `MinorPhrasings.test_minor_never_words_brands_and_units` |
| `0002-Claim-guard-…` | G1, G2, G3, m-2 | `ClaimGuardPairs.test_pairs`, `MinorPhrasings.test_less_common_claims_are_caught`; still passing: `test_claim_guard`, `test_guard_own_summaries`, `test_cloud_review_1` |
| `0003-KNOWN-R17-01-…` | R17-01 (known; the owner's call) | `ClaimGuardPairs.test_known_R17_01_…` |
| `0004-Scope-…` | S1 | `OverReach.test_floor_groups_need_their_own_scope`; still passing: `M11_FloorOverreach` |
| `0005-Fast-path-…` | T1 | `Timers.test_spoken_times_through_the_fast_path` |

No test is weakened, no never-list rule is narrowed, and every patch only adds refusals or catches. The one exception is 0003, which lets one shape through only when a timer result backs it.

## Checked, not filed

- **DST, 24 h cap, restart, firing:** 0 failures in 1,086 generated absolute and relative timer cases against an oracle that enumerates real UTC instants, so it doesn't reuse the code's fold arithmetic. The cases cover both 2026/27 Sydney change weekends, the change hours themselves, "now", and the days either side. Light timers run at the due second and skip lights already set; blind-timer re-check is covered by the existing tests.
- **M9 (as decided):** the "busy" allowance (`core.py:1197`) has no upper bound. A backend call that hangs (HA `blocking=True` has no timeout) would let a later timer in the same tick run as "not late" however long the hang lasted. A cap, such as the sum of the read-back timeouts already spent, would keep A047's intent. This is the owner's design choice, so it's noted here only.
- Over-refusal on the safe side: "the lights near the front door on", "light by the gate" and "lights by the garage door" are refused whole. That is consistent with the rules, but could annoy.
- A bare "Office lights off at 9 pm." (no acknowledgement word) is still not a claim, by design (see G2).
- As in review 1: "Okay, the lights are off." with no tool call reads as a status answer and is left alone.
