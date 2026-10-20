# Ready-made open voices: audition (no training)

Target: a **mature, slightly deeper British male with Fable's accent**, natural and warm, not youthful. Everything here is a built-in voice, a voice pack or a weighted blend of voice packs. No reference cloning was used.

Each voice says the 4 sample lines (`-S1`…`-S4`) and the 10 audition lines (`-L01`…`-L10`, text in `../corpus/audition/audition_lines.txt`). `-joined-L01-L10.mp3` has all ten lines with 0.5 s gaps. The MP3s are mono, 96 kbps and loudness-matched to −18 LUFS.

**I could not listen to any of this; the numbers are proxies. Pick by ear.**

## Top 3 for the target

All three are **Kokoro-82M blends** (Apache-2.0), CPU-fast and ready for Home Assistant today.

1. **`kokoro-bm_fable0.7_bm_lewis0.3-s0.95`** (Fable 70% + Lewis 30%, speed 0.95). It is the only blend that is *deeper* than plain Fable (104 vs 108 Hz median), and it keeps the most Fable (similarity 0.65) with Fable's lively pitch movement (6.2 st). It is natural (UTMOS 4.38, above the Chatterbox teacher's 4.34) with zero word errors. A slower take, `-s0.9`, is also included.
2. **`kokoro-bm_fable0.5_bm_lewis0.5-s0.95`** (50/50). It is equally deep (105 Hz), has the most English accent score of every voice here (0.55), and is natural (4.39). It is noticeably flatter (5.2 st), so it is calmer and less animated, and less like Fable (0.45).
3. **`kokoro-bm_fable0.6_bm_lewis0.2_bm_george0.2-s0.95`** (Fable 60 + Lewis 20 + George 20). It has the highest naturalness (4.44, tied best), but it is *not* deeper (114.5 Hz). Pick it if "mature" turns out to mean George's older timbre rather than lower pitch.

### How the top 3 handled each audition line

Measured on the rendered audio: duration, median pitch, pitch at the end of the line, and pitch range. These are proxies for what each line tests; listen to confirm.

| Line (what it tests) | 1. Fable 70 / Lewis 30 | 2. Fable 50 / Lewis 50 | 3. Fable 60 / Lewis 20 / George 20 |
|---|---|---|---|
| L01 short confirmation | 2.0 s, unhurried, settles low (101 Hz) | quickest (1.6 s), higher (139 Hz) | 2.0 s, mid (115 Hz) |
| L02 question | falls at the end, as an "or…?" alternative question naturally does; full pitch range | nearly level ending, which sounds more like a neutral prompt; narrow range | falls like #1, from a higher pitch |
| L03 numbers and times | every number right; even pace (2.5 words/s) | every number right; ends level | every number right |
| L04 dry wit | 4.9 s; drops into the second sentence, which suits the aside | similar timing; slightly flatter | flatter range (15 st), so the joke is less pointed |
| L05 warmth | widest range of the three; settles at the end | narrow (14 st): calm, but less warm | narrow (14 st) |
| L06 long sentence | 9.8 s at 3.3 words/s, no errors; keeps rising through the clauses | same pace, flatter | same pace, highest pitch |
| L07 firm warning | ends held up (−1.7 st), so the warning stays open | settles (−6.6 st) | settles (−6.3 st) |
| L08 apology and limit | settles gently at the end | level ending: brisker, less apologetic | settles strongly |
| L09 British vowels | English-accent score is good for all three; #2 is the most English overall | | |
| L10 maturity | **lowest pitch of all (88 Hz)**: the most grown-up "Good morning" | highest (145 Hz): the youngest-sounding of the three on this line | 129 Hz |

## All voices

Scores cover all 14 lines:
- **F0** median and spread (semitones; more spread means more animated).
- **UTMOS** (naturalness, 1–5).
- **WER** (Whisper small.en).
- **sim → Fable:** ECAPA similarity to the bm_fable reference. Plain Kokoro Fable scores 0.84; below 0.3 is a different voice.
- **England − US:** CommonAccent ECAPA score; higher means more English.
- **RTF:** CPU real-time factor on this sandbox (4 vCPU Xeon @ 2.1 GHz). Kokoro was re-timed with the CPU idle; the other figures were taken while the CPU was shared, so the real values are lower.

