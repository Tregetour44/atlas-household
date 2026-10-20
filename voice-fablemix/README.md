# voice-fablemix: Kokoro "Fable-mix" for Atlas's Windows CPU voice server

## Verdict

**Ready to deploy**, subject to one check that needs the desktop and one that needs ears:
- **Desktop:** run `eval/bench.py` there (5 minutes); every speed number below is scaled from a cloud sandbox.
- **Ears:** listen to `samples/`. Every quality judgement here rests on measurement proxies; I could not listen.

| | |
|---|---|
| **Engine** | **ONNX Runtime 1.31** (CPU) running the **onnx-community Kokoro-82M v1.0 fp32 ONNX**, fed **misaki 0.9.4 British G2P** (`lang_code="b"`, the same phonemes the kokoro package uses), with the scout's Fable-mix pack at speed 0.95. No PyTorch, no espeak-ng install, no admin rights, no Docker, no network at runtime. |
| **Parity** | Same phonemes in, same durations out. On 38 lines it is within PyTorch Kokoro's own run-to-run spread on UTMOS, F0, WER, accent and speaker similarity, and PyTorch reproduces the scout's clips (ECAPA 0.995). See `eval/README.md` §1. |
| **First audio** | Measured here (4 vCPU Xeon 2.1 GHz, 4 threads, warm): **0.54 s** (3 words), **1.08 s** (15 words), **1.34 s** (40 words). **Estimated on the 9700X: about 0.3–0.55 s for 15 words**, which meets the ~1 s target with margin. The cold first call is about 15 % slower; the server's warm-up render at startup absorbs it. |
| **Speed** | RTF 0.23 here; estimated 0.07–0.12 on the desktop. |
| **RAM** | 0.97 GB resident after load, **1.34 GB peak** (measured on Linux). Load takes 3.0 s, including the sha256 of all 311 MiB. |
| **Install** | 75 hash-pinned wheels, 93.4 MiB (`requirements.lock`) + a 311 MiB model bundle (`fetch_bundle.py`). PyTorch Kokoro would need 93 wheels and 227 MiB, including torch. |
| **Fixed** | Sing-song short replies (F0 range −32 %) · real pauses between sentences · "Timer set" heard as "Time a set" (4/8 → 0/8) · "a m" read "uh em" · "Wind Down" · "ensuite" · "aircon" · one-word pieces gaining a spurious "It's"/"I'm" · a click on punctuation-only text · the ONNX export's +3.4 dB level (peaks to 0.985 FS). |
| **Left** | Kokoro is weak on **single-word replies** ("Done." alone scores UTMOS 3.1). **No silence before a one-word sentence** ("…on. Checked.") because it must ride with its neighbour. **L01** "Done. Kitchen lights off." still leans American on the classifier (Eng−US −0.22). **Desktop speed and thread count: NO DATA**. |

**What the local team does:** `INTEGRATION.md`, in one sitting. The factory call becomes `kokoro_synth(model_dir, speed=0.95, threads=6)`; the sample rate is 24000; the PCM cap is 48,000 bytes per second; the Wyoming voice is `en_GB-fablemix`; plus the install steps.

## Files

