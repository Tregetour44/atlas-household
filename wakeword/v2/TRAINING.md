# Hey Atlas v2: training and evaluation record

## Verdict

**v2 is worse than v1. v1 stays the model; only its cut-off changes.** v2 was trained in one run on accented, far-field and hard-negative synthetic data. Its validation-only choice detects **62%** of v1's validation "Hey Atlas" clips against v1's **91%**. On the new far-field accented validation set it detects **30%** against v1's **32%**. To keep 0 false accepts on the 9.67 h validation ambient set, v2 had to sit at a high cut-off, which cost recall. So the "better model" in the brief's sense is **v1**, and the cut-off work (option 3) uses v1.

What v2 did improve, at its chosen setting: hard negatives. On held-out voices and texts, far field: "Atlas" mid-sentence 0/484, "hey Alice" 0/82, "hey Alex" 0/148 and "at last" 0/200. It got there by being deaf, not by being smarter, so it is not shipped.

**The far-field result is the main news for the owner.** On a new simulated set (talker 2–5 m away in a living room, TV, music or kitchen noise at 0–20 dB, voices never trained on, Australian, NZ and British weighted up), v1 detects only **27%** at today's cut-off 0.93, and **32%** at the recommended 0.85. Near-field it detects 90%. That fits "slow to wake" across a room with the TV on. A lower cut-off helps a little; it does not fix far-field.

