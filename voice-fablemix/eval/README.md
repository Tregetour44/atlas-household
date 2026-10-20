# Quality and parity report

Engine: **ONNX Runtime 1.31 + onnx-community Kokoro-82M v1.0 fp32 ONNX**, fed misaki 0.9.4 British (`lang_code="b"`) phonemes, voice pack `en_GB-fablemix` (the voice-scout Fable-mix pack, bit-identical values), speed 0.95.

## How it was measured

The metrics are the voice-scout's, on the same models and settings (`tools/lab/eval.py`, which reuses `voice-lewis-small/scripts/metrics.py`):
- **UTMOS** (UTMOS22 strong): predicted naturalness, 1–5.
- **Median F0 and F0 spread**: pYIN 55–320 Hz; the spread is the standard deviation, in semitones, around the median.
- **WER**: faster-whisper small.en, beam 5, with the voice-lewis-small normaliser (numbers and times canonicalised).
- **Eng−US**: SpeechBrain CommonAccent ECAPA, England logit minus US logit. "British" counts lines whose top class is England or Australia.
- **Speaker similarity**:
  - ECAPA-TDNN cosine to the scout's own MP3 of the same line (`sim_scout`; L and H lines only, since the scout rendered no others).
  - Resemblyzer cosine to the same clip (`rsim_scout`).
  - ECAPA / Resemblyzer cosine to the centroid of all 18 scout Fable-mix clips (every line).
  - ECAPA to the centroid of the household's liked Chatterbox-Fable clips (`sim_cbfable`, as the scout).

The line sets:
- **L**: the 10 audition lines (`voice-lewis-small/corpus/audition/audition_lines.txt`).
- **H**: the 8 held-out house-name lines (`heldout_r3/house_heldout.txt`, last 8).
- **A**: 20 owner-supplied Atlas reply shapes from `train_ext4/house_given.txt` (every other line or so, none of the held-out six).
- **W**: 12 lines built on the house words (Good Night, Wind Down, ensuite, pergola, atrium, kilowatt hours, ZeroCharge).
- **F**: 7 fix probes.
- **S**: 14 extra short replies.

All texts are in `tools/lab/*.tsv`.

The sandbox was a 4 vCPU Intel Xeon @ 2.1 GHz with 15 GB RAM and no GPU. I could not listen. Every judgement rests on these proxies; warmth, wit and naturalness of pauses need ears.

## 1. Engine parity: the same phonemes through PyTorch and ONNX

Whole line per inference, as the scout rendered it.
- `pt` is kokoro 0.9.4 `KModel` (PyTorch 2.14 CPU) with seed 1234; `ptB` is the same with seed 99. The difference between those two is PyTorch's own run-to-run spread, because Kokoro's sine source adds random noise.
- `pt0` is PyTorch with that noise zeroed.
- `ort32` is the raw ONNX output; `ort32g` is the same with the backend's −3.4 dB level correction.
- `ort8` is the onnx-community int8 file.

Our `pt` renders reproduce the scout's clips: ECAPA similarity to the scout's MP3 of the same line is **0.995–0.996**, and UTMOS on L is 4.472 against the scout's 4.473.

