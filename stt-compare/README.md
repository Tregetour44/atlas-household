# Atlas speech-to-text: local engines compared for this PC

Research and synthetic tests only, 21 Oct 2026. Nothing was installed in the house. The audio is all synthetic (open TTS voices) plus
the owner's text phrasings. The sandbox had a 4-vCPU Xeon at 2.1 GHz and no GPU. PC numbers are estimates until `bench/bench_pc.ps1` runs.

## Verdict

**Recommended:** **faster-whisper `small.en`, int8, on the CPU**, served by **wyoming-faster-whisper 3.8.1**. Give it the house's
names as a fixed initial prompt, and turn on its Silero `--vad-filter`:

```
--stt-library faster-whisper --model small.en --compute-type int8 --beam-size 5 --cpu-threads 8
--language en --vad-filter --initial-prompt "<house names, see testset/house_prompt.txt>"
```

| | today: HA Cloud (Azure), en-AU | recommended: small.en + house prompt, CPU | fast fallback: Parakeet TDT 0.6B v2, CPU |
|---|---|---|---|
| Command understood right (synthetic set, 240 clips) | NO DATA (see below) | **84.6%** | 72.5% |
| House words heard right (atrium, pergola, ensuite, loft, laundry, Good Night, Wind Down, kWh, ZeroCharge) | misheard "atrium" as "aperture" (21 Oct) | **95.8%** | 79.2% |
| STT time after end of speech for a 2-5 s command | included in 2.5-4 s | 1.6 s here; **est. 0.5-1.1 s on the 9700X** | 0.29 s here; est. 0.1-0.2 s |
| Whole hearing stage (HA's 0.7 s end-of-speech wait + STT) | **2.5-4 s** (measured) | **est. 1.2-1.8 s** | est. 0.8-0.9 s |
| Invents text on noise-only audio (9 clips) | - | 0/9 | 0/9 |
| RAM / VRAM | - | ~0.9 GB / **0** | ~1.0 GB / **0** |
| Private (audio stays in the house) | no | yes | yes |

Why this pick:

- **Prompting is the biggest win.** With the house names as a prompt, small.en goes from 74.2% to 84.6% command accuracy. House
  words go from 81% to 96% heard right. Clean WER falls from 9.2% to 6.8%, and noisy WER from 15.4% to 10.0%.
  - It is in the top group with large-v3-turbo + prompt (85.4%). The difference is within noise: 12 clips one way, 14 the other.
  - Turbo needs 3x the CPU time (est. 1.5-3.3 s on the 9700X), so it only makes sense on the GPU (see below).
  - Against Parakeet, small.en + prompt is right on 39 clips where Parakeet is wrong, and the reverse happens on 10 clips.
- **It does not invent house commands from noise.**
  - **Rejected despite good accuracy: Qwen3-ASR 0.6B + prompt (82.9%, est. 0.3-0.6 s).** On noise-only audio it read back its
    whole prompt on 9 of 9 clips ("Atlas, Good Night, Wind Down, ZeroCharge, …"). On TV babble it inserted "Good night". After a
    false wake word that is a wrong action, and the "Vocabulary:" prefix did not stop it.
  - **Whisper with `--vad-filter`:** 0/9 noise clips produce text. Without the filter, small.en + prompt once produced a stock
    "thanks for watching" line, and turbo + prompt said "Thank you." on all 9 noise clips.
  - The filter costs no accuracy: 83.8% with and without it, at beam 1.
- **The GPU stays with Gemma.** Everything here runs on the CPU, so the LLM's VRAM and speed are untouched.
- **It is the standard Home Assistant path.** It is the same Wyoming server as HA's Whisper add-on, and a pinned Docker image exists.

**When to choose otherwise:**
- If the PC bench shows small.en above about 1 s per command and speed matters more than names: use **Parakeet TDT 0.6B v2 int8**
  (`--stt-library sherpa --model sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8`). It is the fastest, silent on noise, and 12 points
  less accurate on commands, with no vocabulary biasing.
- Later upgrade, if the owner wants turbo-class accuracy at Parakeet speed: **whisper.cpp large-v3-turbo on the RX 9070 XT via
  Vulkan** (see "GPU routes").

**Speech-to-Phrase in front of it: no.** It would let through confident wrong actions.
- In front of the recommended engine, with a grammar tuned to the house, it raised command accuracy from 84.6% to 88.8%.
- But 4.6% of clips were accepted with the wrong command, well under its confidence gate. "Open the atrium blind at 1 pm" became
  "open the atrium blind" (now), "…in fifteen minutes" became "…in fifty minutes", and "10:30 pm" became "a m".
- That is the over-reach Atlas's safety bar forbids. There is also no STT-to-STT fallback in HA core (it needs a proxy), and it would
  run on the HA Green, slower than the PC's main engine.
- Details are under "Speech-to-Phrase".

**HA Cloud comparison: NO DATA.** The sandbox has no Nabu Casa account, and no secrets were used. No latency or accuracy figures are
published for it.
- It uses Microsoft Azure, and en-AU is supported.
- Since HA 2026.9 a Labs toggle offers a Soniox "STT v2" engine aimed at accents and noise. It is worth an A/B on the real house
  before switching.
- The owner's own measurement (2.5-4 s hearing stage; "atrium" heard as "aperture") is the baseline used above.

## Expected latency, step by step (PC estimates; the bench confirms)

| step | today (Cloud) | small.en + prompt | Parakeet v2 |
|---|---|---|---|
| End-of-speech detection (HA "finished speaking detection": default 0.7 s silence; relaxed 1.25 s, aggressive 0.25 s) | in the 2.5-4 s | 0.7 s | 0.7 s |
| Audio → Wyoming server on the LAN | upload to Azure | ~10-30 ms | ~10-30 ms |
| Transcription after end of speech | | 0.5-1.1 s | 0.1-0.2 s |
| **Hearing stage total** | **2.5-4 s** | **~1.2-1.8 s** | **~0.8-0.9 s** |

**How the PC estimate was made:** sandbox time ÷ 1.4 to ÷ 3.
- Low end: a published faster-whisper turbo figure on a Ryzen 9 9950X CPU (3.1-3.8 s per short utterance, Qiita, Oct 2026) implies
  only ~1.3x over this sandbox.
- High end: per-thread PassMark (9700X 4,643 against 2,469-3,258 for these Xeons) plus 8 cores instead of 2.

faster-whisper always encodes a 30 s window, so beam 1 saved nothing here. Short commands cost about the same as long ones.

## Wyoming deployment path (for the local team, after the owner's yes)

1. **Run the server on the PC, the same way as the existing local TTS.** Either option works.
   - **Docker Desktop (WSL2):**
     ```
     docker run -d --name atlas-stt --restart unless-stopped -p 10300:10300 -v C:\atlas\stt:/data rhasspy/wyoming-whisper:3.8.1 ^
       --stt-library faster-whisper --model small.en --compute-type int8 --beam-size 5 --cpu-threads 8 --language en ^
       --vad-filter --initial-prompt "<house names>"
     ```
   - **Native:** use a Python 3.12 venv with `wyoming-faster-whisper==3.8.1` and `av==16.1.0`:
     `python -m wyoming_faster_whisper --uri tcp://0.0.0.0:10300 --data-dir C:\atlas\stt <same flags>`.
   - After the first start, add `--local-files-only` so it never reaches the internet again.
2. **Write the prompt.**
   - Use the real house's areas first, then the device names people say, then scene and energy words, comma-separated. Keep it under
     about 200 Whisper tokens; `testset/house_prompt.txt` is about 120.
   - Use names only, and no personal names.
   - HA passes no prompt over Wyoming. The prompt lives in the server's flag, so update it when devices are renamed. Alternatively,
     the server's `--hass-token` option fetches exposed names itself; that needs a long-lived HA token stored on the PC, which is the
     owner's call.
3. **Connect HA.**
   - Go to Settings → Devices & services → Add integration → Wyoming Protocol, then enter the PC's LAN address and port 10300.
   - In Voice assistants → Atlas pipeline, set Speech-to-text to the new entity, language English.
   - Keep a second pipeline on HA Cloud as a manual fallback.
4. **Leave "finished speaking detection" on default at first.** Aggressive would save about 0.45 s but cuts off speakers who pause.
5. **Rollback:** switch the pipeline back to HA Cloud. Nothing else changes.

Deployment gotchas found while testing:
- faster-whisper 1.2.1 fails with PyAV ≥ 17 (`metadata_errors` error). Pin `av==16.1.0` for native installs.
- onnxruntime ≥ 1.27 refuses Qwen3-ASR's external weights when they are reached through the Hugging Face cache symlinks. This
  doesn't affect the pick, but use a plain model folder if Qwen is ever tried.
- whisper.cpp `whisper-server` on an RX 9070 XT under Windows crashes in `amdvlk64.dll` with flash attention on (whisper.cpp issue #3806).
  Use `-nfa`.

## GPU routes (RX 9070 XT; sandbox speed is NO DATA, figures are published ones)

| route | status Oct 2026 | speed on a 9070 XT | VRAM | verdict |
|---|---|---|---|---|
| whisper.cpp v1.9.5 Vulkan, large-v3-turbo | Works on Windows. No official Windows Vulkan binaries (self-build or third-party), no maintained Wyoming wrapper, flash-attn crash (#3806) | 0.16-0.23 s per ~2.6 s utterance end to end; encode 330 ms GPU vs 2,550 ms on a 9950X CPU (Qiita, 11 Oct 2026) | ~1.6 GB | Best "later" upgrade: turbo accuracy (85.4% with prompt) at ~0.2 s. GGML q5_0 turbo matched faster-whisper int8 turbo exactly on the shared clips here (89.3% / 2.8% WER on 28 clips). Needs a small Wyoming bridge and a bench run first |
| parakeet.cpp (in whisper.cpp ≥ 1.9) / wyoming-parakeet (Vulkan, Linux Docker) | Young; `parakeet-cli` only, no server in whisper.cpp | no AMD figures | <2 GB | Not needed: Parakeet is already ~0.1-0.2 s on the CPU |
| ONNX Runtime DirectML (onnx-asr Parakeet) | DirectML is in sustained engineering; onnx-asr lists DML support | NO DATA (bench stage 2 measures it) | - | Optional; no gain over CPU Parakeet expected |
| CTranslate2 4.8.3 ROCm wheels for Windows (gfx1201) | Released 13 Oct 2026, not on PyPI, untested in public | NO DATA | - | Too new; revisit |

**Headroom on the GPU:** a 12B Gemma at Q4_K_M with an 8k context takes ~9.5-10.5 GiB of the 16 GB. That figure is calculated from
Gemma 3 12B's published size and layer layout; check `ollama ps` for the real Gemma 4 number. Whisper turbo's ~1.6 GB fits. STT
runs before the LLM in each turn, so they rarely compete, but a published 9070 XT report saw slower STT while a local LLM was
generating. The bench's `-LlmLoad` switch measures this.

## Speech-to-Phrase (should it front common commands?)

This used the add-on's own recogniser library (OHF-Voice/apps `speech-to-phrase` v2.2.0: a NeMo Parakeet TDT-CTC 110M model
constrained by a grammar FST, with a score gate of 3.8). It ran standalone with this house's lights, blinds, scenes, rooms and floors
as HA registry records, on the core 240 clips. The fallback engine is used when S2P rejects.

| grammar | accepted | accepted & right | **accepted & wrong (wrong action)** | S2P alone | S2P in front of small.en+prompt / Qwen3+prompt / Parakeet |
|---|---|---|---|---|---|
| add-on defaults (24 command types, 450 templates) | 31.2% | 28.3% | **2.9%** | 28.3% | 84.6 → 87.9% / 82.9 → 86.7% / 72.5 → 78.3% |
| tuned to the house (+scenes, timers, percentages) | 60.8% | 56.2% | **4.6%** | 56.2% | 84.6 → 88.8% / 82.9 → 89.6% / 72.5 → 85.0% |

- **Every wrong accept is a confident near miss, and that is the worst kind for Atlas.**
  - Dropped schedules: "Open the atrium blind at 1 pm" → "open the atrium blind", and "Turn on pergola spotlight one at 6:45" →
    turn it on now.
  - Wrong numbers: fifteen → fifty minutes, eighty → thirty percent.
  - Wrong am/pm, a wrong device (ensuite → robe downlight), and "What's the temp?" → "what's the time".
  - The default grammar has no timed commands at all, so every "… at <time>" that fits a plain on/off gets cut down to "do it now".
- **No native fallback.** HA core has no STT-to-STT fallback, so fronting needs a proxy (e.g. the unmerged `stt-fallback` PR or `asr_proxy`).
- **Not faster than the PC.** It took 0.34 s (defaults) and 0.75 s (tuned) per command on this x86 sandbox. The HA Green's
  Cortex-A55 is slower still, while the PC's main engine already does the job in about a second.
- **Recommendation:** don't front it. Atlas's own deterministic timer fast path (`fastpath.py`) already handles fixed command shapes
  after STT, where they can be checked.

## Results

All tables are in [`results/tables.md`](results/tables.md). Per-clip transcripts and server metadata are in `results/raw/`.
Errors per engine can be regenerated with `scripts/score.py`.

**Core comparison**: 80 commands × (AU clean, GB clean, room noise) = 240 clips, CPU int8, through the Wyoming server, 4 threads.

| engine | WER clean | WER noise | cmd clean AU | cmd clean GB | cmd noise | **cmd all** | house words | owner phrasings | latency p50 here | est. 9700X | RAM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| faster-whisper large-v3-turbo + prompt | 6.5% | 4.8% | 76.2% | 91.2% | 88.8% | **85.4%** | 90.3% | 83.3% | 4.60 s | 1.5-3.3 s | 2.1 GB |
| **faster-whisper small.en + prompt** | 6.8% | 10.0% | 78.8% | 92.5% | 82.5% | **84.6%** | 95.8% | 78.8% | 1.60 s | 0.5-1.1 s | 0.9 GB |
| small.en + prompt, beam 1, vad-filter | 6.8% | 11.4% | 78.8% | 91.2% | 81.2% | **83.8%** | 94.4% | 78.8% | 1.47 s | 0.5-1.1 s | 1.3 GB |
| Qwen3-ASR 0.6B int4 + prompt (echoes prompt on noise) | 7.1% | 8.4% | 71.2% | 93.8% | 83.8% | **82.9%** | 89.6% | 86.4% | 0.89 s | 0.3-0.6 s | 1.7 GB |
| faster-whisper large-v3-turbo | 6.8% | 6.2% | 68.8% | 95.0% | 83.8% | **82.5%** | 86.8% | 84.8% | 4.26 s | 1.4-3.0 s | 2.1 GB |
| faster-whisper small.en | 9.2% | 15.4% | 61.3% | 93.8% | 67.5% | **74.2%** | 81.2% | 78.8% | 1.50 s | 0.5-1.1 s | 0.8 GB |
| Qwen3-ASR 0.6B int4 | 10.6% | 9.2% | 52.5% | 92.5% | 76.2% | **73.8%** | 72.2% | 80.3% | 0.78 s | 0.3-0.6 s | 1.5 GB |
| faster-whisper distil-large-v3 | 10.1% | 12.0% | 57.5% | 88.8% | 72.5% | **72.9%** | 77.1% | 72.7% | 4.45 s | 1.5-3.2 s | 1.9 GB |
| Parakeet TDT 0.6B v2 int8 (sherpa-onnx) | 10.4% | 14.8% | 61.3% | 91.2% | 65.0% | **72.5%** | 79.2% | 74.2% | 0.29 s | 0.1-0.2 s | 1.0 GB |
| Parakeet TDT 0.6B v3 int8 | 9.5% | 20.4% | 60.0% | 92.5% | 65.0% | **72.5%** | 75.0% | 81.8% | 0.37 s | 0.1-0.3 s | 1.0 GB |
| Kroko streaming zipformer (sherpa) | 13.8% | 15.2% | 48.8% | 85.0% | 63.7% | **65.8%** | 74.3% | 77.3% | 0.32 s | 0.1-0.2 s | 0.3 GB |
| whisper.cpp turbo q5_0, CPU build (60-clip subset) | | | | | | 70.0% on 60 clips (Parakeet: 58.3%) | | | 25.6 s | GPU only | 1.1 GB |

**Vocabulary prompting (house names):**
- small.en: 74.2 → 84.6%.
- turbo: 82.5 → 85.4%.
- Qwen3-ASR: 73.8 → 82.9%, but with prompt echo.
- Parakeet has no prompt support in the Wyoming server. distil-large-v3 is documented as ignoring the prompt, so it wasn't re-run.

**Far-field (all 604 clips; only Parakeet and Kroko ran on everything, budget):** Parakeet v2 command accuracy is 77.2% clean, 60.9%
in room noise and 56.3% far-field. Expect the same ordering for the others; far-field costs a further ~5-20 points.

**Accent control:**
- The AU voices are Piper VCTK speakers p326 and p374 (listed as Australian in VCTK's metadata; not re-checked here), plus p225 and
  jenny_dioco. They carry an approximate General-Australian vowel shift applied at the phoneme level.
- Without the shift, the same voices score Parakeet 74.2% / Qwen3+prompt 80.0%. With it they score 60.9% / 71.2%. GB (Kokoro/Piper)
  voices score ~93%.
- So part of the AU gap is the crude shift, and part is the lower-quality Piper voices. Absolute AU numbers are pessimistic, but every
  engine sees the same audio, so the ranking holds.

**Uncertainty:** 240 clips give about ±5 points (95%) per engine. Paired comparisons on the same clips are tighter:
- small.en + prompt vs Parakeet: 39 vs 10 clips (significant).
- vs Qwen3 + prompt: 20 vs 16 (a tie).
- vs turbo + prompt: 12 vs 14 (a tie).

## Method

**Test set** (`testset/commands.jsonl`, `scripts/gen_testset.py`):
- 151 commands and questions in Atlas's style: lights, brightness, timers, scenes, blinds, energy, climate, status, and the owner's
  22 real phrasings (`atlas-current/owner-phrasings.json`, written in normal spelling).
- House names come from the `voice-lewis-small` corpus: `train_ext4`, `heldout_r3`, and `gen_house.py`'s name list. That includes
  the held-out names (fountain spotlight, mirror ambiance, robe downlight, ensuite downlight, wall floodlight, …).
- Tricky words included: atrium, pergola, ensuite, loft, laundry, Good Night, Wind Down, kilowatt hours / kWh, ZeroCharge, numbers,
  times and percentages.
- Each item lists the **slots** that must be heard right for the action to be understood: target, on/off, number, time, scene, and
  key question words.

**Audio** (`scripts/render_audio.py`, `testset/audio/`, 16 kHz FLAC, 27 min):
- Every command was rendered by one AU and one GB voice: Piper VCTK p326/p374/p225/jenny with the vowel shift, and Kokoro
  bm_george/bf_emma/bm_lewis/bf_isabella plus Piper northern_english_male/cori/alan.
- Speed varies ±10%. espeak mis-stresses "pergola" and says "ensuite" as "insoot"; both were fixed at the phoneme level.
- **Room noise:** aircon/fan, 50 Hz hum, TV babble, or range hood plus clatter, at 5-15 dB SNR.
- **Far-field:** a simulated room (3.5-7 m, RT60 0.35-0.8 s, 2.5-5 m from the mic) plus fan or hum at 10-20 dB and a small-speaker
  band-pass.
- Plus 151 unshifted AU control clips and 12 noise-only clips.
- **Budget trim (PC Steward, 21 Oct: ceiling ~US$15):** after Parakeet and Kroko, the remaining engines ran on 80 commands × (AU
  clean, GB clean, noise) = 240 clips. Every table compares engines on identical clips.

**Metrics** (`scripts/textnorm.py`, `scripts/score.py`, `scripts/report.py`):
- **WER** uses Whisper's English normaliser plus house folding ("10:15 pm" = "ten fifteen p m"; "30%" = "thirty percent";
  "kWh" = "kilowatt hours"; "Zero Charge" = "ZeroCharge").
- **Command accuracy** means all slots are heard right. It is strict: Parakeet's "7-5%" for seventy-five, or "chandelier too" for
  "two", count as wrong.
- **Latency** runs from Wyoming `audio-stop` to the transcript arriving, through the real server, after a warm-up. It excludes HA's
  end-of-speech wait.
- **RAM** is the server's peak RSS.

**Engines:**
- Everything ran through `wyoming-faster-whisper` 3.8.1 (`scripts/wyoming_bench.py`), except:
  - whisper.cpp (`whisper-server`, beam 5, `-nfa`; `scripts/cpp_bench.py`);
  - Speech-to-Phrase (`scripts/s2p_bench.py`).
- Runners: `scripts/run_matrix.sh`, `scripts/run_core.sh`, `scripts/run_final.sh`.

## Files

| path | what |
|---|---|
| `bench/bench_pc.ps1`, `bench/pc_bench.py`, `bench/manifest_pc.jsonl` | **PC bench**, about 5 min after ~3 GB of downloads, all inside `bench\work\`. See "Running the PC bench" |
| `testset/` | commands, house prompt, audio (604 + 151 + 12 clips) and manifests |
| `scripts/` | generator, renderer, normaliser, harnesses, scorer, report |
| `results/` | `tables.md`, `summary.json`, `raw/` transcripts + metadata + Speech-to-Phrase grammars |
| `STATUS.md` | progress log |

### Running the PC bench

From a checkout of this branch, on the PC, with Ollama running as usual:

```
cd stt-compare\bench
powershell -ExecutionPolicy Bypass -File .\bench_pc.ps1                         # CPU + DirectML stages
powershell -ExecutionPolicy Bypass -File .\bench_pc.ps1 -SkipDirectML -LlmLoad -OllamaModel <model>   # with Gemma generating
powershell -ExecutionPolicy Bypass -File .\bench_pc.ps1 -WhisperCppDir C:\path\to\whisper.cpp-vulkan\bin   # + GPU Whisper
```

- It writes `stt-compare\pc-results\<stamp>\summary.md`: command accuracy, p50/p95 latency, RAM and peak VRAM per engine on 60 clips.
- **What decides it:** if small.en + prompt shows p50 ≤ ~0.8 s, deploy it as above. If it is well above 1 s, prefer Parakeet v2 now
  and plan the Vulkan route.
- Delete `bench\work\` afterwards.
