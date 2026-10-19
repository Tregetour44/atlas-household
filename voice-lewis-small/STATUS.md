# voice-lewis-small: status

**Updated:** 2026-10-19 22:35 UTC (Tue 20 Oct, 09:35 Sydney)
**Step:** 4 of 4. Evaluation is done and **the deliverable is pushed**: `model/`, `samples/`, `README.md`. The brief's definition of done is met.
**Now:** training is continuing past step 2500 (to 3000, then 3500) because held-out results were still improving. The model, samples and README will only be updated if a later checkpoint is better on the held-out measures. If not, step 2500 stays.
**Blockers:** none.

## Headline (step 2500, delivered)

- **Speed:** CPU RTF 0.037 mean, **0.049 p95**, on 4 vCPU Xeon @ 2.1 GHz. Pinned to 1 core it is the same (p95 0.045). RAM ~185–345 MB. The target was p95 ≤ 0.7.
- **Likeness:**
  - speaker similarity to the teacher 0.84 overall and 0.90 on the four sample lines (the teacher scores 0.87 against its own other clips);
  - same pitch (96 vs 99 Hz), similar pitch movement (3.7 vs 3.8 st) and pace (3.71 vs 3.78 words/s);
  - WER 0.9%.
- **Gap:** naturalness, UTMOS 4.06 vs the teacher's 4.34. Judge by ear: `samples/lewis-small-N.mp3` vs `samples/teacher-chatterbox-kokoro-lewis-ref-N.mp3`.

## Step history

- Step 1 gate: no lighter option passed. Turbo RTF 2.4 is too slow; Kokoro bm_lewis is fast but is the delivery the owner passed over; Pocket TTS cloning is gated (NO DATA). See the README.
- Step 2 corpus: 570 accepted clips, 37.0 min (target 30–45). 82 rejected attempts are logged.
- Step 3 student: northern_english_male medium base, 2,500 steps on CPU (~4 h).
- Step 4 evaluate: README tables, `eval/`.

## Time left

- Optional extension: about 45 min per 500 steps. I'll stop when held-out results stop improving, or after step 3500.