| voice | lines | utmos | f0 | f0_st | wer | eng_us | sim_cbfable | sim_scout | rsim_scout | British/US |
|---|---|---|---|---|---|---|---|---|---|---|
| pt | L (10) | 4.472 | 107.250 | 5.707 | 0.000 | 0.228 | 0.712 | 0.996 | 0.971 | 9/1 |
| ptB | L (10) | 4.470 | 110.160 | 5.062 | 0.000 | 0.236 | 0.714 | 0.996 | 0.972 | 10/0 |
| pt0 | L (10) | 4.474 | 109.460 | 5.230 | 0.000 | 0.230 | 0.711 | 0.993 | 0.970 | 9/1 |
| ort32 | L (10) | 4.472 | 109.080 | 5.390 | 0.000 | 0.231 | 0.709 | 0.987 | 0.987 | 9/1 |
| ort32g | L (10) | 4.473 | 109.080 | 5.390 | 0.000 | 0.231 | 0.709 | 0.987 | 0.964 | 9/1 |
| pt | H (8) | 4.464 | 110.463 | 5.647 | 0.047 | 0.244 | 0.664 | 0.995 | 0.968 | 7/1 |
| ptB | H (8) | 4.465 | 110.475 | 5.482 | 0.047 | 0.229 | 0.666 | 0.994 | 0.968 | 7/1 |
| pt0 | H (8) | 4.464 | 110.938 | 5.536 | 0.047 | 0.242 | 0.665 | 0.990 | 0.966 | 7/1 |
| ort32 | H (8) | 4.451 | 110.788 | 5.482 | 0.047 | 0.244 | 0.662 | 0.983 | 0.984 | 7/1 |
| ort32g | H (8) | 4.458 | 110.788 | 5.482 | 0.047 | 0.244 | 0.662 | 0.983 | 0.961 | 7/1 |
| pt | A (20) | 4.459 | 108.630 | 5.420 | 0.042 | 0.191 | 0.646 | — | — | 18/2 |
| ptB | A (20) | 4.460 | 109.110 | 5.537 | 0.027 | 0.199 | 0.643 | — | — | 18/2 |
| pt0 | A (20) | 4.459 | 108.005 | 5.588 | 0.027 | 0.174 | 0.648 | — | — | 18/2 |
| ort32 | A (20) | 4.456 | 108.450 | 5.485 | 0.042 | 0.190 | 0.645 | — | — | 17/2 |
| ort32g | A (20) | 4.457 | 108.450 | 5.485 | 0.027 | 0.190 | 0.645 | — | — | 17/2 |

All 38 lines:

| voice | lines | utmos | f0 | f0_st | wer | eng_us | sim_cbfable | sim_scout | rsim_scout | British/US |
|---|---|---|---|---|---|---|---|---|---|---|
| pt | all (38) | 4.464 | 108.653 | 5.543 | 0.032 | 0.212 | 0.667 | 0.995 | 0.970 | 34/4 |
| ptB | all (38) | 4.463 | 109.674 | 5.400 | 0.024 | 0.215 | 0.667 | 0.995 | 0.970 | 35/3 |
| pt0 | all (38) | 4.464 | 109.005 | 5.483 | 0.024 | 0.203 | 0.668 | 0.991 | 0.968 | 34/4 |
| ort32 | all (38) | 4.459 | 109.108 | 5.459 | 0.032 | 0.212 | 0.665 | 0.985 | 0.985 | 33/4 |
| ort32g | all (38) | 4.461 | 109.108 | 5.459 | 0.024 | 0.212 | 0.665 | 0.985 | 0.963 | 33/4 |
| ort8 | all (38) | 4.447 | 106.082 | 5.150 | 0.034 | 0.136 | 0.642 | 0.957 | 0.974 | 30/7 |

- **fp32 ONNX matches PyTorch within PyTorch's own seed spread** on every metric. It gives the same durations to the sample, because the duration predictor is identical.
  - After level correction, its log-mel distance to the PyTorch render is 0.75 dB. PyTorch run against PyTorch with another seed is 0.37 dB, and against its own noise-free run 0.55 dB.
  - Its ECAPA similarity to the scout's clips is 0.985 (PyTorch 0.995).
  - The graph has no random operators. That makes it deterministic, and the only difference from PyTorch is the missing excitation noise.
- **The ONNX export is a constant 3.38 dB louder** (median gain 1.475, range 1.462–1.487 over 38 lines), which put peaks at up to 0.985 FS. The backend multiplies by 0.678.
- **int8 is not faithful.** It changes durations, slips on accent (30/38 British vs 33–35), drops ECAPA similarity to 0.957, and was not faster here.
- **fp16 is broken on CPU.** It returned all-NaN audio for 8 of 38 lines (A02, A06, A07, A13, H08, L02, L03, L09), so it is not scored.

