# voice-lewis-small: a CPU-fast voice distilled from "Lewis, expressive"

## Verdict

- **Fast enough? Yes, by a wide margin.** On this sandbox's CPU (4 vCPU Xeon @ 2.1 GHz, no GPU) the voice synthesises at a **real-time factor of 0.036 mean and 0.049 p95**, about 25× faster than real time. Pinned to one core it is the same (p95 0.045). The target was p95 ≤ 0.7 on a modern 8-core desktop. It uses **~185 MB RAM** for a single reply (~340 MB in the timing harness), and the model is 64 MB. For comparison, the teacher runs at RTF 6.4 and uses 6.8 GB.
- **Sounds like Lewis? Close, but not the same. Judge by ear.** On held-out text and the four sample lines, the measures put the student next to the teacher:
  - Speaker similarity to the teacher's voice is 0.84 overall and 0.90 on the four sample lines. The teacher scores 0.87 against its own other clips.
  - Median pitch is the same (96 vs 99 Hz).
  - Pitch movement is about the same (3.7 vs 3.8 semitones).
  - Pace is about the same (3.71 vs 3.78 words per voiced second).
  - Words are clear: WER 0.9%, against the teacher's 1.6%.

  **The remaining gap is naturalness: UTMOS 4.06 vs the teacher's 4.34.** Expect a smoother, slightly more "synthesised" Piper/VITS texture, and less of Chatterbox's breathy, human phrasing. I could not listen to any of this, so these are proxies, not a judgement of warmth or wit. Compare `samples/lewis-small-N.mp3` with `samples/teacher-chatterbox-kokoro-lewis-ref-N.mp3`.
- **No real person's voice is involved.** The teacher is Chatterbox conditioned on a 10 s *synthetic* Kokoro bm_lewis clip. Its sha256 `0a726d38e17dbce88b0bbe54ee4f070d334cbfa7f091da23abfc9f8d373f9ff1` was verified before use. The student was trained only on the teacher's synthetic output.

## What's here

| Path | What |
|---|---|
| `model/en_GB-lewis_small-medium.onnx` + `.onnx.json` | **The voice.** Piper medium (VITS), 22,050 Hz, espeak-ng `en-gb-x-rp` phonemes. Drop-in for any Piper ≥ 1.x runtime, including the Wyoming Piper add-on. |
| `samples/lewis-small-{1..4}.mp3` | The four sample lines, rendered by the student (held out from training). |
| `samples/teacher-chatterbox-kokoro-lewis-ref-{1..4}.mp3` | The owner's chosen teacher samples (copied from `voice-samples`), for side-by-side listening. |
| `scripts/speak.py`, `scripts/atlas_text.py` | Text → WAV with the voice, plus a small spoken-form normaliser for times, money, °C, %, units and decimals (see "Using it"). |
| `checkpoint/lewis_small-step2500-generator-fp16.pt` | Generator weights (fp16, 48 MB) for continuing training (see "What's left"). |
| `corpus/` | All corpus **text**: training families, held-out families, dev sentences, sample lines and `manifest.tsv` (ids, seeds). `teacher_run/` holds the teacher log, the scores, the accepted list and every reject with its reasons. No audio. |
| `configs/` | `filter.json` (corpus acceptance thresholds), `piper_train.yaml` (training). |
| `scripts/` | The whole pipeline (below). |
| `eval/` | Step 1 audition, per-checkpoint and final comparisons, raw scores, speed logs. |
| `STATUS.md` | Progress log written during the run. |

## Using it

```sh
pip install piper-tts            # 1.8.0 used here; CPU only, ONNX Runtime
python scripts/speak.py "Good evening. Battery at 80%, dryer at 8:30 pm." out.wav
# or plain Piper (skips atlas_text normalisation):
echo "Done. Study lights off in ten minutes." | piper -m model/en_GB-lewis_small-medium.onnx -f out.wav
```

- **Home Assistant:** copy both `model/` files into the Wyoming Piper add-on's data/voices folder (or point a `wyoming-piper` container's `--data-dir` at it) and choose `en_GB-lewis_small-medium`.
- **Text normalisation:** the voice was trained on spoken-form text ("half past six", "twelve dollars and fifty cents"). espeak reads plain numbers and "80%" correctly, but it reads "6:05" as "six zero five", "$12.50" as "dollar twelve point five zero" and "21°C" as "degrees C". Pass Atlas's text through `atlas_text.normalise()` (pure Python), as `speak.py` does, or do the same expansion upstream.
- **Pace:** `length_scale` in the `.onnx.json` is 1.0, which already matches the teacher's pace. Use 1.05–1.1 for even more unhurried.

## Metrics

