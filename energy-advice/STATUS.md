# energy-advice-build: status

Branch `energy-advice-build`, cut from `energy-advice-input` (3f0d3b9). Nothing on `main` is touched.

| Time (UTC, 20 Oct) | Stage |
|---|---|
| 10:15 | Stage 0: inputs read; Ollama 0.40.6 installed; public `gemma4:12b` pulled (Q4_K_M, 11.9B, CPU only, about 4 tok/s generation on 4 cores). Thinking is off, matching HA's Ollama default. |
| 10:40 | Stage 1: built `build/energy_cards.py` (cards), `build/calc.py` (fast arithmetic path, read-only `atlas_calc` tool, figure guard), `build/guidance.txt`, `build/render.py` (renders the real go-live template per case), 77 cases (Codex 49's 40, owner's 3, dishwasher 14, arithmetic 20). 57 offline tests pass (`python -B -m unittest test_build`). Full Gemma run started 10:39: own cases both arms, then Codex 40 both arms. About 5 min a case on CPU (Gemma's sliding-window attention defeats prefix caching), so roughly 10 h. |
