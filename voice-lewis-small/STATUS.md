# voice-lewis-small: status

## Round 2: narrow the naturalness gap (started 2026-10-19 23:44 UTC / 20 Oct 10:44 Sydney)

**Updated:** 2026-10-19 23:50 UTC | **elapsed round 2:** 0 h 06 m
**Stage:** 2, growing the teacher corpus (writing new sentences).
**Reused from round 1:** all 682 teacher masters (113 MB) and the full step 2000/2500/3000 checkpoints are still in this sandbox, so no regeneration is needed.

**Plan, in stages, stopping at a plateau:**
1. Write about 600 new original sentences: about 120 short confirmations (round 1's weakest family), times, percentages, energy, weather, dry wit and longer briefings. Also 3 new held-out Atlas-style lines.
2. Generate with the same teacher, settings and filters. That is about 5 h of teacher compute for roughly +40 min of accepted audio (37 → about 80 min).
3. Meanwhile (almost free): tune Piper's inference noise settings (`noise_scale`, `noise_w`) on the round-1 model.
4. Student (a): Piper medium warm-started from step 2500 on the bigger corpus, about 1,000–1,500 steps, evaluated every 500.
5. If (a) improves, grow towards 2 h and train again. (b) Piper high and (c) another architecture are judged on training cost and CPU speed; see the round-2 README when it's written.

**Best so far:** round 1, step 2500: UTMOS 4.06 (teacher 4.34), similarity to teacher 0.837, WER 0.9%, p95 RTF 0.049 (4 vCPU).
**ETA:** first round-2 student evaluation in about 7–8 h.
**Blockers:** none.

---

## Round 1 (done)

The round 1 deliverable is at the folder root: `model/`, `samples/`, `README.md`. Verdict: about 25× faster than real time, similarity 0.84, naturalness gap UTMOS 4.06 vs 4.34. Step 3000 was a plateau, so step 2500 was kept.
