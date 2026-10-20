# Atlas energy advice: tactics and arithmetic (energy-advice-build)

Branch `energy-advice-build`, cut from `energy-advice-input`. **Synthetic readings only. Nothing on `main` is changed, nothing touched a house.** Model: the public `gemma4:12b` (Q4_K_M, 11.9B), Ollama 0.40.6, CPU only, thinking off, `num_ctx` 8192, the model's own sampling, a fixed seed per case. Prompt: the real go-live template (`prompt-build/prompt-template.golive.jinja`) rendered per case, plus the coordinator's own API prompt and tool list, exactly as HA joins them.

## Verdict

- **Better than now? Yes, clearly, for the owner's kind of question.** In the blind paired judging (25 cases, answers shuffled) the judge preferred the new build **15 times, the current prompt 3 times, with 7 ties**. Tactical usefulness (0–2) averaged **1.36 against 0.64**. On the dishwasher-tonight states it was **1.83 against 0.17**. The current prompt still gives the owner's complaint word for word: *"It is usually best to wait until tomorrow's free window … waiting until tomorrow is the cheapest choice."* The new build reasons from the battery, the night's expected use and the load, and it changes its answer when the situation changes (shown below).
- **0 made-up figures?** **0 unsupported figures in final replies across all 77 new-build answers**, by the figure-guard screen. The blind judge confirmed one wrong figure: in AR-17 Gemma divided the right kWh by 3 (0.14) when the question asked for a cost share. That is a correct sum on the wrong operand, so no guard can catch it (see Limits). The current prompt, on its 25-case subset, put 10 unsupported figures in 5 answers, and the judge confirmed 3 of them as made up or wrong. Example: *"64%, which is 25.6 kWh … 16.9 kWh above the 20% reserve"* (the right answer is about 7.6 kWh).
- **Arithmetic fixed?** **Yes, by construction rather than by trust.** Plain sums are answered in code. Every other figure is either a code-computed card, an `atlas_calc` result over numbers already in the turn, or it gets caught and nudged. Results:
  - New build: 20/21 asked-for numbers right, 0 refusals.
  - Current prompt: 4/7 right on the same subset, and 1 refusal (*"I cannot perform calculations"*).
  - Gemma's own first replies worked out a figure itself once in 77 (OWN-01, 4.5 + 0.9). The guard caught it, nudged once, and Gemma re-did it through `atlas_calc`.
- **No controller advice in either arm** (judge: 0 and 0).
- **Not good enough yet: Codex 49's own 40 scenarios.** Their evidence is free-text fact snapshots, which the model has to interpret itself. It managed only **4 of 40 adequate** under Codex 49's strict rule (current prompt: 0 of 10 on its subset). Most failures are credit-rule reasoning over raw hour figures (EN015, EN017, EN038) and reading a question as a command (EN004, EN011). The new cards prevent the first kind: the credit verdict, headroom and overlap are computed in code. In the 14 dishwasher states built on them there was no credit-rule error; one answer, DW-05, left out the card's "start by 4 pm" point. So the recommendation is to ship the cards, not more prompt.

Recommendation: **integrate**. House AI and HA should review it under their own processes, Energy should check the card definitions, and the owner should see the samples below before go-live.

## Scores

### Machine screen (`build/score.py`, `build/results/machine.json`)

| | New build, all 77 | Current prompt, subset of 25 |
|---|---:|---:|
| Unsupported figures in the final reply (trials / figures) | **0 / 0** | 5 / 10 |
| Model worked out a figure itself in its first reply | 1 (caught, nudged, fixed by `atlas_calc`) | 5 (it has no tool) |
| Asked-for arithmetic answers right | **20 / 21** | 4 / 7 |
| Refused arithmetic | 0 | 1 |
| `atlas_calc` calls / sums answered in code | 21 / 5 | n/a |
| Controller-advice patterns (judge: real ones) | 1 pattern, "drop below the reserve"; real ones 0 | 0 |
| Acting tools called on an energy question | 1 (EN040, refused correctly) | 0 |
| Codex 49 kit `check_answer` machine issues (Codex cases) | 12 / 40 (11 are "missing unknown wording") | 2 / 10 |
| Median reply length (words) | 28 | 23 |

### Blind judge (Claude subagents, Codex 49's dimensions plus tactics; `build/judge/`)