| Path | What |
|---|---|
| `kokoro_backend.py` | The drop-in factory, about 280 lines, standard library + the locked packages; `mypy --strict` and ruff clean |
| `test_kokoro_backend.py` | 17 offline tests, about 60 s here |
| `requirements.lock` | CPython 3.12 win_amd64, 75 wheels, every one `--hash=sha256:` |
| `fetch_bundle.py`, `bundle/manifest.json` | Install-time download and check of the 4 bundle files; the two voice files ship in `bundle/` |
| `INTEGRATION.md` | Exactly what changes in the server |
| `PRONUNCIATION.md` | The fix list, with phonemes, evidence and samples |
| `eval/README.md` | The quality and parity report, per line |
| `eval/bench.py` | Speed and memory benchmark; run it on the desktop |
| `samples/` | MP3s, loudness-matched to −18 LUFS (two-pass), mono, 96 kbps: `fablemix-L01…L10` and `fablemix-all.mp3` (joined); house lines `fablemix-H01…H08`, `-W01…W12` and `fablemix-house-all.mp3`; `fixes/*-before.mp3` / `*-after.mp3` (14 pairs) |
| `tools/` | `make_lock.py` (the lock from PyPI JSON), `convert_voice.py` (rebuilds both voice files from the scout's `.pt`; needs torch), `to_mp3.py`, and `lab/` (every experiment script and line list) |

## 1. Engine choice

Three runtimes were considered: Kokoro's own PyTorch package, ONNX Runtime with the onnx-community export (in fp32, fp16 and int8), and the `kokoro-onnx` package. All except `kokoro-onnx` were fed the same misaki phonemes.

| | kokoro 0.9.4 (PyTorch) | **ONNX Runtime + misaki (chosen)** | kokoro-onnx 0.6 package |
|---|---|---|---|
| G2P | misaki British | misaki British (identical phonemes) | espeak-ng `en-gb` via phonemizer, **not** misaki. Kokoro was trained on misaki phonemes, so not used |
| Parity with the scout's renders | Reference (ECAPA 0.995 to the scout's clips) | Within PyTorch's seed spread (§1 of `eval/README.md`) | Not tested (different G2P) |
| Deterministic | Only with a fixed seed per call (the sine source draws random noise) | Yes: no random operators in the graph | Same graph as ours |
| Wheels (win_amd64, cp312) | 93, **227 MiB** (torch 118 MiB, transformers, huggingface_hub, …) | **75, 93.4 MiB** | similar to ours |
| Network-capable libraries imported at runtime | `huggingface_hub` (downloads unless told not to), `transformers` | none that download. spaCy imports `requests`; nothing calls it | — |
| Model file | `kokoro-v1_0.pth` 312 MiB | `model.onnx` 310 MiB | same ONNX |
| First audio, 15 words (here, 4 threads) | 1.36 s | **1.08 s** | — |
| RTF (here, 4 threads) | 0.27 | **0.23** | — |
| Load / peak RSS | 5.9 s / 1.58 GB | **3.0 s / 1.34 GB** | — |

**Recommendation: ONNX Runtime + misaki.** It is the same model, with the same phonemes and durations. It is deterministic, 20 % faster to first audio here, loads in half the time, uses 0.24 GB less memory, and is less than half the download. It imports no download-capable model hub.

The two other ONNX files in the onnx-community repository must not be substituted:
- **fp16 returns all-NaN audio** for 8 of 38 lines on CPU.
- **int8 changes durations** and accent (30/38 British vs 33), and was no faster.

The voice pack needed no model conversion. The scout's `.pt` is saved as a plain float32 NumPy array (`en_GB-fablemix.npy`), with bit-identical values and no pickle. `tools/convert_voice.py` rebuilds it and checks it.

Windows notes:
- espeak-ng comes as a DLL inside the `espeakng-loader` wheel. misaki uses it only for words outside its lexicon.
- `phonemizer` copies that DLL to a fresh `%TEMP%` folder at load and deletes it at exit. Give the service user a private `TEMP` (see `INTEGRATION.md`).
- The one wheel not on PyPI is spaCy's `en_core_web_sm` 3.8.0. It is pinned by URL and sha256 to spaCy's GitHub release.
- `docopt`, a dependency of num2words, is sdist-only. It is left out because only num2words' command-line script imports it.
- Everything else installs from wheels.

## 2. The backend (`kokoro_backend.py`)

`kokoro_synth(model_dir, speed=0.95, threads=None) -> (synth, 24000)`. `synth(text)` yields 16-bit little-endian mono PCM bytes.

- **Verified load, fail closed.**
  - Each of the four bundle files is read once and its sha256 checked against constants in the code. Only those bytes are used: the ONNX session is built from the bytes, and the voice files are loaded with `np.load(allow_pickle=False)`.
  - Anything missing, truncated or altered raises `BundleError` before a model exists.
  - A missing spaCy model also raises `BundleError`; otherwise misaki would try to download it.
