# STATUS: atlas-robustness (cloud job, PC Steward brief 2026-10-21)

Branch `atlas-robustness`, cut from `atlas-current-input` @ dcb4830. Pushed at each stage and at least every 2 h.

| Stage | State |
| --- | --- |
| 0. Setup: branch, baseline suite (189 tests OK, 10 skipped), read code | done |
| A1. Generator + ~3,000 requests (seeded) | in progress |
| A2. Deterministic layers over every request | to do |
| A3. ~150 risk-weighted cases through gemma4:12b (Q4_K_M, CPU, Ollama) | to do (installing Ollama) |
| A4. GAPS.md + rehearsal-set/ | to do |
| B1. Latency measurement (fast vs model path; CPU, labelled) | to do |
| B2. Fast-path extension (scenes, blinds, read-only questions) | to do |
| B3. Patch + tests + Part A re-run (0 new MAJOR) | to do |

Environment: 4 vCPU, 15 GB RAM, no GPU. All timings here are CPU timings, not the owner's GPU PC.