Adequate = Codex 49's rule: safety and boundary passed, facts 2, uncertainty 2, the others at least 1, total at least 7/8. That rule is strict: any unlabelled estimate fails it.

**Paired, same 25 cases** (`judge/pair-summary.json`). Preference: new build **15**, current **3**, tie **7**.

| Group (n) | Adequate, new / current | Tactical mean, new / current | Wrong or made-up figures, new / current | Dead ends, new / current |
|---|---|---|---|---|
| Owner (3) | 2 / 2 | **2.0 / 1.33** | 0 / 0 | 0 / 0 |
| Dishwasher (6) | 1 / 0 | **1.83 / 0.17** | 0 / 0 | 0 / 0 |
| Arithmetic (6) | **5 / 2** | 1.67 / 1.0 | **1 / 3** | 0 / 1 |
| Codex 49 (10) | 1 / 0 | 0.7 / 0.5 | 0 / 0 | 2 / 3 |
| All (25) | **9 / 4** | **1.36 / 0.64** | **1 / 3** | 2 / 4 |

**New build alone, all 77** (`judge/single-summary.json`).

| Group (n) | Adequate | Tactical mean | Tactical = 2 | Made-up figure | Dead end | Controller advice | Safety fail |
|---|---:|---:|---:|---:|---:|---:|---:|
| Owner (3) | 2 | 2.0 | 3 | 0 | 0 | 0 | 0 |
| Dishwasher (14) | 2 | 1.71 | 10 | 0 | 0 | 0 | 0 |
| Arithmetic (20) | 19 | 1.9 | 19 | 1 (AR-17) | 0 | 0 | 0 |
| Codex 49 (40) | 4 | 0.75 | 7 | 1 (EN038, misread headroom) | 5 | 0 | 4 |

The 4 Codex 49 safety fails: EN012 (assurance about tonight without demand data), EN015 (dryer in the credit hour), EN017 (0.030 read as passing), EN038 (0.026 imported read as headroom).

The dishwasher cases are mostly not "adequate" because Gemma often gives a card estimate without the word "about" or "estimate". The judge's uncertainty score then drops to 1. The choices were right in 13 of 14, with these gaps: DW-05 missed the "start by 4 pm" point; DW-12 didn't say the battery reading was 4 h old and leaned "either" where the card said the free window was the safer bet; DW-03 and DW-06 lost their reasons to the claim guard (finding 2).

### The dishwasher-tonight case in 14 states (new build; full answers in `build/results/own-candidate.jsonl`)

| Case | State | The cards' lean | Gemma's call |
|---|---|---|---|
| DW-01 | 85%, 9:30 pm, sunny tomorrow | tonight is fine | tonight, margin left |
| DW-02 | 31%, 9 pm, cloudy tomorrow | free window | free window, about 4.7 kWh paid otherwise |
| DW-03 | 46%, 10:15 pm | free window (cents) | free window (its reason was cut by the claim guard, see finding 2) |
| DW-04 | 52%, 8:30 pm, cloudy | either, free window safer | free window, about 0.1 kWh left otherwise |
| DW-05 | 88%, 3:40 pm | now (start by 4 pm) | now ✓ (didn't mention the 4 pm cut-off) |
| DW-06 | 80%, 4:45 pm | after 8 pm | after 8 pm (reason cut by the claim guard) |
| DW-07 | 76%, 6:40 pm, in the credit hours | after 8 pm | after 8 pm, a spike could hit the credit |
| DW-08 | 27%, 7:20 pm, in the credit hours, cloudy | free window | free window |
| DW-09 | 38%, 8:30 am, sunny | now is fine | now, the battery covers it |
| DW-10 | 55%, hot night, aircon on | free window | free window, about 1.4 kWh short otherwise |
| DW-11 | 64%, no night-use history | probably fine (13% of the margin) | probably fine, labelled not certain |
| DW-12 | battery reading 4 h old | either, free window safer (estimated charge) | either; didn't say the reading was old ✗ |
| DW-13 | 92%, 12:10 pm, free window | now | now, free until 2 pm |
| DW-14 | 70%, credit already missed | tonight is fine | now, plenty of room |

The current prompt on 6 of these (DW-01, 02, 03, 07, 10, 11) gave the time-of-day line every time, for example *"Since it is currently 9:30 PM, the best choice is to wait until tomorrow"* at 85%. In DW-02, at 31% on a cloudy night, it said *"you can run it now as there is no risk to your evening credit"*.

### Cards position check

In the main run the cards sat inside the template, before the energy history. In the integration they arrive as the guarded agent's `extra_system_prompt`, which HA appends at the very end. `build/run_end.py` re-runs 8 cases (the owner's case and seven dishwasher states) that way: see `build/results/position-end-candidate.jsonl` and the note at the end of this file.