| Voice | Licence | F0 | F0 spread | UTMOS | WER | sim → Fable | England − US | RTF (here) |
|---|---|---|---|---|---|---|---|---|
| **kokoro bm_fable 0.7 + bm_lewis 0.3, speed 0.95** | Apache-2.0 | **104 Hz** | 6.2 | 4.38 | 0% | 0.65 | 0.39 | **0.39** (p95 0.41) |
| kokoro bm_fable 0.7 + bm_lewis 0.3, speed 0.9 | Apache-2.0 | 105 Hz | 6.2 | 4.38 | 0% | 0.64 | 0.39 | 0.41 |
| **kokoro bm_fable 0.5 + bm_lewis 0.5** | Apache-2.0 | 105 Hz | 5.2 | 4.39 | 0.5% | 0.45 | **0.55** | 0.41 |
| **kokoro bm_fable 0.6 + bm_lewis 0.2 + bm_george 0.2** | Apache-2.0 | 115 Hz | 5.5 | **4.44** | 0.5% | 0.55 | 0.44 | 0.41 |
| kokoro bm_fable 0.5 + bm_george 0.5 | Apache-2.0 | 127 Hz | 5.3 | 4.44 | 0% | 0.40 | 0.45 | ~0.4 |
| kokoro bm_fable 0.7 + bm_george 0.3 | Apache-2.0 | 121 Hz | 6.0 | 4.43 | 0% | 0.66 | 0.33 | ~0.4 |
| kokoro bm_fable 0.7 + bm_daniel 0.3 | Apache-2.0 | 119 Hz | 5.3 | 4.42 | 0% | 0.63 | 0.35 | ~0.4 |
| kokoro bm_fable (plain, speed 0.95) | Apache-2.0 | 108 Hz | 6.9 | 4.32 | 0% | 0.84 | 0.26 | 0.41 |
| kokoro bm_george | Apache-2.0 | 142 Hz | 3.9 | 4.30 | 0.4% | 0.03 | 0.35 | ~0.4 |
| kokoro bm_daniel | Apache-2.0 | 124 Hz | 3.0 | 4.25 | 0.5% | 0.07 | 0.41 | ~0.4 |
| piper vctk p232 | data CC BY 4.0 † | 110 Hz | 3.3 | 4.23 | 2.4% | 0.13 | 0.25 | 0.14 |
| piper vctk p274 | data CC BY 4.0 † | 95 Hz | 2.4 | 4.19 | 6.6% | 0.08 | 0.42 | 0.14 |
| piper vctk p254 | data CC BY 4.0 † | 79 Hz | 2.1 | 4.16 | 6.4% | 0.01 | 0.23 | 0.13 |
| piper vctk p243 | data CC BY 4.0 † | 117 Hz | 2.0 | 4.15 | 7.1% | 0.07 | 0.38 | 0.13 |
| XTTS-v2 "Wulf Carlevaro" (built-in) | CPML, **non-commercial** | 117 Hz | 4.5 | 4.14 | 3.3% | 0.12 | 0.22 | 2.8 ✗ |
| piper vctk p226 | data CC BY 4.0 † | 108 Hz | 2.9 | 4.12 | 9.3% | 0.07 | 0.25 | 0.13 |
| pocket-tts "paul" (VCTK p259) | model CC BY 4.0, voice CC BY 4.0 | 110 Hz | 1.9 | 4.11 | 1.5% | 0.21 | 0.48 | 0.63 (1 thread) |
| piper northern_english_male | data CC BY-SA 4.0 † | 110 Hz | 2.5 | 4.04 | 6.2% | 0.24 | 0.50 | 0.13 |
| pocket-tts "charles" (VCTK p254) | CC BY 4.0 | 71 Hz | 1.8 | 4.02 | 3.3% | 0.12 | 0.27 | 0.63 |
| piper alan | Mimic 3 voice; licence unclear | 96 Hz | 1.7 | 4.01 | 2.8% | 0.04 | 0.46 | 0.12 |
| piper vctk p258 | data CC BY 4.0 † | 116 Hz | 2.3 | 3.83 | 12.8% | 0.05 | 0.30 | 0.14 |
| XTTS-v2 "Marcos Rudaski" (built-in) | CPML, non-commercial | 127 Hz | 3.2 | 3.83 | 5.3% | 0.18 | 0.23 | 3.0 ✗ |
| pocket-tts "javert" (voice donation) | CC0 | 80 Hz | 1.3 | 3.29 | 0.9% | 0.18 | −0.42 | 0.62 |
| pocket-tts "marius" (voice donation) | CC0 | 240 Hz | 2.1 | 2.82 | 5.4% | 0.03 | −0.40 | 0.64 |

† These Piper checkpoints were fine-tuned from Piper's `lessac` voice, whose Blizzard data has its own licence (see the round-1 README).

The `piper-en_GB-vctk-medium-pNNN` files are VCTK speakers in Piper's `en_GB-vctk-medium` voice. I chose p226, p232, p243, p254, p258 and p274 because they are VCTK's southern/RP-ish English male speakers.

## Notes

- **Kokoro blends are the clear winners for naturalness:** UTMOS 4.38–4.44, against 4.0–4.2 for the Piper and Pocket voices, and with much livelier pitch (5–7 st vs 2–3 st). The Piper and Pocket voices are faster but sound flatter, and none of them sounds like Fable (similarity ≤ 0.24).
- **Blending in Lewis is what lowers the pitch.** George and Daniel blends make the voice *higher* (119–127 Hz).
- **Speed and memory:** Kokoro ran at RTF 0.39–0.41 (p95 ≤ 0.47) on this 4-vCPU sandbox, so an 8-core Ryzen will be well inside the 0.7 target. In PyTorch it peaks at about 1.8 GB RAM. The ONNX build (`kokoro-onnx`, about 300 MB model) is the lighter option to bring it near the 1 GB target (not measured here).
- **Home Assistant:** use [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (CPU Docker image, OpenAI-compatible) with the [wyoming_openai](https://github.com/roryeckel/wyoming_openai) bridge. Kokoro-FastAPI accepts weighted blends such as `bm_fable(0.7)+bm_lewis(0.3)` directly, so no files need making.
- **Not rendered:**
  - **MeloTTS EN-BR**, which as far as I know is a female voice. I didn't install it to check.
  - **XTTS** was kept only as a reference: it is non-commercial and 3× slower than real time here.
  - **Parler-TTS** was ruled out in `voice-samples`: American-leaning and slow.

Reproduce with `scripts/ready_audition.py` (renders), `scripts/audition_score.py` (scores) and `scripts/make_mp3s.py`.