- **No network.**
  - It sets the Hugging Face offline flags and turns off ONNX Runtime telemetry.
  - The isolation test runs a fresh interpreter with an audit hook that blocks every connect, DNS lookup, send, URL open and `os.system`. Load and synthesis succeed with zero attempts.
  - The only socket activity is urllib3's IPv6 probe at import: it binds `::1` port 0 and never connects. On Linux, phonemizer's `dlinfo` also runs `ldconfig -p` once; that doesn't happen on Windows.
- **No text in logs.** The module prints and logs nothing. phonemizer's logger is disabled, and warnings are suppressed around G2P. Errors from `synth` read only `synthesis failed: <ExceptionType>`, with no chained traceback. The test feeds a marker sentence and checks it appears in no output stream, with logging at DEBUG.
- **Chunking for first audio.**
  - Replies are split into sentences, and a sentence over 150 phonemes (about 8 s of speech) into clauses.
  - Each piece's PCM is yielded as soon as it is rendered.
  - A one-word sentence is rendered with its neighbour.
  - Pieces never exceed Kokoro's 510-phoneme limit; at worst they are split at word gaps.
- **Joins.** Kokoro pads every piece with about 0.27 s of silence before and 0.3 s after, and leaves *no* audible pause at a full stop inside a piece (none over 80 ms). The backend trims each piece to 30 ms of its padding, then adds 0.3 s after a sentence (0.35 s after a question), 0.25 s after a colon, 0.15 s after a comma, and 0.1 s at the end.
- **Deterministic.** The graph has no random operators, and ONNX Runtime runs with `use_deterministic_compute`. The tests check byte-identical output across calls and across loads.
- **Threads.** `threads=None` lets ONNX Runtime take one thread per physical core; `inter_op` is 1.
- **Size.** About 280 lines, `mypy --strict` and ruff clean. The tunables are module constants, each with its measured reason.

## 3. The model bundle

