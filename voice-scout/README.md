# voice-scout: an open voice to adopt and evolve for Atlas

**The target:** a mature British male: slightly deep, warm and natural, with a dry wit; never robotic, never youthful. The starting point is the voice the household already likes: Kokoro `bm_fable` rendered expressively by Chatterbox (`voice-samples/chatterbox-kokoro-fable-ref-*`). The goal is that voice, slightly deeper and more mature, and less gravelly than `bm_lewis`.

**Ground rules kept:**
- No real person was cloned or imitated. Every Fable-family voice here descends from the household's liked clip, which is itself synthetic (Chatterbox conditioned on a 10 s Kokoro `bm_fable` clip; see `voice-samples/refs/`).
- The one exception is the Pocket TTS built-in `peter_yearsley`. It is a real but consenting LibriVox volunteer reader, released CC0 in Kyutai's Voice-Zero set. It is flagged wherever it appears, so the owner can choose.
- I could not listen to anything. Every judgement below rests on objective proxies (see [How it was measured](#how-it-was-measured)). Wit and warmth need your ears.

## Verdict: top 3

| # | Voice | Why | How it would run on the Windows desktop | Samples |
|---|---|---|---|---|
| **1** | **Qwen3-TTS "Fable-mature"**: Qwen3-TTS 0.6B Base cloning the liked Chatterbox-Fable clip after the clip (`chatterbox-kokoro-fable-ref-1`) was lowered 3 semitones in pitch and 5 % in formants (WORLD vocoder) | **The best fit to the brief.** It is the liked voice, evolved: median pitch 99 Hz against the original's ~115 Hz (about 2.7 semitones deeper), heard as British on **10/10 lines** (no line American; England-minus-US score 0.32, the unevolved Qwen clone 0.18), naturalness UTMOS 4.43, word error 2.5 %. Qwen re-renders the lowered clip cleanly: the raw lowered clip scores UTMOS 3.8, the Qwen render 4.43–4.48. A milder sibling, **"Fable-butler"** (−2 st, plus 40 % of a text-designed "English butler" voice's speaker vector), sits at 106 Hz, also 10/10 British, with exact wording. Listen to both. | **Not real time on CPU.** The int8 C engine (gabriele-mastrapasqua/qwen3-tts) measured RTF 3.5 here; estimated **RTF 1.3–2.0 on the 9700X**, so a 4-second reply would take ~5–8 s. Its `--serve` mode exposes an OpenAI-compatible `/v1/audio/speech`; run it under WSL2 → `wyoming_openai` → Home Assistant Wyoming. **Better: use it as the teacher and distil it into a Piper student** on the existing `voice-lewis-small` recipe (Wyoming Piper, RTF ~0.04). See [Next](#what-id-do-next-to-perfect-the-winner). | `qwen06-fablemature-*.mp3`, `qwen06-fablebutler-*.mp3`; unevolved baseline `qwen06-fable-*.mp3` |
| **2** | **Kokoro "Fable-mix"**: a new Kokoro-82M voice pack. Prosody half: 70 % bm_fable + 30 % fitted pack. Timbre half: 50 % bm_fable + 50 % a pack fitted by inno-kokoro to the Fable-mature target. Speed 0.95. | **The best one that runs live on CPU today.** Kokoro keeps Fable's phrasing while the timbre moves toward the mature target: 108 Hz, UTMOS 4.47 (the highest of the set, though UTMOS favours Kokoro's clean texture), word error 0 %. British on 8/10 lines; L01 and L08 lean American on the classifier. Resemblyzer similarity to the Fable-mature target is 0.93, against bm_fable's 0.87. Expect Kokoro's smoother, more even delivery rather than Chatterbox/Qwen's human phrasing. | **Live on CPU now: RTF 0.41 here, est. 0.11–0.19 on the 9700X.** Kokoro-FastAPI (`start-cpu.ps1` on Windows, or the `kokoro-fastapi-cpu` Docker image) with `voices/kokoro-fablemix.pt` copied into its voices folder → `wyoming_openai` (or the HACS OpenAI-TTS integration) → Home Assistant. | `kokoro-fablemix-*.mp3` |
| **3** | **Pocket TTS `peter_yearsley`** (built-in voice, Kyutai Pocket TTS 100M) ⚠ real CC0 LibriVox reader, not Fable | **The most mature-sounding and most consistently British** voice found: England on 10/10 lines with the strongest margin of any voice (England-minus-US 0.45), 94 Hz, lively pitch movement (4.0 st). Naturalness is lower (UTMOS 4.32), and it's a different man from Fable. No evolution lever without the gated cloning weights. | **Live on CPU: RTF 0.55 here on 2 threads, est. 0.25–0.34 on the 9700X.** Community Wyoming server `ikidd/pocket-tts-wyoming` (Docker), or `pocket-tts serve` → `wyoming_openai`. | `pocket-peter-*.mp3` |

All the leading candidates beat the live `lewis_small` Piper voice on naturalness (UTMOS 4.40–4.47 vs 4.02 on the same lines); compare with `samples/piper-lewis_small-*.mp3`.

**Recommendation:** run **#2 (Kokoro Fable-mix)** live now; it needs no new hardware. Meanwhile, **distil #1 (Qwen Fable-mature)** into a Piper student, the way `voice-lewis-small` was made. That gives the closest voice to the brief at Piper's speed. If you'd like a lighter path to #1 first, accepting Kyutai's free click-through on `kyutai/pocket-tts` would let Pocket TTS clone the Fable-mature clip live on CPU (untested here; see Next).

### Line by line: how the top 3 handled what each line tests

The proxies behind these notes are pitch (F0), pitch spread in semitones (st), pace, Whisper's transcript and the accent classifier. "Listen for" marks the places where I can't tell by measurement.

**1. Qwen3 Fable-mature** (`qwen06-fablemature`)

| Line | Tests | Note |
|---|---|---|
| L01 | Clipped confirmation | Clipped and confident (1.9 s), but **very low and flat** (69 Hz, 1.1 st): listen for creak. Fable-butler's L01 is livelier (82 Hz, 2.6 st). |
| L02 | Question, rising choice | Quick (2.7 s for 12 words). Whisper heard "**should** I leave them", so the model may have swapped "shall"; listen. Fable-butler kept "shall". |
| L03 | Numbers and times | All figures exact (23, 68 %, quarter past nine); unhurried (2.9 words/s); 97 Hz. |
| L04 | Dry wit, pause before the punchline | Measured, 94 Hz, the punchline sentence intact; England. Listen for the pause. |
| L05 | Warm night-time tone | 103 Hz, gentle 3.4 st; Whisper dropped the "'s" of "Everything's" (likely a soft consonant, minor). |
| L06 | Long sentence | Stays steady over 9 s (95 Hz, 3.6 st, UTMOS 4.47); no word errors. |
| L07 | Firm warning | Firm, not shouty (102 Hz, 3.9 st); "ninety kilometres an hour" exact. |
| L08 | Apology then offer | The most pitch movement of any line (6.0 st), good for humility then lift; exact. |
| L09 | British vowels | England (+0.39); 95 Hz. Whisper heard "so **I** take a jacket" (probably a light "I'd"). |
| L10 | Bright but mature morning | 101 Hz with lift (4.6 st); not young-sounding on pitch. |

**2. Kokoro Fable-mix** (`kokoro-fablemix`)

| Line | Tests | Note |
|---|---|---|
| L01 | Clipped confirmation | Natural (UTMOS 4.41) but **sing-song** (6.6 st) and the classifier hears it as American: Kokoro's short-line weakness. |
| L02 | Question, rising choice | Good rise (6.1 st), unhurried (4.1 s), exact "shall". |
| L03 | Numbers and times | Exact and paced (2.5 words/s); highest UTMOS of all the lines (4.52). |
| L04 | Dry wit | 103 Hz, 5.7 st; full stop before "Which…" kept. Listen for timing: Kokoro pauses are uniform. |
| L05 | Warm night-time tone | Exact; 113 Hz is a touch brighter than the target. |
| L06 | Long sentence | Steady over 10.5 s, exact; Kokoro's even cadence shows most here. |
| L07 | Firm warning | Exact "kilometres"; 108 Hz; moderate movement (5.3 st). |
| L08 | Apology then offer | Exact, but the classifier leans American (−0.02). |
| L09 | British vowels | England (+0.31); "can't", "afternoon", "rather" read with British G2P. |
| L10 | Bright but mature morning | Bright (7.0 st); 106 Hz keeps it from sounding young on pitch. |

**3. Pocket TTS peter_yearsley** (`pocket-peter`)

| Line | Tests | Note |
|---|---|---|
| L01 | Clipped confirmation | Firm and low (96 Hz, 2.1 st), not sing-song; lower naturalness (4.21). |
| L02 | Question, rising choice | Natural (4.42); moderate rise (3.7 st). |
| L03 | Numbers and times | Exact; the deepest read in the set (81 Hz); unhurried. |
| L04 | Dry wit | Expressive (5.2 st), England; a good candidate for wit by measurement. |
| L05 | Warm night-time tone | 100 Hz; lower naturalness (4.20); "Everything's" softened. |
| L06 | Long sentence | Steady (90 Hz, 3.3 st), exact. |
| L07 | Firm warning | Low and firm (88 Hz); exact. |
| L08 | Apology then offer | Pitch jumps to 134 Hz with 6.2 st: an animated apology. |
| L09 | British vowels | England (+0.34); natural (4.39); exact. |
| L10 | Bright but mature morning | Low (86 Hz), mature; lower naturalness (4.18). |

## All auditioned voices: the numbers

The 10 audition lines, each scored separately, then averaged. **British lines** counts lines the accent classifier ranked England or Australia above US. The two are neighbours in its space, and Chatterbox-Fable itself scores England/Australia. **sim → liked** is ECAPA speaker similarity to the liked Chatterbox-Fable clips; lower here means "less like the original", which a deeper voice is meant to be. CPU RTF is synthesis time ÷ audio length; below 1 is faster than real time.

| Voice | Stage | UTMOS | Median F0 | F0 spread | WER | British / US lines | sim → liked | RTF here (4 vCPU) | Est. RTF on 9700X |
|---|---|---|---|---|---|---|---|---|---|
| qwen06-fable (Qwen3 0.6B clone of the liked clip) | audition | 4.45 | 116 Hz | 4.0 st | 0.7 % | 10 / 0 | 0.80 | 8.1 (PyTorch) | 2.5–4.2 (PyTorch); 1.3–2.0 (C int8) |
| **qwen06-fablemature** (lowered reference) | evolved | 4.43 | **99 Hz** | 3.5 st | 2.5 % | **10 / 0** | 0.63 | same | same |
| qwen06-fablebutler (−2 st + 40 % designed x-vector) | evolved | 4.43 | 106 Hz | 3.4 st | 0.5 % | 10 / 0 | 0.73 | same | same |
| **kokoro-fablemix** (split-half Kokoro pack) | audition / evolved | **4.47** | 108 Hz | 5.5 st | 0 % | 8 / 2 | 0.71 | **0.41** | **0.11–0.19** |
| kitten2-fable (KittenTTS 2 clone) | audition | 4.44 | 119 Hz | 5.7 st | 1.3 % | 10 / 0 | 0.82 | 10.0 | 2.9–5.0 (PyTorch) |
| pocket-peter (Pocket TTS built-in) ⚠ | audition | 4.32 | 94 Hz | 4.0 st | 0.7 % | 10 / 0 | 0.08 | 0.55 (2 thr) | 0.25–0.34 |
| cbnano-fable (Chatterbox-Nano clone) | audition | 4.43 | 125 Hz | 6.2 st | 3.0 % | **4 / 6** | 0.72 | 1.6 | 0.54–0.87 |
| *reference: the liked Chatterbox-Fable clips (4, their own lines)* | — | 4.39 | 116 Hz | — | — | 4 / 0 | 0.94 | — | — |
| *baseline: the live Piper `lewis_small`, same 10 lines* | — | 4.02 | 98 Hz | 3.7 st | 1.3 % | 10 / 0 | 0.04 | 0.04 (its README) | ≤ 0.04 |

Notes:
- **Kitten** is as natural and as British as Qwen, but has the widest pitch swings on short lines (10.2 st on L01, 9.6 st on L10): the sing-song the brief rules out. On CPU it's also the slowest.
- **Chatterbox-Nano** is the fastest of the cloning models and natural, but it loses the accent: 6 of 10 lines classify as American. It is not a good host for this voice.
- **Desktop estimates:**
  - I measured each engine at 2 and 4 threads on the same line (L06, after a warm-up).
  - 4 → 8 cores is assumed to gain between the square root of, and all of, the measured 2 → 4 gain.
  - Each Zen 5 core at up to 5.5 GHz is assumed to be 1.6–2.2× one 2.8 GHz cloud-Xeon vCPU.
  - Pocket TTS is fastest on 2 threads, so its range is that time ÷ 1.6–2.2.
  - **These are estimates, not desktop measurements (NO DATA from the 9700X itself).**
- **Qwen C engine:** with `--int8 -j 4` it took 27.6 s of generation (talker 8.2 s + code predictor 10.7 s + decoder 8.7 s) for 7.8 s of audio. Each command-line call also spent ~60 s encoding the reference clip; a server caches that once as a `.qvoice` voice. Its renders kept the voice: UTMOS 4.44–4.46, England, 95–102 Hz on L03/L06/L09.

### Held-out house-name lines (top 2)

The 8 held-out lines (`voice-lewis-small/corpus/heldout_r3/house_heldout.txt`, the last 8: house names never seen in that student's training) rendered by the top 2. MP3s: `samples/<voice>-H01…H08.mp3`.

| Voice | UTMOS | Median F0 | F0 spread | WER | British / US lines |
|---|---|---|---|---|---|
| Qwen3 Fable-mature | 4.40 | 102 Hz | 3.4 st | 2.0 % | 7 / 1 |
| Kokoro Fable-mix | 4.46 | 110 Hz | 5.7 st | 4.7 % | 7 / 1 |

| Line | Qwen3 Fable-mature (Whisper heard) | Kokoro Fable-mix (Whisper heard) |
|---|---|---|
| H01 "Done: Fountain Spotlight on. Checked." | "Done, fountain spotlight on, checked." Pauses kept. | "Done fountain spotlight on checked": **runs the colon and full stop together**; classifier US. |
| H02 "…mirror ambiance to thirty percent." | Exact. | "ambience" (same word). |
| H03 "Timer set: Robe Downlight off in ten minutes…" | Exact; this line classifies as US. | "**Time a set** robe downlight…": Kokoro mangles "Timer set:". |
| H04 "The ensuite downlight is already off…" | Exact; England. | "The **N-suit** downlight": check the pronunciation of "ensuite". |
| H05 "Wall floodlight on…rather theatrical." | "**War** floodlight": listen for a weak final /l/. | Exact. |
| H06 "Done: Wall Light off. Checked." | Exact, pauses kept. | "Done wall light off checked": run together again. |
| H07 "Pergola Floodlight Three…" | "**Pagola**": listen for "Pergola". | Exact. |
| H08 "…living room chandelier six on at fifty percent." | Exact. | Exact. |

Kokoro's weak spot is Atlas's terse "Done: X. Checked." pattern; Qwen keeps those pauses. Both need an ear on the house names.

## How the voice was evolved (what worked, what didn't)

1. **Text-described voices alone don't give a British accent.** Five Qwen3 VoiceDesign descriptions ("mature RP gentleman", "BBC-presenter", "English butler"…) were natural and deep, but the accent classifier called every one American. Kokoro, Kitten and Pocket built-in "elderly diplomat"-style voices were American too.
2. **The accent comes from cloning a British synthetic clip** in in-context mode (reference audio + its transcript). The liked Chatterbox-Fable clip works in Qwen (10/10 British) and Kitten (10/10), but not in Chatterbox-Nano (4/10).
3. **Speaker-vector mixing (Qwen x-vector interpolation)** moves timbre without breaking the accent up to ~50 %. 50 % of a designed "mature RP" voice gave ~103–113 Hz and stayed British. At 70 % one line in three flipped to American.
4. **Lowering the reference itself works best.** The WORLD vocoder took the liked clip down 3 semitones in pitch and 5 % in formants (a larger vocal tract, so older and bigger). That clip sounds processed on its own (UTMOS 3.8), but Qwen's clone of it is clean (4.43–4.48), British, and ~2.7 st deeper. −2 st with formants −3 % gave ~100–106 Hz.
5. **Kokoro, evolved without cloning:**
   - inno-kokoro fitted a pack to the Fable-mature target. It came out as 66 % bm_lewis, 20 % am_michael and 13 % am_puck: deep (96–103 Hz) but flat (2–3 st).
   - Blending that pack into bm_fable's **timbre half only**, while keeping bm_fable's **prosody half**, gave the best Kokoro voice: deeper than Fable, Fable's movement kept.
   - **KVoiceWalk** (random-walk search of the style vector) was started toward the same target, with British G2P patched in. Its initial scoring already puts the Fable-mix pack closest to the target: Resemblyzer similarity 0.933 and score 91.2, against bm_fable 0.869 / 80.5, am_fenrir 0.760 / 82.1, bm_lewis 0.693 / 77.4 and bm_daniel 0.590 / 70.3. Each walk step costs ~20 s on this 4-vCPU sandbox, and the walk's gains need thousands of steps, so I stopped it rather than spend CPU on marginal gains. It's listed under Next, to run on the desktop.
6. **Pace:** Qwen's pace follows the reference (3.5 words/s). Kokoro at speed 0.95 reads 3.1 words/s.

## Everything scouted and tried

"Tried" means rendered and measured here. "Scouted" means researched only: either not runnable here, or ruled out on paper. Licences are my reading, not legal advice; private household use is fine for all of them unless marked otherwise.

### Tried here (sandbox: 4 vCPU Xeon @ 2.8 GHz, no GPU)

| Model / method | What I used | Licence | Result for the target | Link |
|---|---|---|---|---|
| **Qwen3-TTS 12Hz 0.6B Base** (Jan 2026) | In-context clone of the household's liked Chatterbox-on-Kokoro-bm_fable clip, with and without speaker-x-vector mixing and a WORLD-lowered reference | Apache-2.0 | **Best quality and accent stability.** Slow on CPU in PyTorch. | [HF](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) · [code](https://github.com/QwenLM/Qwen3-TTS) |
| Qwen3-TTS 12Hz 1.7B Base | Same clone, one line | Apache-2.0 | Similar to 0.6B (UTMOS 4.46), ~30 % slower | [HF](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) |
| **Qwen3-TTS 12Hz 1.7B VoiceDesign** | Five text descriptions of a mature RP gentleman | Apache-2.0 | Natural (UTMOS 4.27–4.42) and deep (84–117 Hz), but **all five scored American**. Useful only as a timbre source for x-vector mixing. | [HF](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) |
| qwen3-tts C engine (gabriele-mastrapasqua) | Same 0.6B Base weights, int8, ICL clone of the Fable-mature reference | MIT (engine) | Same voice (UTMOS 4.44–4.46, England); generation RTF 3.5 here, est. 1.3–2.0 on the 9700X; OpenAI-compatible `--serve` | [GitHub](https://github.com/gabriele-mastrapasqua/qwen3-tts) |
| **Kokoro-82M** + inno-kokoro + split-half blending | A pack fitted by inno-kokoro to the mature-Fable target, blended into bm_fable's timbre half while keeping bm_fable's prosody half | Apache-2.0 (inno-kokoro Apache-2.0; its speaker encoder CC BY-SA 3.0) | Real time on CPU, natural on UTMOS, British on 8 of 10 lines; flatter, Kokoro-smooth delivery | [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) · [inno-kokoro](https://pypi.org/project/inno-kokoro/) |
| KVoiceWalk | Random-walk search of the Kokoro style vector toward the mature-Fable target (British G2P patched in) | Apache-2.0 | Initial scoring confirmed Fable-mix as the closest start (0.93); the walk itself was stopped early (too slow here) | [GitHub](https://github.com/RobViren/kvoicewalk) |
| **KittenTTS 2** (1.7B, ternary) | Clone of the liked clip; built-in voices screened | Stellon Labs Community Licence (free under US$1 M revenue) | Natural (4.44), British, but sing-song on short lines; RTF ~10 here in PyTorch (a llama.cpp fork exists). All 19 built-in male voices, including "Reginald", score American. | [HF](https://huggingface.co/KittenML/kitten-tts-2) |
| **Chatterbox-Nano** (110M, Jul 2026) | Clone of the liked clip and of the Kokoro bm_fable clip | MIT (Perth watermark) | Fast (RTF 1.7 here) and natural, but **drifts American on 6 of 10 lines** | [HF](https://huggingface.co/ResembleAI/chatterbox-nano) |
| **Pocket TTS** (100M, Kyutai) | 10 built-in English male voices screened (the cloning weights are gated) | Model CC-BY-4.0; Voice-Zero voices CC0 (LibriVox readers); VCTK voices CC-BY-4.0 | `peter_yearsley`: England on 10/10 lines, 94 Hz, mature, UTMOS 4.32. `stuart_bell`: England, 130 Hz. `charles`/`paul` (young VCTK) English but flat. | [HF](https://huggingface.co/kyutai/pocket-tts-without-voice-cloning) · [voices](https://huggingface.co/kyutai/tts-voices) |
| Piper `lewis_small` (the live voice, `voice-lewis-small` round 1) | Rendered on the same 10 lines as a baseline | GPL-3.0 runtime; voice CC BY-SA (see that README) | UTMOS 4.02, 98 Hz, British 10/10: the bar to beat. `samples/piper-lewis_small-*.mp3` | `voice-lewis-small` |
| WORLD vocoder (pyworld) | −2 to −3 semitones of pitch and 3–5 % lower formants on the liked clip, used only as a *reference* for cloning | MIT | Alone it sounds processed (UTMOS 3.8); as a Qwen reference it gives a clean, deeper voice | [GitHub](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder) |

### Scouted, not run here

| Model | Licence | Why not run / what it would need | Link |
|---|---|---|---|
| NeuTTS Air / Nano (Neuphonic) | Air Apache-2.0; Nano NeuTTS Open Licence | **Gated** on Hugging Face (needs a token and accepting the terms). Promising: GGUF backbone, ~2–4× faster than real time on CPU, clones a reference. Needs a ~30-line FastAPI wrapper for Home Assistant. Worth a test with a token. | [GitHub](https://github.com/neuphonic/neutts) |
| NeuTTS 2E | "other" | Gated; four fixed speakers, no cloning | [HF](https://huggingface.co/neuphonic/neutts-2e) |
| Maya1 (3B) | Apache-2.0 | Voice design by description with emotion tags; ~16 GB VRAM; on CPU ~3–4× slower than real time even quantised. Reports of uneven British accents. A designer only, not a live voice. | [HF](https://huggingface.co/maya-research/maya1) |
| VoxCPM2 (2B) | Apache-2.0 | Voice design via a parenthesised description; slower than real time even on Apple GPU. Designer only. | [GitHub](https://github.com/OpenBMB/VoxCPM) |
| MOSS-VoiceGenerator + MOSS-TTS-Nano | Apache-2.0 | Design + 0.1B CPU clone; British quality unknown. A fully Apache alternative to Qwen-design → clone. | [GitHub](https://github.com/OpenMOSS/MOSS-TTS) |
| VibeVoice-Realtime-0.5B | MIT | Fixed preset voices (all American/Indian), no custom voices | [GitHub](https://github.com/microsoft/VibeVoice) |
| Supertonic 3 | OpenRAIL-M model, MIT code | Extremely fast; 5 male presets with undocumented (probably American) accents; style JSONs mixable | [GitHub](https://github.com/supertone-inc/supertonic) |
| Spark-TTS 0.5B | Weights CC-BY-NC-SA-4.0 | Reference-free voice creation (gender, pitch, speed) but no accent control | [GitHub](https://github.com/SparkAudio/Spark-TTS) |
| Kani-TTS 370m / Kani-TTS-2 | "other" / LFM 1.0 | Speaker `david` is described as British English; Kani-TTS-2 has interpolable speaker embeddings. Not run, for time. | [HF](https://huggingface.co/nineninesix/kani-tts-370m) |
| IndexTTS-2, Dia/Dia2, Higgs Audio v2/v3, CosyVoice 3, Fish S2 / OpenAudio S1-mini, Orpheus, Zonos, Breeze TTS 2, Voxtral TTS | Various (several non-commercial) | GPU-oriented; cloning only or American presets | — |
| OpenVoice v2 tone converter, Seed-VC, kNN-VC, RVC | MIT / GPL-3.0 / MIT / MIT | Voice-conversion post-filters. Not needed: re-rendering through a cloning model did the "deeper" job more cleanly than a DSP or VC post-filter would. | — |
| Already covered by other sessions | — | Kokoro single voices and plain blends, Chatterbox/Turbo, Parler, Piper, MeloTTS, XTTS-v2 | `voice-samples`, `voice-lewis-small` |

## What I'd do next to perfect the winner

1. **Distil Qwen Fable-mature into a Piper student** with the `voice-lewis-small` recipe, swapping only the teacher:
   - `teacher_generate.py`: replace the Chatterbox call with `tools/qwen_clone.py` using `voices/qwen-fablemature.json` (reference `voices/fable-mature-ref.wav` + its transcript).
   - Reuse the 1,412-sentence round-2 corpus text and the same filters (WER, speaker similarity to the new reference, UTMOS ≥ 3.5, artefact checks).
   - Warm-start from the round-2 Lewis student, or from `northern_english_male`.
   - Teacher cost: Qwen 0.6B runs at RTF ~8 in PyTorch on the 4-vCPU sandbox, close to Chatterbox's 6.4. About 97 min of audio is ~13 h of sandbox CPU, ~4–6 h with the C engine, or minutes on any GPU. Add 2–4 h of CPU training.
   - Expected result: Wyoming Piper at RTF ~0.04, with the Fable-mature timbre. Expect the same smoothing the Lewis student showed (UTMOS ~4.1 vs the teacher's ~4.4).
   - Two fixes first: pin a seed per clip, and have the filter reject wording swaps ("shall" → "should"), as the critical-word check already does for numbers.
2. **Try Pocket TTS cloning of the Fable-mature clip** after accepting Kyutai's free click-through on `kyutai/pocket-tts` (needs an HF token in the environment). It's 100M, CPU-fast (est. RTF 0.25–0.34) and has a Wyoming server, so if it keeps the accent it's a live #1 without distillation. Same for **NeuTTS Air** (gated, Apache-2.0, GGUF on CPU).
3. **Polish Kokoro Fable-mix:** run KVoiceWalk for the full 10k steps toward the Fable-mature target on the desktop (~26 h on CPU per its author, a few hours on any GPU). Fix L01/L08 by blending 10–20 % of bm_george's prosody half, the most British stock voice on short lines.
4. **Pick between Fable-mature and Fable-butler by ear,** then tune with one knob: the reference's semitone drop (−2 to −3) or the x-vector mix (30–50 %).

## Files

| Path | What |
|---|---|
| `samples/<voice>-L01.mp3` … `-L10.mp3`, `<voice>-all.mp3` | The 10 audition lines per voice (mono, 96 kbps, loudness-matched to −18 LUFS) and all 10 joined with 0.5 s gaps. Voices: `qwen06-fablemature`, `qwen06-fablebutler`, `kokoro-fablemix`, `pocket-peter`, `qwen06-fable`, `kitten2-fable`, `cbnano-fable`, plus the live `piper-lewis_small` as a baseline. |
| `samples/<voice>-H01.mp3` … `-H08.mp3` | The 8 held-out house-name lines (`voice-lewis-small/corpus/heldout_r3/`, last 8) for the top 2. |
| `voices/kokoro-fablemix.pt` | The Kokoro voice pack (#2), drop-in for Kokoro-FastAPI's voices folder or `KPipeline(lang_code="b")(text, voice=...)` at speed 0.95. |
| `voices/fable-mature-ref.wav`, `voices/fable-butler-ref.wav` | The WORLD-lowered reference clips (synthetic, from `voice-samples/refs` lineage) that Qwen clones for #1. |
| `voices/qwen-*.json` | Exact Qwen clone settings for #1 (the reference, its transcript, x-vector mix). `voices/designed-butler-L09.wav` is the VoiceDesign clip whose x-vector Fable-butler mixes in. |
| `scores/*.jsonl` | Every measured clip: UTMOS, F0, spread, WER + transcript, accent, similarity. `scores/timing.md` holds the raw timings. |
| `tools/` | Every script used (below). |

### Reproducing

One Python 3.11 venv per engine, CPU PyTorch wheels:
- `qwen-tts` 0.x (torch 2.14 CPU);
- `kokoro` 0.9.4 + `inno-kokoro` 0.2.0;
- `kittenml` 0.9.4;
- `pocket-tts` 3.3.0;
- `chatterbox-tts` from git `5de7a54` (for Nano);
- an eval venv: torch 2.6, speechbrain 1.0.3, faster-whisper, SpeechMOS `utmos22_strong`, pyworld.

The scripts:
- `qwen_design_multi.py`: VoiceDesign.
- `qwen_clone.py`: clone with x-vector mixing.
- `deepen.py`: WORLD pitch and formant lowering.
- `kokoro_run.py`: split-half packs.
- `kokoro_enroll.py`: inno-kokoro.
- `kitten_run.py`, `cbnano_run.py`, `pocket_run.py`.
- `eval.py`: scoring (reuses `voice-lewis-small/scripts/metrics.py`).
- `to_mp3.sh`.
- `qc_c.sh`: Qwen C engine.
- `queue*.sh`: the run order.

The Qwen C engine is `gabriele-mastrapasqua/qwen3-tts` @ `ef339be`, `make blas`. KVoiceWalk is `RobViren/kvoicewalk` with two local patches: British G2P (`lang_code="b"`) and a librosa `tempo` fix.

## How it was measured

Measured on the 10 audition lines, each WAV scored before MP3 conversion, in a cloud sandbox: 4 vCPU Intel Xeon @ 2.8 GHz, no GPU, 15 GB RAM.
- **UTMOS** (`utmos22_strong`): predicted naturalness, 1–5.
- **Median F0 and spread:** pYIN; spread is the standard deviation in semitones around the median.
- **WER:** faster-whisper `small.en` with Whisper's English normaliser and the `voice-lewis-small` number and time canonicalisation.
- **Accent:** SpeechBrain CommonAccent ECAPA; top class and England-minus-US score.
- **Similarity:** ECAPA-TDNN cosine to the centroid of the four liked Chatterbox-Fable clips.
- **RTF:** wall-clock synthesis ÷ audio length, after a warm-up, with nothing else running.

Sampling models (Qwen, Kitten, Pocket, Nano) were seeded with 1234 per line; one take per line, no cherry-picking.

**Budget:** about 3.5 h of a 4-vCPU sandbox, no GPU and no paid APIs. That is well under the US$40 guide, though I can't see the actual bill.

## Licences (my reading, not legal advice)

- **Qwen3-TTS** weights and code: Apache-2.0.
- **Kokoro-82M:** Apache-2.0. **inno-kokoro:** Apache-2.0; its speaker-encoder weights are CC BY-SA 3.0, used only to fit the pack.
- **Pocket TTS:** model CC-BY-4.0; `peter_yearsley` is CC0 (Voice-Zero, LibriVox).
- **KittenTTS 2:** Stellon Labs Community Licence (free for private use).
- **Chatterbox:** MIT; Chatterbox outputs carry the Perth watermark.
- **Tools:**
  - The qwen3-tts C engine is MIT.
  - KVoiceWalk is Apache-2.0.
  - pyworld is MIT.
  - Whisper, SpeechBrain and UTMOS are as in `voice-lewis-small`.
- All sample audio is synthetic output of the models above. No human recording entered any Fable-family voice.
