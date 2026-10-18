# Atlas voice samples

Candidate voices for Atlas, the household assistant. The target is a smooth, refined British male storyteller: warm, unhurried, gently melancholic, drily witty.

Every voice reads the same four lines (`tools/lines.txt`). Files are named `<model>-<voice>-<line#>.mp3`. They are mono, 96 kbps and loudness-matched to -18 LUFS, so no voice wins by being louder.

| # | Line |
|---|------|
| 1 | Good evening. The house is in order: battery at eighty percent, solar's done for the day… unless you're feeling reckless. |
| 2 | If you are hoping for good news, I'm afraid you have come to the wrong assistant… in perfectly good shape. |
| 3 | Done. Study lights off in ten minutes. |
| 4 | Shall I put something smooth on the Sonos and lower the blinds? Purely for energy efficiency, of course. |

**No real person was cloned or imitated.** No recording of any actor or public figure was used, and no prompt names one. Each voice comes from one of three places:

- a model's own built-in voice;
- a text description of the style (Parler-TTS);
- for the two `chatterbox-kokoro-*-ref` voices, a 10-second clip of a *synthetic* Kokoro voice used as Chatterbox's style reference. The exact clips, their sha256 and how they were made are in [`refs/`](refs/README.md). That gives Chatterbox's natural delivery with a British voice, without any human reference.

The XTTS speaker names are the labels of Coqui's built-in studio voices. They are not public figures.

## Top 3 picks for the target feel