## 2. The shipped configuration against the scout's way of running it

`before` is the same engine as the scout ran it: whole line, no text fixes, the plain pack, Kokoro's own padding. `after` is `kokoro_backend.py` as shipped: sentence pieces with trimmed joins and real pauses, the short-reply pack, the lexicon and rewrites.

| voice | lines | utmos | f0 | f0_st | wer | eng_us | sim_cbfable | sim_scout | rsim_scout | British/US |
|---|---|---|---|---|---|---|---|---|---|---|
| before | L (10) | 4.473 | 109.080 | 5.391 | 0.000 | 0.231 | 0.709 | 0.987 | 0.965 | 9/1 |
| after | L (10) | 4.470 | 109.130 | 4.573 | 0.014 | 0.246 | 0.750 | 0.912 | 0.950 | 9/1 |
| before | H (8) | 4.458 | 110.788 | 5.482 | 0.047 | 0.244 | 0.663 | 0.983 | 0.961 | 7/1 |
| after | H (8) | 4.470 | 111.263 | 4.532 | 0.038 | 0.257 | 0.743 | 0.877 | 0.952 | 7/1 |
| before | A (20) | 4.457 | 108.205 | 5.499 | 0.027 | 0.190 | 0.644 | — | — | 17/2 |
| after | A (20) | 4.457 | 108.305 | 4.933 | 0.000 | 0.187 | 0.725 | — | — | 18/2 |
| before | W (12) | 4.416 | 111.250 | 5.472 | 0.058 | 0.255 | 0.628 | — | — | 11/1 |
| after | W (12) | 4.436 | 109.900 | 4.070 | 0.014 | 0.252 | 0.728 | — | — | 11/1 |
| before | F (7) | 4.170 | 125.043 | 4.133 | 0.000 | 0.177 | 0.451 | — | — | 5/2 |
| after | F (7) | 4.143 | 111.114 | 4.377 | 0.000 | 0.181 | 0.585 | — | — | 6/1 |

Similarity to the centroid of the scout's 18 Fable-mix clips (voice identity, all lines):

| set | ECAPA before → after | Resemblyzer before → after | PyTorch reference |
|---|---|---|---|
| L (10) | 0.874 → 0.871 | 0.936 → 0.943 | 0.887 / 0.939 |
| H (8) | 0.875 → 0.870 | 0.936 → 0.938 | 0.878 / 0.941 |
| A (20) | 0.866 → 0.854 | 0.930 → 0.930 | 0.872 / 0.935 |
| W (12) | 0.848 → 0.844 | 0.922 → 0.922 | — |

Reading this:
- **Naturalness is unchanged** (UTMOS 4.47 / 4.47 / 4.46 on L / H / A).
- **Pitch movement is calmer.** F0 spread falls by 0.6–1.4 st on every set.
- **Word errors fall** on the house and Atlas lines (A 2.7 % → 0 %, W 5.8 % → 1.4 %, H 4.7 % → 3.8 %). That comes from "Timer set" and "ensuite".
- **Accent holds** (33/38 → 34/38 British across L, H and A).
- **The voice moves slightly toward the liked Chatterbox-Fable clips** (`sim_cbfable` 0.71 → 0.75 on L, 0.66 → 0.74 on H).
- **Same voice, different delivery.**
  - ECAPA similarity to the scout's clip *of the same line* falls (0.99 → 0.91 on L), while similarity to the scout's voice *centroid* doesn't move.
  - What changed is the delivery: pauses, piece-by-piece prosody, the flatter short-reply prosody. Timbre didn't change; the decoder half of the pack is untouched.
  - L01 changes most (ECAPA 0.70 to its own scout clip), because its whole prosody now comes from the short pack.

## 3. Short lines (sing-song)

