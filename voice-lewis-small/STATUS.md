# voice-lewis-small: status

## Round 2: narrow the naturalness gap (started 2026-10-19 23:44 UTC / 20 Oct 10:44 Sydney)

**Updated:** 2026-10-20 01:35 UTC | **elapsed round 2:** 1 h 51 m
**Stage:** 2, growing the teacher corpus. Teacher generation has been running since 23:48 UTC; 235 of about 914 new clips are done.
**Accepted so far:** 755 clips, **48.7 min** (round 1: 37.0 min). The projection is about 85 min once all batches are generated (about 4 h more).
**Free gain found:** an inference-noise grid on the round-1 model. Lowering `noise_scale` from 0.667 to 0.5 (`noise_w` 0.8) raises UTMOS from 4.06–4.07 to 4.11 with WER 0.7% and unchanged similarity. Piper sampling is random, so small differences will be confirmed with repeated renders.
**(b) Piper high:** published `en_GB-cori-high` runs about 5× slower than our medium model on the same CPU. That fits the desktop target, but probably not 1–2 ARM cores, and its CPU training would cost 3–5× more per step. Deferred until (a) is measured.
**Corpus written:** 897 new original training lines (about 56 min of teacher audio expected, so about 87 min accepted in total), plus 17 new evaluation-only lines:
- `train_ext2/`: 126 short confirmations, energy and weather, wit, status, longer briefings, 200 templated times and percentages;
- `train_ext3/`: long briefings, phonetic coverage, household lines;
- `train_ext4/`: **the owner's house names and reply shapes, folded in.** That is the 42 supplied reply lines as written, plus 230 variations; every name is used at least twice.
- **Held out:** 3 new Atlas-style lines (`heldout_r2/`), plus 6 of the supplied reply lines and 8 lines using 8 held-out names (`heldout_r3/`). The held-out names never appear in training text.
- Round-1 ids and seeds are unchanged (new rows are appended).
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
