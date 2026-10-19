# voice-lewis-small: status

**Updated:** 2026-10-19 21:10 UTC (Tue 20 Oct, 08:10 Sydney)
**Step:** 3 of 4, student (Piper fine-tune), currently training from step 1500 to 2000. The gate and the corpus are done.
**On track:** yes. No blockers.

## Step 1 gate: done, no lighter option was good enough

The comparison used 8 fresh development sentences (`corpus/dev_sentences.txt`, not the four sample lines) and the same synthetic reference. The reference sha256 `0a726d38…f9ff1` was verified. CPU is this sandbox: 4 vCPU Xeon @ 2.1 GHz, no GPU. RTF = synthesis time ÷ audio length, so below 1 is faster than real time.

| Option | CPU RTF (mean / p95) | Peak RAM | Speaker similarity to teacher (teacher vs itself 0.85) | Verdict |
|---|---|---|---|---|
| Chatterbox (the teacher) | 5.9 / 12.8 | 6.8 GB | — | the target; ~6–8× too slow |
| Chatterbox Turbo (350M), same reference | 2.4 / 3.2 | 6.2 GB | 0.82 | closest sound, but 3–4× slower than real time. Also ignores exaggeration/cfg. **Rejected: too slow.** |
| Kokoro bm_lewis (the voice the reference was made from) | 0.37 / 0.42 | 1.8 GB | 0.79 | fast, but it is the flatter, deeper (84 Hz vs 97 Hz), less expressive delivery the owner already heard and passed over. **Rejected: doesn't sound like the teacher.** |
| Pocket TTS 3.3 (Kyutai), cloning the reference | NO DATA | — | NO DATA | voice-cloning weights are gated on Hugging Face (terms + token); not available here. A built-in catalog voice ran at RTF 0.59 but is a different speaker (similarity 0.28). **Rejected: can't use the reference.** |

Details: `eval/step1_audition.md`, `eval/step1_audition_speed.jsonl`.

## Step 2 corpus: done

- 594 original training sentences in 10 families. Held out for evaluation only: the 2 families `garden_pets` and `travel`, the 8 dev sentences and all 4 sample lines.
- Teacher: Chatterbox 0.1.7, fixed reference, exaggeration 0.4, cfg 0.4, per-clip deterministic seeds, watermark kept.
- Teacher speed on the first 30 clips: RTF 6.4 mean, 7.5 p95.
- Filter: Whisper WER ≤ 5% with exact numbers and critical words (small.en, then medium.en as a second opinion); ECAPA speaker similarity to the reference ≥ 0.65 (≥ 0.45 for clips under 2 s; other voices score ≤ 0.27); UTMOS ≥ 3.5; artefact checks. One retry round with seed+1.
- **Accepted: 570 clips, 37.0 minutes** (pilot target 30–45 min ✓). 24 sentences still failed and are logged in `corpus/teacher_run/rejects.jsonl`.

## Step 3 student: in progress

- Base: Piper `en_GB/northern_english_male/medium`, a British male with en-gb-x-rp phonemes. The licence caveat will be in the README.
- Training on CPU at about 8–13 s per batch; 500 steps take about 45 minutes.

| Checkpoint | UTMOS | WER | Speaker similarity to teacher | MCD vs teacher | Median F0 | CPU RTF p95 |
|---|---|---|---|---|---|---|
| base (untrained) | 4.02 | 4.0% | 0.09 | 44.0 | 110 Hz | 0.05 |
| step 500 | 3.99 | 2.2% | 0.80 | 29.6 | 92 Hz | 0.05 |
| step 1000 | 4.06 | 1.2% | 0.83 | 28.5 | 94 Hz | 0.05 |
| step 1500 | 4.07 | 1.1% | 0.85 | 28.5 | 99 Hz | 0.05 |
| teacher (for reference) | 4.34 | 1.6% | 0.87 (vs. its own other clips) | 0 | 99 Hz | 6.4 mean |

These are on 42 eval-only clips. The student already runs about 20× faster than real time here (target p95 ≤ 0.7).

## Time left (estimate)

- Steps 2000 and 2500: about 1.5 h, extending only while held-out results improve.
- Step 4 (final evaluation, sample MP3s, README): about 45 min.
- Expected done: about 2.5 h from this update.