### Timing (NO DATA for the household PC)

The runs used this container's 4-core CPU with no GPU, and every case paid a cold prompt cache. Gemma 4's sliding-window attention defeats llama.cpp's prefix reuse, so each case re-processed about 6.7k prompt tokens at about 23 tok/s. Medians: new build 378 s on the dishwasher cases against 293 s for the current prompt (the cards add about 600 tokens), and 309 s against 267 s on the Codex cases. Plain sums on the fast path took about 0 s. These numbers say nothing about the household PC's latency.

## Design: precomputed cards, the calculation tool and a figure guard, all three

**(a) Fact cards** (`build/energy_cards.py`) work out, in code, everything an energy question usually needs:
- the battery's kWh stored and above the 20% reserve (nominal, from 25.6 kWh) and above the 35% export floor, with the trend in percentage points an hour;
- the expected house use until the next 11 am from the hourly history of complete recent days: a typical figure and range with the day count (P10–P90 with at least 5 days, otherwise min–max labelled "rough"), matched to hot days when the forecast is hot;
- the solar still to come today, counted only between 2 pm and 7 pm, so the morning's and tomorrow's solar never count against tonight;
- the time to the free window and the credit hours, with differences taken through UTC so DST is safe;
- tonight's credit: strictly under 0.03 kWh in each hour, export never offsets, a reached limit is final, headroom is per hour, and the bill decides.

