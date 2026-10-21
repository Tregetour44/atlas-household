# STATUS: atlas-robustness (cloud job, PC Steward brief 2026-10-21)

**Done.** Verdict in README.md; patterns in GAPS.md; patches in patches/. Branch `atlas-robustness`, cut from `atlas-current-input` @ dcb4830.

| Stage | State |
| --- | --- |
| 0. Setup: branch, baseline suite (189 tests OK, 10 skipped) | done |
| A1. Generator (`rehearsal/generate.py`, seed 20261021): 2,982 requests with expected outcomes | done |
| A2. Deterministic layers over all 2,982 (input and patched) + claim-guard corpus (1,350 pairs) | done |
| A3. gemma4:12b Q4_K_M (CPU): 209 risk-weighted cases on the input branch; 52 riskiest on the patched branch | done |
| A4. GAPS.md + rehearsal-set/ (with baseline and release check `rehearsal/check.py`) | done |
| B. Fast paths (scenes, blinds, read-only): coverage 13.1% -> 29.5%; latency in README | done |
| Patches 0001 (safety), 0002 (fast paths), 0003 (optional over-refusals): each step passes the suite; all applied: 235 tests OK | done |

## For PC Steward: your 15:1x budget message

Your message (ceiling about US$30, keep the model sample to ~50, push after each stage) arrived after Part A was complete. That included the 209-case Gemma sample on the input branch and the deterministic run over the full set. The Part B patch was also already done.

I acted on it as follows:
- I stopped the 209-case patched re-run and replaced it with the 52 riskiest cases: every input MAJOR, MINOR and miss, plus 2 controls per risky category.
- I made no further large runs.
- I kept pushing after each stage.

This cloud session can't message other sessions ("this cloud session cannot message other sessions yet"), so this note is the reply.

## Open items for the owner
- **G21 (MAJOR, model):** an invented blind schedule. The proposal in GAPS.md is to give the coordinator the schedule's read-only entities.
- **Optional patch 0003:** whether to take it.
- **Auto-undo on the never-list tripwire:** a proposal, not patched.
- **Live map:** add a `readings` section for the read-only fast path, and optionally `fast_paths`.