All speech here is synthetic. Real recall in the house (real voices, the Voice PE's microphones and its XMOS front end, which does its own noise suppression and gain) is **NO DATA**. The simulated far-field set has no beamforming or echo cancellation, so it is probably harsher than the real device.

## v1 against v2 (test sets, each at its validation-chosen setting)

Same evaluation code as v1 (`../scripts/evaluate.py`, `../scripts/choose.py` detector), same runtime (LiteRT) for both. v1: W=3, cutoff 0.93 (as shipped). v2: checkpoint 24000, W=5, cutoff 0.95 (`results/run2/choice.json`).

| Test set | v1 | v2 |
| --- | --- | --- |
| v1's test positives (near-field, LibriTTS-R test voices), recall | **90.1%** (3242/3600) | 54.2% (1951/3600) |
| v1's test hard negatives, accepts | 5.6% (45/800) | **0.9%** (7/800) |
| Far-field accented test positives (new), recall | 27.1% (502/1850) | **28.2%** (522/1850) |
| … of which the held-out Australian voice (VCTK p326, alone or mixed) | **17.1%** (36/211) | 11.8% (25/211) |
| Far-field test hard negatives (new: "Atlas" mid-sentence, hi/pay Atlas, hey Alice/Alex, at last, v1's confusables), accepts | 6.6% (115/1750) | **3.9%** (68/1750) |
| DiPCo test ambient (5.33 h), false accepts per hour | 0.00 /h (0) | 0.00 /h (0) |
| Simulated TV, test (2.00 h), false accepts per hour | 0.00 /h (0) | 0.00 /h (0) |

(v1 on TFLite Micro, ESPHome's runtime, gives 1 DiPCo false accept at 0.93, 0.19 /h, as in v1's own record; LiteRT gives 0. The two runtimes differ by a few uint8 steps on rare frames.)

Validation (what the choice saw): v1 at 0.93: 91.1% / 31.7% recall (v1 sets / far-field), 5.6% / 6.9% hard-negative accepts, 0 false accepts on CHiME-6 9.67 h and 0 on 2 h TV. v2 chosen: 61.8% / 29.9%, 2.1% / 3.4%, 0 and 0.

**Choice rule for v2, as fixed before any v2 checkpoint was scored** (`scripts/choose_v2.py`): 0 false accepts on CHiME-6 validation (9.67 h) and on validation TV (2 h); at most 3% accepts on v1's validation hard negatives and at most 5% on the far-field validation hard negatives; then the highest mean validation recall (v1 set and far-field set). The 3% cap is v1's. On the regenerated sets v1 itself accepts 5.6% at 0.93, so the cap is stricter than today's model. **Checked afterwards, and not used for the choice:** with caps relaxed to v1's own validation rates (5.6% and 6.9%), v2's best is checkpoint 26000, W=5, 0.97: 70.3% / 33.3% validation recall. That is still far below v1's 91.1% near-field, and only +1.6 points far-field. The verdict does not depend on the cap. No v2 setting reaches 85% validation recall with 0 validation false accepts (`results/run2/choice_sweep.csv`, every checkpoint × W × cut-off).

Why v2 lost (likely causes; not separately measured): (1) its window is 2.4 s, not 3.78 s, after the first attempt failed (below); (2) 65% of its positives were far-field with TV, babble or music at 0–15 dB, which seems to teach it to accept speech-like noise, so it needed high cut-offs to keep CHiME-6 dinner-party speech quiet; (3) disk allowed only one of v1's two VOiCES speech-negative sets (far, not mid).

## v1 operating points (option 3)

v1 on **TFLite Micro** (ESPHome's runtime), W=3, every set (`results/v1/v1_ops_all_tflm.csv`). The device threshold is `int(cutoff × 255)`, checked in ESPHome 2026.9.1's `micro_wake_word/__init__.py` (`quantized_probability_cutoff = int(probability_cutoff * 255)`; same wheel hash as the build lock), so 0.90 → 229 and 0.85 → 216 are exact.

| Cut-off (u8) | Recall, v1 test (near) | Recall, far-field accented test | Hard-neg accepts, v1 test / far-field test | FA CHiME-6 val 9.67 h | FA DiPCo test 5.33 h | FA TV val + test 4 h |
| --- | --- | --- | --- | --- | --- | --- |
| **0.93** (237), today | 90.1% | 27.2% | 5.5% / 6.6% | 0 (0.00 /h) | 1 (0.19 /h) | 0 |
| 0.90 (229) | 91.8% | 29.0% | 6.9% / 7.4% | 2 (0.21 /h) | 1 (0.19 /h) | 0 |
| **0.85 (216), recommended** | **93.6%** | **31.7%** | 8.5% / 8.3% | 4 (0.41 /h) | 1 (0.19 /h) | 0 |
| 0.80 (204) | 94.5% | 34.2% | 10.1% / 9.1% | 6 (0.62 /h) | 4 (0.75 /h) | 1 |

Validation recall (v1 set / far-field set): 91.0 / 31.9% at 0.93, 92.6 / 33.7% at 0.90, 94.0 / 37.2% at 0.85, 95.0 / 39.6% at 0.80.

**Recommendation: 0.85.** It is the most responsive setting before false accepts climb on both dinner-party sets. From 0.85 to 0.80, DiPCo goes from 1 to 4 and TV from 0 to 1, for about one more point of recall.

**Extra false wakes to expect at 0.85**, from these synthetic and recorded sets: across the 15 h of dinner-party audio (CHiME-6 val and DiPCo), 5 false accepts against 1 at 0.93. That is roughly **one extra false wake per 4 hours of lively conversation in the room**: 0.33 /h against 0.07 /h. None in 4 h of simulated TV. Saying the name in passing triggers more often:

| Phrase (test voices, not trained on) | 0.93 | 0.85 |
| --- | --- | --- |
| "hi Atlas", near / far | 54/109 / 21/109 | 64/109 / 25/109 |
| "pay Atlas", near / far | 68/117 / 30/117 | 73/117 / 40/117 |
| "hey Alice", near / far | 20/117 / 13/117 | 26/117 / 20/117 |
| "hey Alex", near / far | 7/93 / 8/93 | 13/93 / 9/93 |
| "at last", near / far | 0/124 / 0/124 | 1/124 / 2/124 |
| "Atlas" mid-sentence (far, 484 clips) | 2 | 5 |
| "the atlas" (v1 probe set, near, 16 clips) | 10 | 11 |

"near" and "far" use the same weak-spot probe clips, from new voices (Piper VCTK, ARU and Kokoro test voices), with v1's near-field augmentation or the far-field rooms (`test_weak_near`, `test_weak`).

## What was done

### Data (all synthetic speech; v1's tools and pins)

| | Train | Validation | Test |
| --- | --- | --- | --- |
| Positives, LibriTTS-R (Piper generator, v1's 640/80/80 voice split) | 20,000 | 400 | 400 |
| Positives, Piper `en_GB-vctk-medium` (109 speakers; Australian p374 and NZ p335 in train, Australian p326 held out for test) | 9,000 | 500 | 500 |
| Positives, Kokoro-82M (28 voices: 20 train, 4 validation, 4 test) | 4,000 | 400 | 400 |
| Positives, Piper `en_GB-aru-medium` (12 UK speakers: 10 / 1 / 1) | 3,000 | 250 | 250 |
| Positives, Piper single GB voices (alba, northern_english_male → train; cori → validation; southern_english_female → test) | 2,000 | 300 | 300 |
| Hard negatives, all engines | 21,500 | 1,750 | 1,750 |
| Weak-spot probes (5 phrases, VCTK/ARU/Kokoro test voices) | | | 560 |

* **Voices.** Multi-speaker Piper models are edited once so the speaker embedding is an input (`scripts/synth_onnx.py`). A clip is one speaker or a SLERP mix of two speakers *of the same split*, as v1 does with LibriTTS-R. Kokoro voices are blended linearly the same way. Australian, NZ and British VCTK speakers are listed 2–8 times in the plan, so they are drawn and mixed more often (`plans/`, `scripts/make_plans.py`). VCTK accents come from the dataset's speaker metadata (`checks/vctk_speakers.json`).
* **Accents and casual speech.** v1's templates keep v1's splits exactly (so v1's validation and test templates never enter v2 training). New families have their own 80/10/10 split (`scripts/templates_v2.py`): 15 more Australian-sounding IPA variants ([hæɪ]/[ɐɪ]/[æe], [ɐ]/[ɪ] in "-las", glottal t), 6 New Zealand ([ɛ] in "At-", [ɘ] in "-las"), 6 casual ([hɛ], unstressed or fast "hey", "hey, atlas"), and the espeak-ng Lancashire, West Midlands and RP voices. Positives sample families with weights au 2, au2 3, nz 1.5, casual 1.5, gb 1.5, gb2 1.5, us 1, other 0.5. Pace: length scale 0.75–1.5 (Kokoro speed 0.67–1.33). Loudness: gain −30…0 dB, plus a "soft voice" high-shelf cut of 3–9 dB above ~1 kHz on 30% of clips.
* **Hard negatives.** v1's 127 texts (v1 splits) plus 2,050 sentences with "Atlas" mid-sentence, made from 47 frames such as "ask Atlas about {topic}", "the atlas on the {place}" and "{person} said Atlas {did something}" (split by frame, so no frame crosses splits). Added: hi/hiya Atlas, pay Atlas, hey Alice, hey Alex and at last, 8–10 variants each. Every text is checked never to contain "hey" followed by "atlas". Group weights: mid-sentence 4, hi Atlas 1.5, at last 1.5, the rest about 1.
* **Far field.** `scripts/gen_farfield_assets.py` uses pyroomacoustics: 100 training rooms, 60 validation and 60 test rooms, plus 12 more rooms per split for the long TV streams. Each room: 3.5–7.5 × 3–6 × 2.4–3 m, RT60 0.25–0.8 s, image-source method up to order 17, device 0.7–1.2 m high (60% against a wall), talker 2–5 m away, TV 1–4.5 m away against a wall, a side source 2–6 m away. Noise scenes are rendered through each room's own TV or side RIRs: broadcast-style talk with a loudspeaker band limit and compression, sometimes with a music bed; music; kitchen (clatter, running water, extractor fan, recorded noises); babble. In `scripts/make_features_v2.py`, 65% of training clips are far-field, mixed at 0–15 dB (TV, music), 3–20 dB (kitchen), 3–15 dB (babble) or 25–35 dB (quiet), plus a second scene in a quarter of clips. The other 35% get v1's augmentation unchanged. Positives and negatives get the same treatment. **The far-field validation and test sets are 100% far-field.** Two of the three training-room jobs were killed out of memory, so training has 100 rooms and 300 scenes, not the planned 300 and 900.
* **Broadcast-style speech: MUSAN** (OpenSLR 17, CC BY 4.0; its README: every file is Creative Commons or US public domain, with no non-commercial content). Streamed, keeping a bounded subset: 4.0 h US-government hearings, 1.0 h LibriVox, 6.0 h music, 3.0 h noise (`checks/musan_fetch_log.txt`, archive SHA-256 `86d1061c…55ee1`). Split by file 80/10/10. Used inside the room scenes, as 300 training scene negatives, and as the continuous TV streams (12 × 10 min per split) for false accepts per hour on TV. The validation and test TV streams reuse only 3 MUSAN talk files each, so they are not very varied.
* **Negatives from v1:** the same Hugging Face revision and zip hashes. **Only VOiCES "far"** is used for speech (v1 also used "mid"), because of disk.

### Training (one kept run)

v1 candidate B's recipe (`configs/v2.yaml`, `results/run2/training_config_resolved.yaml`): mixednet with the notebook's flags, batch 128, class weights 1/20, hard negatives sampling 4 / penalty 2, the scene negatives at weight 3, SpecAugment, 40,000 steps (20k at 1e-3, 12k at 5e-4, 8k at 2e-4). It took 83 minutes on 4 CPU cores. Every 2,000th checkpoint from 10,000 to 40,000 (16) was exported and streamed over every set.

**A first attempt was aborted at step 14,000** (`results/aborted_run1/`). Positives were rendered 4.0 s long (400 frames), so v1's 378-frame window always began about 0.15 s into a clip, inside the audio frontend's start-up transient. That transient falls from about 17 to about 1.5 (mean feature value) over the first 1–1.5 s. The model learned the transient as a cue for "Hey Atlas". Streamed, its recall collapsed to 14%. The test: the same validation clips with 2 s more lead-in fell from median peak 0.99 to 0.02. The kept run uses the same features with a **240-frame (2.4 s) window** (`clip_duration_ms: 2580`), which starts at least 1.5 s into every clip. At checkpoint 3000 the lead-in test was flat (0.90 against 0.92). The window covers phrases up to 2.11 s, about the 99th percentile of positive durations; the slowest ~1% lose the start of "hey".

### Evaluation

Every model, v1 included, is streamed by v1's `evaluate.py` over the same sets (`scripts/eval_v2.sh`). v1's validation and test sets were regenerated with v1's voices, templates, splits and augmentation seeds (synthesis seeds new). v1's recorded figures reproduce: 90.1% test recall against 90.5% recorded, 1 DiPCo false accept on TFLM. v1's regenerated probe set covers 83 of its 118 phrases ("hi Atlas" and "pay Atlas" were not drawn), so the weak-spot table uses the new probe set. The detector emulation is v1's (sliding-window sum, 100-inference refractory). ESPHome 2026.9.1's real cool-off is 100 *sub-threshold feature slices*, about 1 s (`streaming_model.cpp`, `MIN_SLICES_BEFORE_DETECTION`). The emulation can merge bursts that the device would count twice, so false-accept counts may be slightly low.

### Tools added in v2 (pinned)

| Tool / model | Version, hash | Licence |
| --- | --- | --- |
| piper-tts (ONNX runtime use), onnxruntime, onnx | 1.3.0, 1.31.0, 1.23.2 | GPL-3.0 (tool only), MIT, Apache-2.0 |
| kokoro-onnx | 0.6.1 | MIT |
| Kokoro-82M `kokoro-v1.0.onnx`, `voices-v1.0.bin` | SHA-256 `7d5df8ec…a6c5`, `bca610b8…7bf7d` | Apache-2.0 (model card) |
| Piper voices `en_GB-vctk-medium`, `-aru-medium`, `-alba-medium` | `4e9fc85a…41e6`, `9e74d089…2619`, `401369c4…d03b` | CC BY 4.0 (datasets VCTK, ARU, alba) |
| `en_GB-cori-high` | `470b4dd6…5903` | public domain (LibriVox) |
| `en_GB-northern_english_male-medium`, `en_GB-southern_english_female-low` | `57a219ae…0689`, `f2f37aed…c07c3` | CC BY-SA 4.0 (OpenSLR 83) |
| pyroomacoustics | 0.10.1 | MIT |
| MUSAN | OpenSLR 17 | CC BY 4.0 |

Full hashes: `checks/tts_models_sha256.txt`; model cards: `checks/*.MODEL_CARD`; environment: `checks/freeze-v2.txt`. The v1 environments were rebuilt from `../checks/pip_freeze.txt`. v1's TFLM environment also needs `mmap-ninja` 0.9.0, which its freeze list omits. Every Piper or Kokoro voice is used only to make training audio for this private model; no voice or audio is shipped.

### Run time

About 4 h 30 min of wall clock on 4 CPU cores (11:15–15:45 UTC on 2026-10-22): set-up and downloads 20 min; v1 set regeneration and scoring 25 min; v2 synthesis 1 h 55 min (Kokoro about 0.6 clips/s per core was the slowest); rooms and features 12 min; aborted attempt 25 min; kept training 83 min; checkpoint streaming overlapped with training.

### Files

| Path | What |
| --- | --- |
| `results/v1/` | v1 on all sets: `v1_ops_all_tflm.csv` (the operating-point table), `v1_breakdown_tflm_<cutoff>.json` (by engine, accent family, Australian voice, phrase, hard-negative group), LiteRT equivalents |
| `results/run2/` | the kept v2 run: `choice.json` (rule and choice), `choice_sweep.csv` (every checkpoint × W × cut-off, every set), `v2_chosen_*`, in-loop metrics, resolved config |
| `results/aborted_run1/` | the aborted attempt's config and in-loop metrics |
| `scripts/` | everything run, in order: `synth_v2.sh` (`synth_psg.py`, `synth_onnx.py`, `tmpl_build.py`, `templates_v2.py`, `make_plans.py`), `fetch_musan.py`, `gen_farfield_assets.py`, `features_v2.sh` (`make_features_v2.py`), `v1eval_features.sh`, `make_config_v2.py`, `train_v2.sh`, `eval_v2.sh`, `choose_v2.py`, `op_points.py`, `report_v2.py` |
| `plans/`, `configs/`, `checks/` | voice plans, training config, hashes, model cards, VCTK speaker metadata, MUSAN record |

No audio, features or model weights other than the shipped `../hey_atlas.tflite` are committed. v2's model is not committed, because it is not used.