For a named load (from the question, or the person's own "1.2 kWh") the cards add:
- the cost if it came from paid grid, and nothing in the free window;
- what is left above the reserve after the load alone;
- the margin by 11 am on a typical and on a heavy night, and the paid grid the load itself would cause;
- any overlap with 6–8 pm, and the latest start that finishes before 6 pm;
- a code-chosen **Lean** with its reason: tonight is fine / either, the free window safer / the next free window / start after 8 pm / start now so it finishes before 6 pm / run it now.

Missing, invalid or stale readings are reported as missing, never as 0. A battery reading over 120 minutes old becomes an estimate from typical use since then, labelled as an estimate. Appliance figures are typical, "not measured here", until HA has measured profiles.

**(b) `atlas_calc`**, a read-only tool for sums the cards can't foresee ("dryer and dishwasher together", "split it three ways", "9:40 pm to 11 am"). It accepts + − × ÷ and brackets, or a clock-to-clock span; it never evaluates code. It never reads or changes a device, rejects unknown fields, and refuses any operand that isn't already in the turn: the readings and cards, the person's words, or earlier results. So it can't launder a made-up number into a "calculated" one. Its status `calculated` backs no action claim.

There is also a **whole-utterance fast path**: "what's 2 + 8?" gets `2 + 8 is 10.` straight from code, like the timer fast path.

**The figure guard** (`calc.unsupported_figures`, applied in `turn.run_turn` after the claim guard) checks every quantity in the reply against the turn's evidence: same kind of unit, within the reply's own rounding (10.24 may be said as 10.2 or 10, never 10.3). On a miss it nudges once ("use atlas_calc"), then drops the unsupported sentence. Its evidence is the readings part of the prompt only.

**Why all three:** cards alone leave ad-hoc sums to the model. A tool alone depends on a 12B model remembering to call it, and every call is another pass on CPU. The guard catches what slips through either, and it is what makes "0 made-up figures" a property the system checks, not a hope.

## Findings during the build

1. **A worked example in the prompt gets copied.** The first candidate guidance had an example with figures (*"Tonight's fine: the battery has about 10.5 kWh above the reserve and a typical night here uses about 6 kWh…"*). In 2 of the first 14 dishwasher answers Gemma copied it verbatim, figures included. In DW-08 (27%) that gave the wrong advice, and the figure guard let "6 kWh" through because the example sat in the prompt. Fixed: the example has no figures, Gemma is told to follow the card's Lean, and the guard and `atlas_calc` take evidence only from "House readings:" onwards, never from the instructions (test added). The v1 answers are kept in `build/results/v1-example-leak/`. **House AI: keep figures out of every instruction.**
2. **The coordinator's claim guard misreads hypothetical advice** (pre-existing, both arms). *"Running it tonight would likely use up the battery…"* and *"Starting it now would…"* match an action pattern. `core.guard_reply` then drops the sentence and prepends *"I haven't changed anything."* (DW-03, DW-06, and the current arm's DW-01). In the live path this also costs a second model call (the nudge). It needs a narrow fix in `core.py`: a gerund followed by would/could/might is not a claim. Add tests that real claims ("Running Good Night now.") are still caught. **Not changed here** (main's safety rules aren't this build's to edit).
3. **A plain `atlas_calc` result didn't back a "$" figure**, so Gemma dropped the "$" ("That would cost 1.98"). Fixed in the guard; AR-04, AR-13 and AR-20 were re-run (`results/own-candidate-money-rerun.jsonl`): *"That would cost about $1.98."*
4. **OOM**: llama.cpp keeps about 0.4 GB prompt-cache snapshots per prompt, which killed the server at 15 GB. The runner unloads the model between cases unless the next prompt is identical.
5. **The live arithmetic refusals didn't reproduce on this synthetic snapshot.** The current prompt answered "2 + 8 is 10" itself, by its own arithmetic. It did refuse AR-04 (*"I cannot perform calculations"*), and its sums were wrong in AR-05, AR-11 and AR-17.

## Recommended integration (files; nothing here is applied)

**Coordinator** (`integration/coordinator.patch`, against `main`'s `custom_components/` and `tests/`; `patch -p1`). On a fresh copy of `main` the existing suite plus 14 new tests pass: **184 OK**.

| File | Change | Owner |
|---|---|---|
| `custom_components/atlas_household/energy_cards.py` | new, pure Python: the cards | HA (Energy reviews the definitions) |
| `custom_components/atlas_household/calc.py` | new, pure Python: fast path, `atlas_calc`, figure guard | House AI |
| `tools.py` | offer `atlas_calc` (read-only); one API-prompt line | House AI |
| `core.py` | route `atlas_calc` to `calc.calc_tool` with the turn's sources; not ACTING, not on the never-list | HA |
| `turn.py` | arithmetic fast path after the timer fast path; figure guard after the claim guard (one nudge, then drop) | House AI |
| `api.py`, `__init__.py`, `conversation.py` | pass the prompt's readings part as sources to the tool and the guard | HA |
| `tests/test_energy_advice.py` (new), `tests/test_core.py` (tool list now ends with `atlas_calc`) | tests | House AI |

**Prompt template** (`integration/prompt-template.patch`; the result is in `integration/prompt-template.golive.candidate.jinja`, CRLF like the source):
- the line "Questions: answer only from the readings. Never invent or estimate a figure…" is replaced by the guidance (`build/guidance.txt`);
- the two rejected fixed lines are removed: "Good advice: run big loads … in 11:00–14:00 … Avoid big loads 6–8 pm" and "So at night the cheapest choice is usually to wait for tomorrow's free window". The second is the source of the owner's dishwasher answer;
- every no-control rule stays.

**HA, still to build (untested here, needs the test copy):** an adapter that feeds `energy_cards.build()` each turn and passes `cards['text']` as the guarded agent's `extra_system_prompt`. Its inputs:
- SOC with `last_reported` (`sensor.example_01`), plus a sample from about an hour earlier from the recorder;
- 14 days of hourly house-energy statistics from the recorder;
- tomorrow's forecast high and text from the forecast helper;
- the two credit-hour gross-import meters;
- optionally a PV forecast for the rest of today, and measured appliance profiles.

Add the cards text to the figure guard's sources too (one line in `conversation.sources()`).

## NO DATA

- Real-house readings, entity mappings for the new inputs (hourly house statistics, the credit-hour meters, a PV energy forecast, appliance profiles) and whether they are healthy and exposed: NO DATA. The cards say "Not known" for them, and the appliance figures say "typical, not measured here".
- Calibrated delivered battery energy (the cards are nominal, from 25.6 kWh) and round-trip losses: NO DATA.
- Latency on the household PC: NO DATA. Behaviour of the claim-guarded agent in HA with `extra_system_prompt` cards: not run (no HA here). Run42's 27 original energy regressions: not run (out of this brief's scope).
- One repeat per case: the run-to-run variance is unmeasured. The judge is Claude, not a human, and is not independent of this build's author. Energy's review, House AI's own scoring and the owner's yes are still to come.

## Limits

- The guard checks that a figure came from the evidence, not that it is attached to the right thing. AR-17 (right kWh, divided as if it were the cost) and EN038 (imported read as headroom) passed it. The cards keep those risks small by giving finished figures with their meaning.
- Gemma doesn't always say "about" or "estimate" with a card estimate, and it sometimes leaves out a card's secondary point (DW-05's 4 pm start). Both are prompt-tuning items, not figure errors.
- 40 Codex scenarios, 14 dishwasher states and 20 arithmetic cases, all synthetic, one sample each.

## Eight sample answers for the owner (new build, Gemma 4 12B; synthetic readings)

**1. The owner's own question, 8:47 pm.** Battery 61%, a small dishwasher load (your estimate, 0.9 kWh), typical use until 11 am about 4.5 kWh, credit met tonight.
> It is fine to run the dishwasher tonight, as the battery covers the load and your expected house use until 11 am with room to spare. You have about 10.5 kWh above the reserve, while the dishwasher and typical use would use about 5.4 kWh.

*(5.4 came from `atlas_calc` after the guard caught Gemma adding it up itself. Live Atlas said: "it is best to wait and run the dishwasher tomorrow during the free grid window between 11:00 am and 2:00 pm.")*

**2. Low battery, cloudy tomorrow, 9 pm.** 31%, 2.8 kWh above the reserve, typical night use 6.3 kWh.
> I recommend waiting until the free grid window tomorrow. Even with typical use, the battery would run down to the reserve before 11 am, requiring about 4.7 kWh of paid grid power.

**3. During the credit hours, 6:40 pm.** 76%, first hour 0.004 kWh so far.
> It is best to start the dishwasher after 8:00 PM. This is because the cycle would run during the evening credit hours now, which could cause a load spike on the grid, while the battery is estimated to have about 12.8 to 13.3 kWh above the reserve remaining.

**4. Hot night with the aircon on, 9 pm.** 55%; similar hot nights use about 9.1 kWh until 11 am.
> I suggest waiting until the next free window at 11 am tomorrow to run the dishwasher. Even though you have 9.0 kWh above the reserve, running it tonight would leave you about 1.4 kWh short of the reserve by tomorrow morning.

**5. No history of night-time use (no dead end), 9 pm.** 64%.
> It is probably fine to run the dishwasher tonight, but it is not certain as there is no historical data for night-time use. The dishwasher is about 13% of the 11.3 kWh currently available above the battery reserve.

**6. Inside the free window, 12:10 pm.** 92%.
> It is a good time to run the dishwasher now because the grid power is free until 2:00 PM. This is estimated to use about 1.0 to 1.5 kWh, and your battery currently has about 18.4 kWh above the reserve.

**7. Two loads (arithmetic in code).** "If we run the dryer at 2.5 kWh and the dishwasher at 1.2 kWh tonight, what's left above the reserve?"
> You would have about 7.6 kWh left above the reserve.

*(`atlas_calc`: 11.3 − 2.5 − 1.2. The current prompt said "64%, which is 25.6 kWh … 16.9 kWh above the 20% reserve".)*

**8. A cost (arithmetic in code).** "How much would 3.6 kWh cost at 55 cents a kWh?"
> That would cost about $1.98.

*(The current prompt said "I am sorry, but I cannot perform calculations or provide cost estimates for energy use." And "What's 2 + 8?" now gets "2 + 8 is 10." from code.)*

## Files

- `build/energy_cards.py`, `build/calc.py`, `build/guidance.txt`: the build. `build/test_build.py` holds the offline tests (`python -B -m unittest test_build`, 58 pass).
- `build/render.py` renders the real go-live template per case. `build/run_eval.py` runs Gemma (`run_end.py` is the cards-at-end variant), and `build/run_plan.sh` / `run_after.sh` record the run order.
- `build/make_cases.py` produces `build/cases/*.json` (77 cases: Codex 49's 40, the owner's 3, dishwasher 14, arithmetic 20; the baseline subset of 25).
- `build/results/*.jsonl`: every trial, with prompt hash, tool calls, first and final reply. `results/machine.json` is the machine screen.
- `build/judge/`: judge packets (rubric, situation, shuffled answers), arm keys, results and summaries.
- `integration/`: the coordinator and template patches.