I had no way to listen to these. The picks are based on objective measures: UTMOS naturalness score, a British-vs-American accent classifier, Whisper intelligibility, pitch and pace (see [How the scores were made](#how-the-scores-were-made)). Please confirm them by ear.

1. **Chatterbox, conditioned on Kokoro bm_lewis** (`chatterbox-kokoro-lewis-ref-*`). It had the strongest British-accent score of all 20 voices tried, near-top naturalness (UTMOS 4.37), a lower pitch (~116 Hz) and a measured pace (2.6 words/s). Chatterbox gives the most human-sounding phrasing in the set. The catch: on CPU it is ~5× slower than real time, so a 10-second reply takes ~50 s. On the home PC it needs a GPU, or pre-rendered phrases for fixed announcements (see below). One slip: Whisper heard line 3's "Done" as "Dumb".
2. **Chatterbox, conditioned on Kokoro bm_fable** (`chatterbox-kokoro-fable-ref-*`). It had the highest naturalness score of any British voice (UTMOS 4.40) and scored as English on all four lines. It is slightly brisker (3.1 words/s) and a little less dark than #1. The CPU speed caveat is the same.
3. **Kokoro bm_george** (`kokoro-bm_george-*`). This is the practical pick: about 2.5× *faster* than real time on CPU, under 2 GB of RAM, Apache-2.0, and easy to connect to Home Assistant today. It was clearly British on every line (4/4), the most unhurried Kokoro voice (2.45 words/s) and natural enough (UTMOS 4.22). As is typical of Kokoro, long sentences can sound a little even. **bm_fable** scores higher on naturalness (4.33) but less consistently English (2/4), so try both.

A sensible plan: run **Kokoro bm_george** live now. Try **Chatterbox + Kokoro-lewis** if the PC's AMD GPU can be made to run PyTorch, or pre-render the phrases Atlas repeats (greetings, "Done.").

## Voices delivered (12)

Speed is the real-time factor: synthesis time ÷ audio length, measured in this cloud sandbox (4 vCPU, no GPU, 15 GB RAM). **Below 1 is faster than real time.** RAM is the peak memory of the process. Expect the home PC to be faster per core.

| Model | Voice (files) | Licence · personal home use? | CPU speed (RTF) | RAM (peak) | Home Assistant integration | Naturalness (one-line, honest) |
|---|---|---|---|---|---|---|
| Kokoro-82M v1.0 | `bm_george` | Apache-2.0 · **yes** (commercial too) | 0.40 | ~1.6 GB | [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (OpenAI-compatible `/v1/audio/speech`, CPU and GPU images) → HA via an OpenAI-TTS custom integration, or via the [wyoming_openai](https://github.com/roryeckel/wyoming_openai) bridge into the Wyoming protocol | Clearly British, unhurried, warm; smooth but a touch even/flat across long sentences. UTMOS 4.22 |
| Kokoro-82M v1.0 | `bm_lewis` | Apache-2.0 · yes | 0.38 | ~1.6–1.9 GB | same as above | Deepest voice in the set (~86 Hz), strongly British, but the grainiest Kokoro voice. UTMOS 4.04 |
| Kokoro-82M v1.0 | `bm_daniel` | Apache-2.0 · yes | 0.36 | ~1.6–2.1 GB | same as above | British, clean, quicker and lighter than george; less "storyteller". UTMOS 4.19 |
| Kokoro-82M v1.0 | `bm_fable` | Apache-2.0 · yes | 0.34 | ~1.6–2.2 GB | same as above | Most natural Kokoro voice (UTMOS 4.33), but the accent classifier rates it only half-English: more neutral. |
| Piper (piper-tts 1.8) | `alan` (en_GB-alan-medium) | Engine GPL-3.0; voice data from Mimic 3 "apope", fine-tuned from lessac (licence unclear: fine for personal use, not for commercial use) · yes | 0.04 | ~0.35 GB | **Native**: official Wyoming Piper add-on, zero glue | Baseline: intelligible and clearly British but noticeably synthetic, with clipped VITS-style prosody. UTMOS 3.99 |
| Piper (piper-tts 1.8) | `northern-english-male` (en_GB-northern_english_male-medium) | Engine GPL-3.0; voice CC-BY-SA 4.0 (OpenSLR 83) · yes | 0.04 | ~0.45 GB | **Native** Wyoming Piper add-on | Pleasant Northern English accent, not "refined"; brisk; still sounds like a classic TTS voice. UTMOS 4.02 |
| Parler-TTS mini v1 | `storyteller` (text description below) | Apache-2.0 · yes | 6.6 | ~6.3 GB | No ready-made server; would need a custom OpenAI-compatible wrapper | Follows "slow, warm" but the accent came out American-leaning on all 4 lines, and the voice changes between lines. UTMOS 3.92 |
| Chatterbox (Resemble AI) 0.1.7 | `default` (built-in voice, exaggeration 0.5 / cfg 0.5) | MIT · yes; outputs carry Resemble's inaudible Perth watermark | 5.1 | ~6.8 GB | Community OpenAI-compatible servers (e.g. Chatterbox-TTS-Server, chatterbox-tts-api) → wyoming_openai or an OpenAI-TTS integration | Very natural, human phrasing (UTMOS 4.37), but the built-in voice is American. |
| Chatterbox 0.1.7 | `calm` (built-in voice, exaggeration 0.3 / cfg 0.3) | MIT · yes | 4.6 | ~6.8 GB | same as above | Calmer and slower than default; highest UTMOS of any built-in voice (4.42); still American. |
| Chatterbox 0.1.7 | `kokoro-fable-ref` (built-in model conditioned on a 10 s Kokoro bm_fable clip; exaggeration 0.4 / cfg 0.4) | MIT (+ Kokoro Apache-2.0) · yes | 5.0 | ~6.7 GB | same as above (these servers accept a reference WAV per voice) | **Top-2 pick.** British (4/4) with Chatterbox's natural delivery. UTMOS 4.40 |
| Chatterbox 0.1.7 | `kokoro-lewis-ref` (same, Kokoro bm_lewis clip) | MIT (+ Kokoro Apache-2.0) · yes | 5.2 | ~6.7 GB | same as above | **Top pick.** Most British-sounding voice in the whole test, lower and measured. UTMOS 4.37 |
| XTTS-v2 (coqui-tts 0.27) | `marcos-rudaski` (built-in studio speaker "Marcos Rudaski") | Weights: Coqui Public Model License, **non-commercial only** (code MPL-2.0) · yes for personal home use | 1.6 | ~4.3 GB | AllTalk TTS / openedai-speech (OpenAI-compatible) → wyoming_openai | British per the classifier (4/4) and the slowest pace (2.3 words/s), but less natural (UTMOS 3.82). XTTS occasionally hallucinates words (seen on another speaker). |

Parler description used: *"A man with a refined British accent speaks slowly and warmly in a gently melancholic, storytelling tone, very clear audio."*

### Tried but not delivered

To stay within the 8–12 target, and because some failed:

- **Parler-TTS large v1.** It ran, but produced unintelligible babble on all four lines (Whisper heard nothing usable; UTMOS 1.3). It needed ~11 GB RAM and was ~15–30× slower than real time on CPU. Not worth pursuing for the home PC.
- **Parler mini, second description** ("deep, smooth British… dry, wry"): worse intelligibility (word error rate 18%) and still American-leaning.
- **Chatterbox "expressive"** (exaggeration 0.75): faster, higher-pitched, less natural than default.
- **Chatterbox conditioned on Kokoro bm_george:** natural (4.31), but scored English on only 3 of 4 lines.
- **XTTS studio speakers.** All 29 male speakers were screened with one line. "Wulf Carlevaro" was similar to Marcos and was dropped for count. "Ige Behringer" hallucinated nonsense words at the start of line 1. The rest scored as American, Canadian or other accents.
- **Piper en_GB-semaine** (obadiah, spike): similar to alan, slightly less natural.
- **Not attempted: Orpheus TTS.** It is a 3B model with American voices only (Apache-2.0); too heavy for CPU, and it has no British voice.

## How the scores were made

`tools/eval_run.py` scores every WAV before MP3 conversion:

- **UTMOS** (`utmos22_strong`): a predicted naturalness "MOS" from 1 to 5. Above ~4.2 is good for TTS.
- **Accent:** the SpeechBrain CommonAccent ECAPA classifier (16 English accents). The table reports how many of the 4 lines it ranked "England" first, plus the England-minus-US score.
- **Intelligibility:** word error rate from faster-whisper `small.en` against the script.
- **Pitch and pace:** median pitch (pYIN) and words per second.

These measures are proxies. They can't hear wit or melancholy; only you can.

| Voice | UTMOS | England top (of 4) | WER | Median pitch | Words/s |
|---|---|---|---|---|---|
| chatterbox-kokoro-lewis-ref | 4.37 | 4 | 4% | 116 Hz | 2.61 |
| chatterbox-kokoro-fable-ref | 4.40 | 4 | 2% | 114 Hz | 3.07 |
| kokoro-bm_george | 4.22 | 4 | 4% | 143 Hz | 2.45 |
| kokoro-bm_fable | 4.33 | 2 | 1% | 112 Hz | 2.75 |
| kokoro-bm_daniel | 4.19 | 4 | 1% | 125 Hz | 2.87 |
| kokoro-bm_lewis | 4.04 | 4 | 1% | 86 Hz | 2.40 |
| chatterbox-calm | 4.42 | 0 (US) | 1% | 134 Hz | 3.21 |
| chatterbox-default | 4.37 | 0 (US) | 1% | 127 Hz | 3.66 |
| piper-northern-english-male | 4.02 | 4 | 8% | 119 Hz | 3.09 |
| piper-alan | 3.99 | 4 | 9% | 96 Hz | 2.48 |
| parler-mini-storyteller | 3.92 | 0 (US) | 8% | 131 Hz | 2.64 |
| xtts-marcos-rudaski | 3.82 | 4 | 4% | 124 Hz | 2.26 |

(The word error rate includes harmless differences such as "you've" vs "you have".)

## Running on the home PC (Windows, 31 GB RAM, CPU or AMD GPU)

- **Kokoro.** Real-time on CPU, so this works today. Kokoro-FastAPI has CPU Docker images. The ONNX build (`kokoro-onnx`) can also use DirectML on an AMD GPU under Windows.
- **Piper.** Trivial: the Wyoming Piper add-on, or the Wyoming container on the PC.
- **Chatterbox.** Too slow on CPU for live replies (~5× slower than real time). Options:
  - PyTorch on the AMD GPU via ROCm, either under WSL2 or with AMD's Windows ROCm builds where the card is supported. This is fiddly; check the card first.
  - Pre-render the phrases Atlas repeats.
  - Use Chatterbox for non-urgent announcements and Kokoro for quick replies.
  31 GB RAM is plenty (~7 GB peak).
- **XTTS-v2.** ~1.6× slower than real time on CPU, with streaming support. Usable with some delay. Non-commercial licence only.
- **Parler.** Not recommended: slow, and unreliable on British accents.

## Reproducing

`tools/` holds the scripts that made these files. Use one Python 3.11 venv per model with the CPU PyTorch wheels: `kokoro`, `piper-tts`, `parler-tts`, `chatterbox-tts` (+ `setuptools<81`), `coqui-tts` with `transformers<4.56` and `torch==2.8`. Each `*_run.py` writes WAVs to `tools/out/` and timings to `tools/stats.jsonl`. `to_mp3.sh` makes the MP3s, and `eval_run.py` scores them. The Kokoro script points phonemizer at the system `espeak-ng` (a Linux path), working around a broken bundled data path in `espeakng-loader`.
