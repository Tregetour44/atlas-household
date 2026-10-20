# energy-advice-build: status

Branch `energy-advice-build`, cut from `energy-advice-input` (3f0d3b9). Nothing on `main` is touched.

| Time (UTC, 20 Oct) | Stage |
|---|---|
| 10:15 | Stage 0: inputs read; Ollama 0.40.6 installed; public `gemma4:12b` pulled (Q4_K_M, 11.9B, CPU only, about 4 tok/s generation on 4 cores). Thinking is off, matching HA's Ollama default. |
| 10:40 | Stage 1: built `build/energy_cards.py` (cards), `build/calc.py` (fast arithmetic path, read-only `atlas_calc` tool, figure guard), `build/guidance.txt`, `build/render.py` (renders the real go-live template per case), 77 cases (Codex 49's 40, owner's 3, dishwasher 14, arithmetic 20). 57 offline tests pass (`python -B -m unittest test_build`). Full Gemma run started 10:39: own cases both arms, then Codex 40 both arms. About 5 min a case on CPU (Gemma's sliding-window attention defeats prefix caching), so roughly 10 h. |
| 10:55 | Stage 2: first run attempt OOM-killed (llama.cpp prompt-cache snapshots); fixed by unloading the model after each case; run restarted 10:41. Integration drafted and tested in a scratch copy of the coordinator: `integration/coordinator.patch` applies cleanly to `main`'s `custom_components/` and `tests/`; the existing suite plus 14 new tests pass (184 OK). `integration/prompt-template.patch` is the go-live template change (one line replaced by the guidance, the two rejected fixed-advice lines removed). |
| 11:15 | Plan changed at PC Steward's request (22:1x Sydney): candidate arm on all 77 cases first (own 37, then Codex 40), then the current prompt on a 25-case subset (`build/cases/baseline-subset.json`: 3 owner, 6 dishwasher, 6 arithmetic, 10 Codex). Results pushed every ~10 cases. ETA about 7–8 h of CPU; the full Codex 40 stays in unless time runs out (then 20, said here). |
| 12:10 | Progress: own-candidate 15;  |
| 12:30 | **Finding, fixed, candidate arm restarted.** In the first 20 candidate answers (kept in `build/results/v1-example-leak/`), Gemma copied the guidance's worked example verbatim in 2 of 14 dishwasher cases (DW-07, DW-08: "Tonight's fine … a typical night here uses about 6 kWh"); in DW-08 (battery 27%) that gave the wrong advice. The figure guard let "6 kWh" through because the example sat in the prompt it used as evidence. Fixes: the example now has no figures; the guidance says to follow the card's "Lean" line and to quote ranges as ranges; the figure guard and `atlas_calc` take evidence only from the readings part of the prompt ("House readings:" on), never from instructions (test added). The 12 other v1 dishwasher answers and the arithmetic answers were sound. |
| 13:27 | Progress: own-candidate 10;  |
| 14:11 | Progress: own-candidate 20;  |
| 14:45 | Progress: own-candidate 30;  |
| 15:10 | Own cases, candidate arm done (37). Machine screen: 0 unsupported figures in final replies; arithmetic 20/21 right (AR-17 split the kWh, not the cost); 0 controller advice, 0 refusals; 20 `atlas_calc` calls; 5 sums answered in code; 4 figure-guard nudges (OWN-01: Gemma added 4.5 + 0.9 itself, was nudged, then used `atlas_calc`). Two fixes for the record: the guard now lets an `atlas_calc` result back a "$" figure (it made Gemma drop the "$" in AR-04/13/20; those 3 are re-run at the end), and the scorer allows display rounding. Finding outside this build: the coordinator's claim guard reads "Running it tonight would…" as an action claim (DW-03, DW-06 got "I haven't changed anything."); details in the README. Codex 40 (candidate) running. |
| 15:12 | Progress: codex-candidate 3; own-candidate 37;  |
| 16:06 | Progress: codex-candidate 13; own-candidate 37;  |
| 16:58 | Progress: codex-candidate 23; own-candidate 37;  |
| 17:49 | Progress: codex-candidate 33; own-candidate 37;  |