Nineteen short replies (L01, L10, H06, A01, A09, A13 and S02–S14). The measures:
- **F0 range**: p90 − p10 of the frame pitch, in semitones.
- **Ending**: the median pitch of the last third minus that of the rest. Negative means a fall.
- **Frame jump**: mean pitch change between 10 ms frames.

S01 "Lights off." is left out because pYIN found no voiced frames in the before clip.

Experiments, ONNX, whole line (`tools/lab/exp.py`; `short_pred` replaces the prosody half of the pack for replies of at most 40 phonemes; `floor` is the minimum style row):

| variant | n | median F0 (Hz) | F0 spread (st) | F0 range p10–p90 (st) | ending (st) | frame jump (st) | UTMOS | Eng−US | British | WER | dur (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 19 | 116.3 | 5.70 | 15.89 | -9.40 | 0.262 | 4.349 | +0.128 | 15/19 | 0.021 | 2.48 |
| c352 | 19 | 120.3 | 4.79 | 13.99 | -7.36 | 0.237 | 4.428 | +0.117 | 15/19 | 0.026 | 2.40 |
| c442 | 19 | 122.2 | 5.31 | 14.46 | -9.44 | 0.245 | 4.416 | +0.083 | 13/19 | 0.026 | 2.45 |
| c451 | 19 | 118.2 | 4.85 | 13.39 | -7.79 | 0.250 | 4.411 | +0.098 | 14/19 | 0.000 | 2.42 |
| lewis | 19 | 113.0 | 4.75 | 13.04 | -6.71 | 0.255 | 4.402 | +0.147 | 14/19 | 0.021 | 2.47 |
| pflat | 19 | 112.9 | 4.97 | 13.70 | -7.55 | 0.238 | 4.390 | +0.121 | 15/19 | 0.021 | 2.42 |
| pflatf40 | 19 | 114.8 | 3.99 | 10.61 | -5.89 | 0.247 | 4.393 | +0.145 | 16/19 | 0.000 | 2.51 |
| pgeorge30 | 19 | 132.9 | 4.87 | 13.55 | -7.04 | 0.260 | 4.398 | +0.173 | 18/19 | 0.021 | 2.48 |
| pinno | 19 | 111.0 | 3.82 | 10.53 | -6.17 | 0.248 | 4.405 | +0.096 | 12/19 | 0.026 | 2.37 |

Variant key:
- `pflat`: prosody 50 % bm_fable + 50 % the fitted mature pack.
- `pinno`: 30 / 70.
- `pgeorge30`: 50 % bm_fable + 20 % fitted + 30 % bm_george (the scout's suggestion).
- `c352` / `c442` / `c451`: three-way mixes of fable / fitted / george.
- `lewis`: 20 % bm_lewis.
- `pflatf40`: `pflat` plus a style floor of 40.

Round 1 (12 lines, in `scores/short.jsonl`) also tried:
- speed 0.90 and 1.00 for short lines: spread 5.35 / 5.63 against base 5.82, so little effect;
- style floors of 40, 80 and 120 on the plain pack: 5.20 / 4.76 / 4.68, but UTMOS fell to 4.36 / 4.32 / 4.31;
- sentence-by-sentence rendering without merging: spread 5.45, UTMOS 4.31.

**What helped:** a flatter prosody half from the fitted mature pack, together with a style floor. bm_george's prosody made it more British (18/19) but raised the median pitch by 17 Hz, which is younger and brighter, against the brief. So it was not used.

**As shipped** (`kokoro_backend.py` through the real `synth`, with joins and the one-word rule):

| variant | n | median F0 (Hz) | F0 spread (st) | F0 range p10–p90 (st) | ending (st) | frame jump (st) | UTMOS | Eng−US | British | WER | dur (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| after | 19 | 114.4 | 4.00 | 10.80 | -6.01 | 0.248 | 4.394 | +0.150 | 15/19 | 0.008 | 2.14 |
| before | 19 | 116.3 | 5.70 | 15.89 | -9.40 | 0.262 | 4.354 | +0.128 | 15/19 | 0.021 | 2.47 |

## 4. "Timer set:" and the house words

"Timer set:" lines T01–T08 (`tools/lab/timer.tsv`). The count is lines Whisper began "Time a …":

| variant | heard "Time a" | WER | UTMOS |
|---|---|---|---|
| as written | 4 / 8 | 5.3 % | 4.440 |
| phoneme override `[Timer](/tˈImə/)` (misaki's own phonemes) | 4 / 8 | 5.3 % | 4.440 |
| "Timer set —" | 3 / 8 | 2.7 % | 4.443 |
| "Timer set." | 0 / 8 | 1.8 % | 4.344 |
| "Right, timer set:" | 0 / 8 (heard "Write timer set") | 8.5 % | 4.438 |
| "Timer's set:" | 0 / 8 (written "Timers set") | 11.6 %, spelling only | 4.432 |
| "I've set a timer:" | 0 / 8 | 0 % | 4.429 |
| **lexicon `timer` → `tˈImˌə` (shipped)** | **0 / 8, wording unchanged** | — | — |

Whisper's transcripts for the shipped lexicon are in `scores/timer_lexicon_asr.txt`: all 8 "Timer set" lines, plus "Timer cancelled." (before: "Time are cancelled.").

House words: `samples/fablemix-W*.mp3`, and the transcripts in `scores/release.jsonl` (W lines). The full list with phonemes is in `../PRONUNCIATION.md`.

## 5. Every line: shipped configuration against the scout's Fable-mix

Where the scout scored the line (L, H), cells read scout → shipped.

| line | UTMOS scout → after | WER | median F0 (Hz) | F0 spread (st) | Eng−US | ECAPA sim to scout's clip | Resemblyzer sim | ECAPA / Resemblyzer sim to scout centroid | sim → liked Fable | Whisper heard |
|---|---|---|---|---|---|---|---|---|---|---|
| A01 | 4.45 | 0.00 | 114 | 3.5 | +0.21 | — | — | 0.853 / 0.936 | 0.67 | Done study lights on, checked. |
| A02 | 4.48 | 0.00 | 116 | 3.5 | -0.37 | — | — | 0.809 / 0.914 | 0.63 | Done kitchen downlight left off, checked. |
| A03 | 4.40 | 0.00 | 97 | 5.2 | +0.24 | — | — | 0.829 / 0.928 | 0.72 | I've turned the hallway lights off for you. |
| A04 | 4.47 | 0.00 | 100 | 6.0 | +0.17 | — | — | 0.897 / 0.929 | 0.78 | I have turned the dining room pendant on at 70%. |
| A05 | 4.42 | 0.00 | 112 | 4.8 | +0.46 | — | — | 0.857 / 0.935 | 0.76 | I've brightened the guest bedroom lamp to 80%. |
| A06 | 4.47 | 0.00 | 102 | 5.4 | +0.42 | — | — | 0.896 / 0.943 | 0.74 | Timer set, porch lights off at 10.15pm. Say cancel that to stop it. |
| A07 | 4.48 | 0.00 | 118 | 4.2 | +0.40 | — | — | 0.915 / 0.938 | 0.73 | Timer set, kitchen lights on in 25 minutes. Say cancel that to stop it. |
| A08 | 4.44 | 0.00 | 102 | 4.2 | +0.36 | — | — | 0.835 / 0.925 | 0.79 | Close the atrium blind at 8.20pm. |
| A09 | 4.46 | 0.00 | 110 | 3.8 | +0.31 | — | — | 0.869 / 0.951 | 0.71 | Cancelled the study lights timer. |
| A10 | 4.46 | 0.00 | 99 | 5.6 | +0.21 | — | — | 0.846 / 0.950 | 0.83 | You have one timer, the porch lights go off at 11.30pm. |
| A11 | 4.48 | 0.00 | 109 | 4.1 | +0.27 | — | — | 0.878 / 0.931 | 0.75 | Garage lights are already on. I didn't change anything. |
| A12 | 4.41 | 0.00 | 111 | 3.9 | +0.14 | — | — | 0.840 / 0.935 | 0.69 | I can't control the aircon yet. It's currently set to off. |
| A13 | 4.45 | 0.00 | 113 | 4.5 | -0.27 | — | — | 0.827 / 0.921 | 0.66 | I can't control the speakers yet. |
| A14 | 4.42 | 0.00 | 104 | 5.6 | +0.38 | — | — | 0.771 / 0.936 | 0.74 | What time would you like the porch lights turned off? |
| A15 | 4.47 | 0.00 | 114 | 5.0 | +0.19 | — | — | 0.902 / 0.929 | 0.72 | How bright would you like the dining room lights as a percentage? |
| A16 | 4.49 | 0.00 | 126 | 6.7 | +0.02 | — | — | 0.858 / 0.922 | 0.76 | The home battery is at 63.4%. |
| A17 | 4.48 | 0.00 | 98 | 7.8 | +0.33 | — | — | 0.827 / 0.918 | 0.74 | You've made 14.6 kilowatt hours of solar today. |
| A18 | 4.51 | 0.00 | 107 | 5.0 | +0.21 | — | — | 0.884 / 0.926 | 0.76 | It's 23 degrees outside, heading for a low of 14 degrees overnight. |
| A19 | 4.50 | 0.00 | 111 | 4.9 | +0.03 | — | — | 0.832 / 0.916 | 0.63 | It's 19.5 degrees in the study. |
| A20 | 4.41 | 0.00 | 103 | 5.2 | +0.05 | — | — | 0.853 / 0.922 | 0.68 | porch lights on, visitors will at least see where they're going. |
| F01 | 4.41 | 0.00 | 98 | 5.8 | +0.46 | — | — | 0.739 / 0.862 | 0.59 | Timer cancelled. |
| F02 | 4.47 | 0.00 | 100 | 5.4 | +0.29 | — | — | 0.825 / 0.945 | 0.77 | Open the living room blinds at 6.45am tomorrow. |
| F03 | 4.33 | 0.00 | 109 | 4.2 | +0.18 | — | — | 0.707 / 0.840 | 0.56 | Porch Lights on. |
| F04 | 4.36 | 0.00 | 135 | 3.8 | +0.42 | — | — | 0.688 / 0.773 | 0.53 | Good night. |
| F05 | 3.08 | 0.00 | 96 | 0.5 | -0.34 | — | — | 0.648 / 0.779 | 0.57 | Done. |
| F06 | 4.36 | 0.00 | 116 | 3.7 | +0.15 | — | — | 0.747 / 0.876 | 0.64 | Blinds open. |
| F07 | 3.99 | 0.00 | 125 | 7.3 | +0.10 | — | — | 0.620 / 0.701 | 0.43 | All set. |
| H01 | 4.44 → 4.46 | 0.00 → 0.00 | 102 → 107 | 6.2 → 3.6 | -0.10 → -0.03 | 0.797 | 0.959 | 0.842 / 0.939 | 0.58 → 0.69 | Done fountain spotlight on, checked. |
| H02 | 4.42 → 4.45 | 0.12 → 0.12 | 116 → 112 | 6.2 → 6.1 | +0.29 → +0.31 | 0.861 | 0.947 | 0.873 / 0.935 | 0.69 → 0.76 | I've dimmed the mirror ambience to 30%. |
| H03 | 4.50 → 4.47 | 0.07 → 0.00 | 108 → 118 | 5.4 → 4.0 | +0.41 → +0.41 | 0.951 | 0.966 | 0.913 / 0.947 | 0.69 → 0.72 | Timer set, robe downlight off in 10 minutes. Say cancel that to stop it. |
| H04 | 4.48 → 4.48 | 0.18 → 0.18 | 104 → 106 | 5.7 → 3.8 | +0.43 → +0.35 | 0.900 | 0.942 | 0.909 / 0.941 | 0.73 → 0.81 | The on-suite downlight is already off. I didn't change anything. |
| H05 | 4.46 → 4.45 | 0.00 → 0.00 | 108 → 111 | 5.1 → 4.8 | +0.08 → +0.04 | 0.888 | 0.954 | 0.830 / 0.948 | 0.62 → 0.67 | wall floodlight on. The back of the house looks rather theatrical. |
| H06 | 4.46 → 4.47 | 0.00 → 0.00 | 114 → 114 | 5.9 → 3.3 | +0.26 → +0.41 | 0.794 | 0.951 | 0.842 / 0.902 | 0.50 → 0.68 | Done, wall light off. Checked. |
| H07 | 4.45 → 4.49 | 0.00 → 0.00 | 112 → 104 | 5.2 → 5.2 | +0.25 → +0.23 | 0.947 | 0.946 | 0.884 / 0.954 | 0.77 → 0.81 | Pergola Floodlight 3 is already on at full brightness. I didn't change anything. |
| H08 | 4.48 → 4.48 | 0.00 → 0.00 | 118 → 118 | 5.6 → 5.5 | +0.30 → +0.33 | 0.881 | 0.954 | 0.866 / 0.940 | 0.70 → 0.80 | I've turned living room chandelier 6 on at 50%. |
| L01 | 4.41 → 4.44 | 0.00 → 0.00 | 110 → 122 | 6.6 → 3.2 | -0.07 → -0.22 | 0.703 | 0.949 | 0.798 / 0.913 | 0.47 → 0.62 | Done. Kitchen lights off. |
| L02 | 4.46 → 4.46 | 0.00 → 0.00 | 106 → 106 | 6.1 → 6.0 | +0.10 → +0.06 | 0.913 | 0.969 | 0.850 / 0.944 | 0.66 → 0.74 | Would you like the blinds down as well, or shall I leave them? |
| L03 | 4.52 → 4.51 | 0.00 → 0.00 | 110 → 111 | 4.8 → 4.0 | +0.37 → +0.35 | 0.984 | 0.961 | 0.898 / 0.949 | 0.80 → 0.82 | It's 23 degrees outside, the battery's at 68%, and the dishwasher finishes at quarter past nine. |
| L04 | 4.49 → 4.47 | 0.00 → 0.00 | 103 → 99 | 5.7 → 5.0 | +0.23 → +0.16 | 0.950 | 0.953 | 0.842 / 0.941 | 0.77 → 0.75 | the garage door, I'm told, is beyond my reach. Which is probably for the best. |
| L05 | 4.48 → 4.48 | 0.00 → 0.00 | 113 → 118 | 5.1 → 3.9 | +0.27 → +0.28 | 0.947 | 0.962 | 0.887 / 0.949 | 0.78 → 0.81 | Good night. Everything's switched off, the doors are your department, and tomorrow looks sunny. |
| L06 | 4.50 → 4.47 | 0.00 → 0.00 | 106 → 109 | 5.2 → 4.8 | +0.30 → +0.26 | 0.968 | 0.951 | 0.888 / 0.950 | 0.83 → 0.81 | Solar did rather well today. You made just over 30 kilowatt hours, used about half of it, and sent the rest to the grid while the battery filled up by early afternoon. |
| L07 | 4.49 → 4.48 | 0.00 → 0.00 | 108 → 108 | 5.3 → 5.2 | +0.33 → +0.33 | 0.979 | 0.951 | 0.904 / 0.951 | 0.73 → 0.74 | Careful, there's a storm warning from six this evening, with gusts up to 90 kilometers an hour. |
| L08 | 4.45 → 4.47 | 0.00 → 0.00 | 108 → 101 | 4.8 → 4.6 | -0.02 → +0.45 | 0.924 | 0.930 | 0.908 / 0.936 | 0.67 → 0.76 | I'm sorry. I can't do that one yet. Shall I ask Claude instead? |
| L09 | 4.48 → 4.47 | 0.00 → 0.00 | 112 → 116 | 5.0 → 3.7 | +0.31 → +0.43 | 0.963 | 0.967 | 0.892 / 0.970 | 0.80 → 0.79 | Rather a gray afternoon, I'm afraid. The forecast can't make up its mind, so I'd take a jacket. |
| L10 | 4.46 → 4.46 | 0.00 → 0.14 | 106 → 102 | 7.0 → 5.3 | +0.45 → +0.35 | 0.787 | 0.909 | 0.842 / 0.928 | 0.57 → 0.65 | Good mornings. Coffee weather, I'd say. |
| W01 | 4.49 | 0.00 | 118 | 3.5 | +0.36 | — | — | 0.848 / 0.929 | 0.72 | Done good night is on, checked. |
| W02 | 4.45 | 0.00 | 102 | 4.2 | -0.34 | — | — | 0.719 / 0.891 | 0.60 | Shall I run wind down now? |
| W03 | 4.48 | 0.00 | 106 | 3.6 | +0.34 | — | — | 0.859 / 0.922 | 0.82 | The ensuite light is already off. |
| W04 | 4.39 | 0.00 | 114 | 4.3 | +0.34 | — | — | 0.846 / 0.937 | 0.71 | Pergola lights on rather pleasant out there |
| W05 | 4.42 | 0.00 | 115 | 3.8 | +0.09 | — | — | 0.832 / 0.872 | 0.71 | Atrium blind closed. |
| W06 | 4.47 | 0.00 | 124 | 3.4 | +0.31 | — | — | 0.817 / 0.929 | 0.69 | You've used 12 kilowatt hours today. |
| W07 | 4.23 | 0.17 | 107 | 5.5 | +0.27 | — | — | 0.845 / 0.940 | 0.78 | Zero charge is on, so the car won't charge from the grid. |
| W08 | 4.49 | 0.00 | 106 | 4.3 | +0.23 | — | — | 0.887 / 0.942 | 0.74 | Wind down starts at 9.30pm. |
| W09 | 4.44 | 0.00 | 110 | 4.5 | +0.35 | — | — | 0.861 / 0.942 | 0.74 | Good night ran at 11 p.m. Everything's off. |
| W10 | 4.43 | 0.00 | 108 | 4.2 | +0.34 | — | — | 0.845 / 0.907 | 0.74 | The ensuite fan is on. |
| W11 | 4.46 | 0.00 | 102 | 3.7 | +0.43 | — | — | 0.870 / 0.906 | 0.73 | I've turned on the good night scene. |
| W12 | 4.47 | 0.00 | 108 | 4.0 | +0.30 | — | — | 0.897 / 0.947 | 0.74 | starting wind down. The lamps will fade over 10 minutes. |

## Files

- **`scores/*.jsonl`**: every scored clip.
  - `parity` is §1.
  - `release` and `release_cent` are §2 and §5. `release_render_log.jsonl` has each clip's text, phoneme chunks and timings.
  - `short`, `short2` and `relshort` are §3.
  - `timer` is §4.
  - `ab`: the style row from the whole reply against from each piece. There was no gain, so per piece is shipped.
  - `pause`: merging pieces against not merging. One-word pieces mangle when unmerged.
  - `house`: an earlier backend on the house lines.
  - `scout_fablemix.jsonl`: the scout's own scores, copied from `voice-scout/scores/`.
- **`scores/*.txt`**: Whisper-only probes for the timer lexicon, one-word replies and join punctuation (with measured pauses).
- **`raw/bench_*.jsonl`**: the speed and memory runs (README §Speed).
- **`bench.py`**: the benchmark. Run it on the desktop.
- **`make_report.py`**: the per-line tables.
