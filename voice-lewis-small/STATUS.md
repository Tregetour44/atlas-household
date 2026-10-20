# voice-lewis-small: status

## STOPPED (owner decision, 21 Oct 01:1x Sydney)

Atlas's voice will be the **Kokoro Fable-mix** from `audition-ready/`, and a new session will build its engine. This session has stopped all work. Nothing is running. Lewis training will not resume, and Fable distillation was not started.

**Best Lewis round 2 checkpoint: step 3000** (59-line eval: UTMOS 4.11, WER 2.4%, similarity to teacher 0.851, vs round 1's 4.09 / 4.3% / 0.850). The gain over round 1 is near noise, so **round 1 (`model/`) remains the delivered Lewis voice**, and it is live in the home. The round 2 checkpoints (step 3000 and the rolling step 3300, 846 MB each) and the teacher audio (1,762 FLAC masters) stay only in this sandbox and were not committed (size rule), so they will be lost when it is reclaimed.

**Kept on the branch:**
- `model/`, `samples/`, `README.md`: the round 1 small Lewis (Piper medium ONNX) with its verdict, metrics, hashes and licences.
- `checkpoint/`: the round 1 step 2500 generator (fp16) for warm starts.
- `corpus/`: all corpus text (round 1 and round 2, including the owner's house names and reply shapes and the held-out lines), the manifest with per-clip seeds, and the round 1 teacher logs, scores, accepted list and rejects.
- `fable-deeper/`: 9 Chatterbox Fable variants (4 sample lines and 10 audition lines), the deepened reference clips, scores and a README.
- `audition-ready/`: 24 ready-made voices (Kokoro blends, Piper en_GB/VCTK, Pocket TTS, XTTS-v2), scores, the top 3 and per-line notes. Top pick: **Kokoro bm_fable 0.7 + bm_lewis 0.3**.
- `scripts/`, `configs/`, `eval/`: the full pipeline (teacher generation, filters, Piper training, evaluation, audition tools).

## Round 2: narrow the naturalness gap (started 2026-10-19 23:44 UTC / 20 Oct 10:44 Sydney)

**Updated:** 2026-10-20 14:20 UTC | **elapsed round 2:** 14 h 36 m (final)
**Change of tack (owner, 20 Oct):** Fable samples come first, and **Lewis training is paused** at step 3300 (rolling checkpoint kept; the best evaluated checkpoint is step 3000). I stopped it at 10:16 UTC instead of finishing to 3500, because it was slowing the Fable work to a crawl on the shared CPU. Further Lewis steps may be moot if the owner picks Fable.
**Done: `fable-deeper/`** (pushed). There are 9 Fable teacher variants: −1/−2/−3/−4 st, −2 st "mature" (formants −4%), formants −6% and −10% at the same pitch, and a crude post-shift. Each has the 4 sample lines and the 10 audition lines, per-line plus joined MP3s, and a README with F0, UTMOS, similarity and accent.
- Key finding: Lewis and Fable already share the same median pitch on the sample lines (115 Hz). Chatterbox only partly follows a deeper reference, and similarity to Fable falls fast with depth.
- Suggested listening: −2 st mature, −3 st, formants −6%.

**Done: `audition-ready/`** (pushed): 24 ready-made voices with scores and a top 3. **Top pick: Kokoro blend bm_fable 0.7 + bm_lewis 0.3**: deeper than Fable (104 vs 108 Hz), keeps Fable's character (similarity 0.65), UTMOS 4.38 (above the Chatterbox teacher's 4.34), CPU RTF 0.39 here, and it works in Home Assistant today via Kokoro-FastAPI and wyoming_openai with no training. Second: the Fable/Lewis 50/50 blend; third: Fable 60 / Lewis 20 / George 20.
**Student option (c), desk audit:** Kokoro fine-tuning exists as a community StyleTTS2 recipe (`semidark/kikiri-tts`, reportedly Apache-2.0), but it needs a GPU; it is impractical on this CPU-only sandbox. A CPU-feasible middle path is to optimise a Kokoro *voice pack* towards the chosen teacher voice.
**Waiting on the owner:** which Fable depth to distil. No big generation run starts until then.
**Earlier, Lewis round 2, step 3000:** First round-2 result (59 eval-only lines: the 42 from round 1 plus 17 new):

| model | UTMOS | WER | sim → teacher | MCD |
|---|---|---|---|---|
| round 1 (step 2500), default noise | 4.09 | 4.3% | 0.850 | 27.9 |
| round 1, noise_scale 0.5 | 4.11 | 3.4% | 0.853 | 27.6 |
| round 2 step 3000, default noise | 4.11 | 2.4% | 0.851 | 28.0 |
| round 2 step 3000, noise_scale 0.5 | 4.13 | 3.6% | 0.840 | 27.5 |

So far the gain is small (about +0.02–0.04 UTMOS, near noise). WER is better on the house names. Two more 500-step stages will show whether it keeps rising; if not, I'll stop at the plateau.
**Corpus (final):** **1,412 accepted clips, 96.7 min** (round 1: 570 clips, 37.0 min). Rejected attempts: 245; 79 sentences still fail after one retry, all logged.
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
