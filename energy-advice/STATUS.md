# energy-advice-build: status

Branch `energy-advice-build`, cut from `energy-advice-input` (3f0d3b9). Nothing on `main` is touched.

| Time (UTC, 20 Oct) | Stage |
|---|---|
| 10:15 | Stage 0: inputs read; Ollama 0.40.6 installed; public `gemma4:12b` pulled (Q4_K_M, 11.9B, CPU only, about 4 tok/s generation on 4 cores). Thinking is off, matching HA's Ollama default. |

Next: card functions and tests, prompt renderer (the real go-live template rendered with an HA-like Jinja stub), then the runs.