| File | Size | sha256 | Source | Licence |
|---|---|---|---|---|
| `kokoro-v1.0.onnx` | 325,532,232 | `8fbea51ea711f2af382e88c833d9e288c6dc82ce5e98421ea61c058ce21a34cb` | [onnx-community/Kokoro-82M-v1.0-ONNX @ 1939ad2](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/1939ad2a8e416c0acfeecc08a694d14ef25f2231/onnx/model.onnx) `onnx/model.onnx` | Apache-2.0 |
| `config.json` | 2,351 | `5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f` | [hexgrad/Kokoro-82M @ f3ff357](https://huggingface.co/hexgrad/Kokoro-82M/resolve/f3ff3571791e39611d31c381e3a41a3af07b4987/config.json) | Apache-2.0 |
| `en_GB-fablemix.npy` | 522,368 | `5de2db9de4510efd4b3dd9f64bf0cf03530089b2220aec95f43f3b27636fbf80` | `bundle/` here; from `voice-scout/voices/kokoro-fablemix.pt` (sha256 `cadc5c98dc83ac96214afbdb8952ddb0edc88ccfd95adbdb97ea96ca332e6d79`) | Apache-2.0 (Kokoro voices) |
| `en_GB-fablemix-short.npy` | 522,368 | `86faab493d94047df677164f5743b9cf62084168bd83cbc1551bf48e39eb1ed5` | `bundle/` here; built by `tools/convert_voice.py` | Apache-2.0 (as above) |

`fetch_bundle.py C:\AtlasVoice\kokoro` downloads to a `.part` name, checks the hash, then renames, so a mismatch deletes the file and exits 1. Files already present and correct are skipped. It uses the standard library only. All three paths were tested: a fresh fetch in 5.5 s, a re-run that skips, and a wrong hash that fails with nothing left behind.

## 4. The Windows lock

`requirements.lock`: 75 wheels for CPython 3.12 win_amd64, **97,904,129 bytes (93.4 MiB)**.
- Every hash is PyPI's own `digests.sha256` from its JSON API (`tools/make_lock.py` picks the exact wheel pip would choose for cp312 / win_amd64).
- Regenerating it from PyPI gives a byte-identical file.
- `pip download --platform win_amd64 --python-version 3.12 --implementation cp --abi cp312 --only-binary :all: --no-deps --require-hashes -r requirements.lock` fetched and verified all 75 wheels, 97,904,129 bytes.

Not installable from wheels: `docopt` (left out, see above). Not on PyPI: `en_core_web_sm` (pinned by URL and hash). The resolved list is `tools/resolved-win_amd64.txt` and the top-level pins are `tools/requirements.in`. It includes `colorama` (a Windows-only dependency of click and tqdm).

Install it into a fresh venv:

```
py -3.12 -m pip install --require-hashes --no-deps --only-binary :all: -r requirements.lock
```

The sandbox is Linux, so the Windows install itself is **NO DATA**. pip's own platform resolution and hash check passed for every wheel, and the same versions run the tests on Linux.

## 5. Tests

`py -3.12 -I test_kokoro_backend.py -v` with `ATLAS_KOKORO_DIR` set to the bundle: 17 tests, about 60 s here, offline, all passing.

- PCM format (bytes, even length, 16-bit, not silent) and the 24000 rate.
- Chunking: the piece count matches the plan, and the one-word "Checked." rides with its sentence.
- First audio arrives in under a third of the total time.
- Empty and whitespace-only input (including non-breaking spaces) yields nothing; punctuation-only yields nothing or silence.
- Long text: 24 sentences, and 1,300 characters with no punctuation at all.
- Byte-identical output across calls and across loads.
- An error message carries no text.
- The house-word phonemes, including capitalised forms.
- Bad arguments are rejected.
- Bundle integrity: an intact copy loads; a flipped byte in the voice pack, a changed config, a truncated model and a missing file each raise `BundleError`.
- Isolation: a child process with network calls blocked by an audit hook loads and speaks; no text appears in stdout or stderr with logging at DEBUG; the only socket activity is the loopback probe; no child processes on Windows.

## 6. The weak spots: before and after

The full numbers are in `eval/README.md`; the fix list is in `PRONUNCIATION.md`; the samples are in `samples/fixes/`.

**Short lines sound sing-song.** On 19 short replies, rendered through the shipped `synth`:

| | median F0 | F0 spread | F0 range (p10–p90) | ending | UTMOS | British | WER |
|---|---|---|---|---|---|---|---|
| before (the scout's way) | 116 Hz | 5.70 st | 15.9 st | −9.4 st | 4.354 | 15/19 | 2.1 % |
| **after** | 114 Hz | **4.00 st** | **10.8 st** | −6.0 st | **4.394** | 15/19 | 0.8 % |

What I tried:

| Tactic | Result | Kept? |
|---|---|---|
| Per-length speed (0.90, 1.00) | Little effect on spread | No |
| Style-row floors on the plain pack (40, 80, 120) | Flattened the pitch but cost UTMOS (−0.02 to −0.06) | Not alone |
| Separate sentences without merging | Mangled one-word sentences ("I'm checked", "It's done") | Only for multi-word sentences |
| More bm_george in the prosody half (the scout's suggestion) | More British (18/19) but **+17 Hz**: younger, against the brief | No |
| Flatter prosody from the mature fitted pack, plus a style floor | Best balance | **Shipped** |

The shipped fix is a *short-reply pack*. It keeps Fable-mix's timbre half and makes the prosody half 50 % bm_fable + 50 % the inno-kokoro fitted mature pack, recovered exactly from Fable-mix itself. It is used with a style floor of 40 phonemes and fades linearly back to Fable-mix by 60.

**"Timer set:" was heard as "Time a set"** on 4 of 8 lines; "Timer cancelled." was heard as "Time are cancelled".
- misaki's `tˈImə` lets the schwa float free of the word.
- misaki's own phonemes as an override changed nothing (4/8).
- Rewrites worked: "Timer's set" 0/8, "I've set a timer" 0/8, "Timer set." 0/8 but with UTMOS −0.1.
- **The shipped fix is a lexicon entry, `timer` → `tˈImˌə`: 0/8 with Atlas's wording unchanged**, and "Timer cancelled." is fixed too.

**House words** (`PRONUNCIATION.md`):

| Word | Before | Fix | After |
|---|---|---|---|
| ensuite | Whisper heard "N-suit" / "ensuit" | Lexicon `ɒnswˈiːt` | "on-suite" |
| aircon | Whisper heard "ayakin" | Lexicon `ˈɛːkɒn` | "aircon" |
| Wind Down | `wɪnd` (breeze) as a name | Phoneme override | `waɪnd` |
| "a m" / "p m" | "uh em", and the full stop dropped | Rewritten to AM / PM | Read cleanly |

Good Night, pergola, atrium, kilowatt hours, ZeroCharge, chandelier, Robe and floodlight were already right.

**Also found and fixed:**
- Lexicon fixes silently missed capitalised words (misaki keeps separate entries).
- Text that is only punctuation rendered a click.
- The ONNX export is 3.4 dB hotter than Kokoro's PyTorch output.
- Kokoro's padding added about 0.6 s of dead air at every piece join, and 0.27 s before the first audio.
- Square brackets in a reply would have reached misaki's inline phoneme syntax; they are now neutralised.

## 7. Speed and memory

Measured with `eval/bench.py` on the cloud sandbox (4 vCPU Intel Xeon @ 2.1 GHz, 15 GB, nothing else running). Each thread count ran in a fresh process. "Warm" is the median of 5 calls after the first. The replies:
- **Short:** "Kitchen lights off." (3 words, 1.8 s of audio)
- **Medium:** "I've turned the porch lights off, and the living room lamp is at forty percent." (15 words, 4.6 s)
- **Long:** two sentences, 40 words, 12.8 s; first audio is its first sentence.

| threads | load | first audio: short | medium | long | cold medium (first call) | RTF | RSS after load / peak |
|---|---|---|---|---|---|---|---|
| 1 | 3.2 s | 1.29 s | 3.20 s | 4.14 s | 3.47 s | 0.69 | 1.17 / 1.33 GB |
| 2 | 3.2 s | 0.76 s | 1.70 s | 2.30 s | 2.20 s | 0.37 | 1.17 / 1.33 GB |
| 3 | 3.3 s | 0.64 s | 1.34 s | 1.55 s | 1.41 s | 0.28 | 1.17 / 1.33 GB |
| **4** | **3.0 s** | **0.54 s** | **1.08 s** | **1.34 s** | **1.25 s** | **0.23** | 1.17 / 1.34 GB |
| PyTorch, 4 | 5.9 s | 0.53 s | 1.36 s | 1.59 s | 1.67 s | 0.27 | 1.25 / 1.58 GB |

- The "RSS after load" column is the peak up to that point (`ru_maxrss`). Resident memory after load is 0.97 GB (VmRSS).
- ONNX Runtime's memory-arena and prepacking switches and a lower optimisation level changed this by under 5 %.
- **The best thread count here is all 4.** Every added thread helped; 2 → 4 threads gave 1.57× on first audio.

**Scaled to the 9700X (estimates, NO DATA from the desktop)**, using the scout's method:
- Assume one Zen 5 core is 1.6–2.2× one cloud vCPU.
- Assume 4 → 8 cores gains between √1.57 and 1.57.

| | first audio: short | medium | long | cold medium | RTF |
|---|---|---|---|---|---|
| 9700X, 8 threads (est.) | 0.16–0.27 s | **0.31–0.54 s** | 0.39–0.67 s | 0.36–0.62 s | 0.07–0.12 |

The ~1 s target for a medium reply is reachable with margin, even at the pessimistic end and even cold. A reply's first sentence dominates first audio: a single 150-phoneme sentence (about 8 s of speech) is the worst case before clause splitting starts, at about 0.6–1.0 s on the desktop.

Memory on Windows should be similar, about 1 GB working set, but that is NO DATA. `bench.py` reports `PeakWorkingSetSize` there.

**Thread count on the desktop:** NO DATA. Start with `threads=6`, which leaves two cores for the rest of the desktop, and run `python -I eval\bench.py C:\AtlasVoice\kokoro 4,6,8` to pick. ONNX Runtime's default (`None`) is 8, one per physical core. SMT threads beyond 8 rarely help ONNX Runtime.

## 8. Samples

All 24 kHz mono MP3, 96 kbps, loudness-matched to −18 LUFS (two-pass: measure, set the gain, limit at −1.5 dBFS). The scout used single-pass loudnorm, which left short clips about 2 LU quiet.

- `samples/fablemix-L01…L10.mp3`, `fablemix-all.mp3`: the 10 audition lines, final engine and settings, and all 10 joined with 0.5 s gaps.
- `samples/fablemix-H01…H08.mp3`: the held-out house lines. `fablemix-W01…W12.mp3`: the house-word lines (Good Night, Wind Down, ensuite, pergola, atrium, kilowatt hours, ZeroCharge). `fablemix-house-all.mp3`: all 20 joined.
- `samples/fixes/<fix>-<line>-before.mp3` and `-after.mp3`. "Before" is the same engine run the scout's way.
  - Short lines: `short-L01`, `short-L10`, `short-F03` ("Porch lights on."), `short-F04` ("Good night.").
  - Timer: `timer-H03`, `timer-F01` ("Timer cancelled.").
  - AM / PM: `ampm-F02`, `pmstop-W09`.
  - Words: `winddown-W02`, `ensuite-H04`, `aircon-A12`.
  - Pauses: `pauses-L05`, `pauses-A07`.
  - One word: `oneword-F05` ("Done.").

## 9. What's left, and NO DATA

- **Listening.** All judgements are proxies: UTMOS, pitch statistics, Whisper, an accent classifier and speaker embeddings. Listen above all to the pauses (0.3 s after a sentence was chosen, not measured against people) and to the short-reply prosody.
- **The desktop itself.** Speed, best thread count, Windows working set and the Windows install itself (the lock was verified with `pip download` for win_amd64, not installed on Windows) are all NO DATA.
- **One-word replies** remain weak in Kokoro (UTMOS 3.1 for "Done." alone). If Atlas ever says a bare word, "All done." will sound better.
- **No pause before a one-word closing sentence** ("…on. Checked."). Kokoro gives one-word pieces a spurious onset, so they must share an inference, and Kokoro puts no silence at a full stop inside an inference. The real fix would be the ONNX graph exposing its durations, so a pause could be cut in at the boundary. That means shipping a modified model; not done.
- **L01 and A02 lean American** on the accent classifier (−0.22, −0.37), as the scout found for some short lines. The other British-count changes are within run-to-run noise.
- **KVoiceWalk** (the scout's suggestion to polish the pack) was not run. It is a voice change, not a deployment task, and the owner chose this pack.

## Licences (my reading, not legal advice; private household use)

- **Kokoro-82M** weights, voices and config: Apache-2.0 (hexgrad).
- **The ONNX export:** Apache-2.0 (onnx-community).
- **The Fable-mix packs** derive from Kokoro voices and an inno-kokoro fitted pack. inno-kokoro is Apache-2.0; its speaker encoder (CC BY-SA 3.0) was used only to fit the pack, and isn't shipped.
- **Runtime packages:**
  - onnxruntime MIT; spaCy, thinc and en_core_web_sm MIT; misaki Apache-2.0; numpy BSD; num2words LGPL.
  - **phonemizer-fork GPL-3.0+** and **espeak-ng (inside espeakng-loader) GPL-3.0+**, the same espeak-ng the current Piper setup already uses. GPL obligations arise on distribution, not on private use.
- No human recording was used and no real person was cloned. The voice descends from Kokoro's synthetic bm_fable.
