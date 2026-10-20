# energy-advice-build: status

Branch `energy-advice-build`, cut from `energy-advice-input` (3f0d3b9). Nothing on `main` is touched.

| Time (UTC, 20 Oct) | Stage |
|---|---|
| 10:15 | Stage 0: inputs read; Ollama 0.40.6 installed; public `gemma4:12b` pulled (Q4_K_M, 11.9B, CPU only, about 4 tok/s generation on 4 cores). Thinking is off, matching HA's Ollama default. |
| 10:40 | Stage 1: built `build/energy_cards.py` (cards), `build/calc.py` (fast arithmetic path, read-only `atlas_calc` tool, figure guard), `build/guidance.txt`, `build/render.py` (renders the real go-live template per case), 77 cases (Codex 49's 40, owner's 3, dishwasher 14, arithmetic 20). 57 offline tests pass (`python -B -m unittest test_build`). Full Gemma run started 10:39: own cases both arms, then Codex 40 both arms. About 5 min a case on CPU (Gemma's sliding-window attention defeats prefix caching), so roughly 10 h. |
| 10:55 | Stage 2: first run attempt OOM-killed (llama.cpp prompt-cache snapshots); fixed by unloading the model after each case; run restarted 10:41. Integration drafted and tested in a scratch copy of the coordinator: `integration/coordinator.patch` applies cleanly to `main`'s `custom_components/` and `tests/`; the existing suite plus 14 new tests pass (184 OK). `integration/prompt-template.patch` is the go-live template change (one line replaced by the guidance, the two rejected fixed-advice lines removed). |
| 11:15 | Plan changed at PC Steward's request (22:1x Sydney): candidate arm on all 77 cases first (own 37, then Codex 40), then the current prompt on a 25-case subset (`build/cases/baseline-subset.json`: 3 owner, 6 dishwasher, 6 arithmetic, 10 Codex). Results pushed every ~10 cases. ETA about 7–8 h of CPU; the full Codex 40 stays in unless time runs out (then 20, said here). |