All measures are on text never seen in training: 30 clips from two held-out families (`garden_pets`, `travel`), 8 dev sentences and the four sample lines. Measures:
- **UTMOS22-strong:** predicted naturalness, 1–5.
- **WER:** Whisper small.en with Whisper's English normaliser (numbers compared exactly).
- **Speaker similarity:** ECAPA-TDNN cosine, to the reference clip and to the centroid of the teacher's renders of the same eval set.
- **MCD:** same-text mel-cepstral distance after DTW vs the teacher. Lower is closer; rough dB scale.
- **Pitch:** median F0, and spread in semitones (expressiveness).
- **Pace:** words per voiced second.

**All 42 eval clips:**

| system | UTMOS | WER | sim → ref | sim → teacher | MCD vs teacher | median F0 | F0 spread (st) | words/s |
|---|---|---|---|---|---|---|---|---|
| teacher (Chatterbox, exag 0.4 / cfg 0.4) | 4.34 | 1.6% | 0.812 | 0.871 † | 0 | 99 Hz | 3.80 | 3.78 |
| Piper base (northern_english_male, untrained) | 4.02 | 4.0% | 0.100 | 0.088 | 44.0 | 110 Hz | 2.40 | 4.23 |
| student step 500 | 3.99 | 2.2% | 0.758 | 0.799 | 29.6 | 92 Hz | 2.83 | 3.99 |
| student step 1000 | 4.06 | 1.2% | 0.769 | 0.831 | 28.5 | 94 Hz | 2.62 | 3.99 |
| student step 1500 | 4.07 | 1.1% | 0.790 | 0.846 | 28.5 | 99 Hz | 3.00 | 3.96 |
| student step 2000 | 4.10 | 1.3% | 0.778 | 0.837 | 28.3 | 98 Hz | 3.15 | 3.96 |
| **student step 2500 (delivered)** | **4.06** | **0.9%** | 0.771 | **0.837** | **27.9** | 96 Hz | **3.70** | **3.71** |

† Leave-one-out: each teacher clip against the centroid of the *other* teacher clips.

**The four sample lines only:**

