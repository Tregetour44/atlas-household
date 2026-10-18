# Chatterbox reference clips

These are the exact files passed as `audio_prompt_path` to Chatterbox for the `chatterbox-kokoro-lewis-ref-*` and `chatterbox-kokoro-fable-ref-*` samples. Both are synthetic Kokoro speech; no human recording is involved.

They are byte-identical to the files used. They were created at 14:26:58 UTC on 2026-10-18, before either Chatterbox run (14:28 to 14:35), and were not modified afterwards. Check them with `sha256sum -c SHA256SUMS`.

| File | sha256 | Kokoro voice | Speed | Seed |
|---|---|---|---|---|
| `kokoro-bm_lewis.wav` | `0a726d38e17dbce88b0bbe54ee4f070d334cbfa7f091da23abfc9f8d373f9ff1` | `bm_lewis` | 0.92 | **none set** (see below) |
| `kokoro-bm_fable.wav` | `e50c03e666607abbe88056a4eca746a8097dc153ab09bd84b312af794c86fd47` | `bm_fable` | 0.92 | **none set** (see below) |

Both files are WAV, PCM 16-bit, mono, 24 000 Hz, exactly 10.000 s (240 000 samples).

## Text

Kokoro was given the whole of sample line 2:

> If you are hoping for good news, I'm afraid you have come to the wrong assistant. The dishwasher is finished, the bins go out tomorrow, and the battery, unlike most things in this story, is in perfectly good shape.

Each clip is the first 10.000 s of that output, so each one stops partway through the line. The words actually heard in each clip (endpoints from faster-whisper `small.en` word timestamps) are:

- **`kokoro-bm_lewis.wav`**: "If you are hoping for good news, I'm afraid you have come to the wrong assistant. The dishwasher is finished, the bins go out tomorrow, and the battery" ("battery" ends at ~9.98 s; the cut falls at the comma pause after it).
- **`kokoro-bm_fable.wav`**: "If you are hoping for good news, I'm afraid you have come to the wrong assistant. The dishwasher is finished, the bins go out tomorrow, and the battery, unlike most things in this story" ("story" ends at ~9.72 s; ", is in perfectly good shape." is cut off).

## How they were made

1. `tools/kokoro_run.py` generated `kokoro-bm_<voice>-2.wav` (sample line 2) with these settings:
   - `KPipeline(lang_code="b")`, i.e. British English G2P;
   - `voice="bm_<voice>"`, `speed=0.92`;
   - chunks concatenated, written by `soundfile` as 16-bit PCM at 24 kHz.

   One warm-up call (`"Warm up."`, bm_george) ran first in the same process. The four voices then ran in the order george, lewis, daniel, fable.
2. The first 10 s were cut with `ffmpeg -i kokoro-bm_<voice>-2.wav -t 10 refs/kokoro-bm_<voice>.wav`. The samples were verified to be an exact, unaltered prefix of the step-1 output: no resampling, gain or fades.

Versions: kokoro 0.9.4 and misaki 0.9.4 (espeak-ng 1.51 system library for fallback), torch 2.14.1+cpu, Linux x86-64, 4 threads. Weights came from `hexgrad/Kokoro-82M` at revision `f3ff3571791e39611d31c381e3a41a3af07b4987`:

| Weights file | sha256 |
|---|---|
| `kokoro-v1_0.pth` | `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4` |
| `voices/bm_lewis.pt` | `b5204750dcba01029d2ac9cec17aec3b20a6d64073c579d694a23cb40effbd0e` |
| `voices/bm_fable.pt` | `d44935f3135257a9064df99f007fc1342ff1aa767552b4a4fa4c3b2e6e59079c` |

## Seed: none, so these files cannot be regenerated bit-for-bit

No random seed was set when these clips were made. Kokoro's vocoder adds random noise, so its output is not bit-reproducible without a seed. Re-running the same voice, text and speed afterwards gave the same length (344 400 and 290 400 samples) but different samples: the maximum difference was 8 544 for lewis and 5 489 for fable, out of a 16-bit range of 32 767. That is perceptually the same voice, but not the same file.

**These committed WAVs are therefore the only exact copies.** Use them, not a regeneration, if the Chatterbox voices must match the samples.

For future clips, call `torch.manual_seed(0)` immediately before each Kokoro call. With that, two consecutive runs of bm_lewis on this text came out bit-identical in this environment. Identity across different CPUs or torch versions is not guaranteed.

## Chatterbox settings that used these clips

`ChatterboxTTS.from_pretrained("cpu")`, chatterbox-tts 0.1.7, with these settings:

- `generate(text, audio_prompt_path=<clip>, exaggeration=0.4, cfg_weight=0.4)`;
- the defaults `temperature=0.8`, `repetition_penalty=1.2`, `min_p=0.05`, `top_p=1.0`;
- `torch.manual_seed(7)` before each line.