| system | UTMOS | WER | sim → teacher | MCD vs teacher | F0 spread (st) | words/s |
|---|---|---|---|---|---|---|
| teacher (owner's chosen MP3s) | 4.34 | 3.6% ‡ | 0.877 † | 0 | 4.32 | 3.46 |
| **student step 2500** | 4.06 | 0.0% | 0.899 | 27.3 | 3.66 | 3.54 |

‡ Whisper hears line 3's "Done" as "Dumb" in the teacher sample, as the `voice-samples` README noted.

The student's similarity to the teacher's *centroid* can exceed the teacher's own leave-one-out score because a VITS student renders an "average" of the teacher. It does not mean the student is more Lewis than the teacher. Per-subset tables are in `eval/student_vs_teacher_by_subset.md`.

**Step 1 gate (lighter options, 8 dev sentences, same reference):**

| option | CPU RTF mean / p95 | peak RAM | sim → teacher | MCD | why rejected |
|---|---|---|---|---|---|
| Chatterbox Turbo (350M) | 2.37 / 3.18 | 6.2 GB | 0.819 | 29.6 | ~3× slower than real time; ignores exaggeration/cfg |
| Kokoro-82M bm_lewis (speed 0.92) | 0.37 / 0.42 | 1.8 GB | 0.792 | 33.3 | fast, but flatter and deeper (84 Hz, 3.4 st): the voice the owner already passed over |
| Pocket TTS 3.3, cloning the reference | **NO DATA** | — | — | — | voice-cloning weights are gated on Hugging Face (terms + token); not available here. A catalog voice ran at RTF 0.59 but is a different speaker (sim 0.28) |
| (teacher, for scale) | 5.93 / 12.79 | 6.8 GB | — | — | — |

On the same 8 dev sentences, the delivered student scores sim → teacher **0.862** and MCD **27.1**, closer than both Turbo and Kokoro.

**CPU speed of the delivered model** (42 eval lines, 1.6–8.7 s each; `eval/final_model_speed.jsonl`):

| setting | RTF mean | RTF p50 | RTF p95 | peak RSS |
|---|---|---|---|---|
| 4 vCPU (ONNX Runtime default) | 0.037 | 0.036 | 0.049 | 343 MB |
| pinned to 2 cores | 0.037 | 0.036 | 0.045 | 344 MB |
| pinned to 1 core | 0.036 | 0.036 | 0.045 | 340 MB |

Not measured on the owner's 8-core desktop (**NO DATA**). Expect it to be at least this fast.

## How it was made

1. **Gate** (`scripts/audition.py`): see the table above. No lighter option was both teacher-like and fast, so I distilled.
2. **Teacher corpus** (`scripts/build_manifest.py`, `gen_numbers.py`, `teacher_generate.py`):
   - 594 original sentences in 10 families: phonetic coverage, household status, Australian household vocabulary, hand-written and templated spoken numbers/times/percentages/money, short confirmations, questions, reminders, restrained dry wit, and longer briefings.
   - Teacher: Chatterbox 0.1.7 (`ResembleAI/chatterbox` @ `5bb1f6ee`), conditioned on the verified reference, exaggeration 0.4, cfg_weight 0.4, other settings default.
   - Seeds: `torch.manual_seed(crc32(id) + attempt)` before each clip; the Perth watermark is kept (library default).
   - Masters are kept as 24 kHz 24-bit FLAC.
   - Teacher speed on the first 30 clips: RTF 6.4 mean, 7.5 p95. Throughput was 15% better as 2 processes × 2 threads.
3. **Filter** (`scripts/score_clips.py`, `recheck_asr.py`, `filter_corpus.py`, `configs/filter.json`). A clip is accepted only if all of these hold:
   - **Words:** Whisper WER ≤ 5% with every number and critical word (on/off/locked/not/…) exact. small.en is used first; medium.en is a second opinion before blaming the audio.
   - **Speaker:** ECAPA similarity to the reference ≥ 0.65 (≥ 0.45 for clips under 2 s, whose embeddings are noisier). Calibration: teacher clips median 0.82 and p1 0.67 for long clips, median 0.63 and p5 0.46 for short clips; 11 other voices from `voice-samples` score ≤ 0.27. Only Kokoro bm_lewis itself, the source of the reference, scores higher (0.85).
   - **Naturalness:** UTMOS ≥ 3.5.
   - **Artefacts:** no clipping; no internal pause > 1.2 s; ≤ 0.3 s of sound outside Whisper's word span (trailing babble); 1.3–5 words per voiced second (rushed or garbled).

   Rejected sentences got one retry with seed + 1. **Result: 570 of 594 sentences accepted, 37.0 min** (pilot target 30–45 min). 82 rejected attempts are logged with reasons: ASR 53, rushed 20, UTMOS 14, speaker 9, stray sound 5. The 24 still missing are mostly one- or two-word confirmations ("Sorted.", "Noted.", "Got it.") that the teacher clipped or slurred, plus "one dollar eighty-nine". Piper copies are mono 22,050 Hz with edge silence trimmed (`prepare_piper.py`).
4. **Student** (`scripts/train_student.sh`, `piper_fit.py`, `configs/piper_train.yaml`):
   - Code: OHF-Voice piper1-gpl @ `619f513`, Piper medium, warm-started with `--model.warmstart_ckpt` (all 784 tensors) from `rhasspy/piper-checkpoints` `en/en_GB/northern_english_male/medium/epoch=9029-step=2261720.ckpt` (sha256 `39a47097…815585`, dataset revision `37d1bea2`).
   - **Why this base and not `lj-med_1000`:** it is a British male voice already trained on `en-gb-x-rp` phonemes, so less has to change. On this CPU every 500 steps costs ~45 min, so the head start matters. The licence is clear enough for personal home use, with a caveat (see Licences). LJSpeech (public domain, US female) is the clean-licence alternative: pass `lj-med_1000.ckpt` as the base argument of `train_student.sh`.
   - Settings: batch 16, CPU, fp32, lr 2e-4, checkpoints every 500 steps. Lightning counts 2 steps per batch (generator + discriminator), so 2,500 steps = 1,250 batches ≈ 37 epochs.
   - It trained in 500-step stages, evaluating held-out text between stages (table above), and was extended while the results improved. Step 2500 is delivered: best MCD, WER, pitch movement and pace, with speaker similarity level with step 2000 and UTMOS within noise of the best (4.10 at step 2000).
5. **Evaluate** (`scripts/eval_checkpoint.sh`, `student_synth.py`, `compare.py`).

## Run time

About 10.5 h wall clock on the 4-vCPU sandbox:
- Gate: ~1 h.
- Teacher corpus: ~4 h, including ~35 min lost to an out-of-memory kill.
- Filtering: ~0.5 h.
- Training: ~4 h for 2,500 steps; one more OOM restart cost ~10 min.
- Evaluation and packaging: ~1 h.

Teacher compute was ~7.6 process-hours. Training ran at 8–13 s per batch.

## Versions

- chatterbox-tts 0.1.7, resemble-perth 1.0.1, torch 2.6.0+cpu.
- pocket-tts 3.3.0 (torch 2.14.1).
- kokoro 0.9.4 / misaki 0.9.4 (`hexgrad/Kokoro-82M` @ `f3ff3571`).
- piper1-gpl @ `619f513` (piper-tts 1.8.0, lightning 2.6.6, espeak-ng @ `724808c` built in).
- onnxruntime 1.31.0.
- faster-whisper 1.2.1 (`small.en` @ `d1d751a5`, `medium.en` @ `a29b04bd`).
- speechbrain 1.0.3 (`spkrec-ecapa-voxceleb`).
- SpeechMOS v1.2.0 `utmos22_strong` (sha256 `38aa51ab…1e9bff`).
- Python 3.11, Linux x86-64.

## Licences (my reading, not legal advice)

- **The voice model:** fine-tuned from Piper `northern_english_male`. Its training data, OpenSLR 83, is **CC BY-SA 4.0**. That checkpoint was itself fine-tuned from Piper's `lessac` voice, whose Blizzard 2013 Lessac data has [its own licence](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html), which I did not review. **Treat the model as fine for personal home use. Check that licence, or retrain from public-domain `lj-med_1000`, before any commercial or public use.** If you share it, attribute OpenSLR 83 and share alike.
- **The training audio** was generated by Chatterbox (MIT) from a Kokoro-82M (Apache-2.0) reference.
- **The Piper code/runtime** is GPL-3.0 (piper1-gpl).
- **The student's output carries no watermark.** The teacher's Perth watermark is not learned or reproduced.
- **The corpus text** is original, written for this project.
- **Evaluation tools:** Whisper MIT, SpeechBrain/ECAPA Apache-2.0, UTMOS MIT; `scripts/third_party/english_normalizer.py` is Apache-2.0 (OpenAI/Hugging Face).

## Hashes (sha256)

```
45034e996ddbf8a91b95b13881f2bac6a184b20269d14a43d0a994b8bafa14c3  model/en_GB-lewis_small-medium.onnx
9be375ea48f12b03aaeeaa8f889cc720da050047651dfb38f1fe31edf8541952  model/en_GB-lewis_small-medium.onnx.json
5b189a7d25e0bc273a825d6d1c80948704fadf6987aa1dca80eb6e3725449d7d  checkpoint/lewis_small-step2500-generator-fp16.pt
2d0af11bc306b7b194435c0d71ad14927a9ff4a41b79a2213e9b3a790ae6b7a7  samples/lewis-small-1.mp3
dc31f4635043076a4fe65a923efd27c74c609ebd259e7e41f707c1d1dc21560d  samples/lewis-small-2.mp3
3a3e11c881754f3f1bd3d51a4bf72dfb3ff2b1af69d9d795afc001f4dcb77e99  samples/lewis-small-3.mp3
dcb737c11134d59e78fecf5c4c56887757d6f02c3c885ca844e5e310ffd97beb  samples/lewis-small-4.mp3
0a726d38e17dbce88b0bbe54ee4f070d334cbfa7f091da23abfc9f8d373f9ff1  (input) voice-samples/refs/kokoro-bm_lewis.wav
39a4709778f6c9f58ddf0e7f5b55eaf3f2c3993698ebb61bdf12664e43815585  (input) northern_english_male medium base checkpoint
```

## What's left / NO DATA

- **Listening.** Every judgement above is an objective proxy; the owner decides by ear. If the student sounds too smooth or too even, the next lever is more data and more steps, not a different model.
- **More training.** Results were still moving at step 2500, mainly pitch movement and pace. To continue, a later session needs:
  - the corpus audio, regenerated from `corpus/manifest.tsv` with `scripts/teacher_generate.py`. Seeds are fixed, but bit-identical output across machines and torch versions isn't guaranteed. The masters (113 MB) and the full checkpoint (846 MB, with optimiser state) were too big to commit.
  - a warm-start checkpoint, built with `python scripts/make_warmstart.py merge checkpoint/lewis_small-step2500-generator-fp16.pt <northern_english_male ckpt> warm.ckpt`, then `scripts/train_student.sh <dataset> <out> warm.ckpt`. This keeps the generator but starts with a fresh optimiser and the base's discriminator, so expect a short wobble.
- **A bigger corpus.** The brief's stretch goal was ~2 h of teacher audio. The pilot stopped at 37 min because the teacher costs ~6× real time on this CPU (~12 h of teacher compute for 2 h of audio). Short confirmations are the weakest family: 11 of 59 were rejected.
- **NO DATA:**
  - Pocket TTS with the reference (gated weights).
  - Speed on the owner's 8-core desktop.
  - Speed on a GPU.
  - Wit and warmth, which no metric here measures.
- `atlas_text.normalise` covers the common forms only: times, money, °C, %, kWh/kW, km and km/h, mm, negatives, decimals. Ordinal dates ("14th") and phone numbers are left to espeak.
