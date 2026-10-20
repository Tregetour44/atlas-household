# Swapping Piper for Kokoro Fable-mix: what changes in the server

Everything here is for the existing hardened Wyoming TTS server on the Windows desktop. The server keeps its own admission, caps, single-synthesis lock, watchdog, logging rules and text normaliser. Only the factory, the sample rate, one cap and the advertised voice change. Budget about an hour, most of it the downloads and the test run.

## 1. Install (once, as the server's own Windows user, no admin rights)

Nothing system-wide is installed: no espeak-ng (its DLL ships inside the `espeakng-loader` wheel), no Docker, no PyTorch. The network is used only during these steps.

```bat
:: 1. A fresh venv next to the server's (any folder the server user can write).
py -3.12 -m venv C:\AtlasVoice\venv-kokoro
C:\AtlasVoice\venv-kokoro\Scripts\python -m pip install --upgrade pip

:: 2. The 75 locked wheels (93.4 MiB). Every wheel is hash-pinned; nothing is resolved or built.
C:\AtlasVoice\venv-kokoro\Scripts\python -m pip install --require-hashes --no-deps --only-binary :all: -r voice-fablemix\requirements.lock

:: 3. The model bundle (4 files, 311 MiB), each checked against its sha256.
C:\AtlasVoice\venv-kokoro\Scripts\python -I voice-fablemix\fetch_bundle.py C:\AtlasVoice\kokoro

:: 4. The backend's tests against that bundle (about a minute; no network).
set ATLAS_KOKORO_DIR=C:\AtlasVoice\kokoro
C:\AtlasVoice\venv-kokoro\Scripts\python -I voice-fablemix\test_kokoro_backend.py -v
```

Then copy `voice-fablemix\kokoro_backend.py` next to the server's own modules (it is one file, standard library plus the locked packages). `fetch_bundle.py`, `bundle\` and the tests are install-time only.

If the server runs from a venv it already has, step 2 can target that venv instead, but check it doesn't already hold different versions of `numpy` or the other locked packages. A separate venv is cleaner.

## 2. Server code: the diff, in words

### The factory call

```python
# before
synth, sample_rate = piper_synth(model_path)                     # 22050

# after
from kokoro_backend import kokoro_synth, BundleError, SynthesisError, VOICE_NAME
synth, sample_rate = kokoro_synth(r"C:\AtlasVoice\kokoro", speed=0.95, threads=THREADS)   # 24000
```

* `synth(text)` has the Piper shape: a generator of 16-bit little-endian mono PCM `bytes`. It yields one piece per sentence (short sentences merged, very long ones split at commas), so the first piece arrives after the first sentence is rendered, not the whole reply.
* Empty or whitespace-only text yields nothing (no exception).
* `threads`: see the speed section of `README.md` for the measured best. On the 9700X, start with `THREADS = 6`, which leaves two cores for the rest of the desktop, then try 8 if it is otherwise idle. `None` lets ONNX Runtime take one thread per physical core.

### Sample rate: 24000, not 22050

Wherever the server builds Wyoming audio events, use the returned `sample_rate`; don't use a literal:

```python
AudioStart(rate=sample_rate, width=2, channels=1)
AudioChunk(rate=sample_rate, width=2, channels=1, audio=pcm)
```

Search the server for `22050` and for any arithmetic that converts bytes to seconds (`/ 44100`, `* 22050 * 2`). Each one becomes `sample_rate * 2` = **48,000 bytes per second**.

### The PCM cap per request

Kokoro Fable-mix at speed 0.95 averaged 0.067 s of audio per character of text over 38 Atlas lines, and at most 0.088 s per character (the shortest lines, where pauses dominate). A cap with headroom:

```python
max_pcm_bytes = 48_000 * (0.1 * len(text) + 1.0)    # 0.1 s per character + 1 s, at 48,000 bytes per second
```

If the server instead has a fixed cap in seconds, keep the seconds and recompute the bytes at 48,000 per second (a 60 s cap is 2,880,000 bytes, up from 2,646,000).

### The Wyoming voice and attribution

```python
TtsVoice(
    name=VOICE_NAME,                      # "en_GB-fablemix"
    description="Atlas Fable-mix (Kokoro-82M, British English)",
    languages=["en-GB"],
    attribution=Attribution(name="hexgrad (Kokoro-82M); Fable-mix voice pack by voice-scout",
                            url="https://huggingface.co/hexgrad/Kokoro-82M"),
    installed=True,
    version="kokoro-82m-v1.0+fablemix-1",
)
```

The Home Assistant voice selection then needs `en_GB-fablemix` picked once in the Assist pipeline.

### Startup checks

1. **Bundle check, fail closed.** `kokoro_synth()` itself reads every bundle file once, checks its sha256 against the constants in `kokoro_backend.BUNDLE`, and raises `BundleError` on any missing, truncated or altered file, or if the spaCy model isn't installed. Treat `BundleError` exactly like the server's existing startup-hash failure: don't serve the voice. Its message names the file and the hashes, never any text.
2. **Warm-up.** Right after loading, render a fixed phrase once and check it produced audio. The first call in a process is slower (see `README.md`, cold vs warm), and this keeps that cost out of the first real reply:
   ```python
   warm = b"".join(synth("Ready."))
   assert len(warm) > sample_rate // 2          # at least 0.25 s of audio
   ```
3. **Log** only the voice name, "bundle verified", and the load time.

The existing startup hash check of Piper's `.onnx` can be removed along with Piper, or left in place for rollback.

### Errors at request time

`synth()` raises `SynthesisError` for anything that goes wrong while rendering. Its message is only `synthesis failed: <ExceptionType>`, with no text or phonemes and no chained traceback, so it is safe to log. Handle it where the server handles a Piper failure today.

### Text

Keep the normaliser as it is: it already turns times, money and units into words, which is what Kokoro needs too. The backend applies the Kokoro-only fixes itself (see `PRONUNCIATION.md`). There are two rewrites: "a m"/"p m" → "AM"/"PM", and the "Wind Down" scene name. There are three lexicon entries: "timer", "ensuite" and "aircon". Atlas's wording is never changed. Two rules to keep in the normaliser:

* **Don't pass digits with colons** ("9:05"). misaki reads them as "nine: zero five". The normaliser already spells times out.
* Square brackets in a reply are turned into parentheses by the backend before G2P. That way misaki's inline phoneme syntax `[word](/phonemes/)` can only come from the backend's own reviewed table. Nothing for the normaliser to do; it's noted here so the reviewer knows.

### The process environment

* The backend sets `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `HF_DATASETS_OFFLINE` and `HF_HUB_DISABLE_TELEMETRY` to `1` in its own process, and turns off ONNX Runtime's telemetry events. No library in this stack downloads at runtime; these are belt and braces.
* **espeak-ng DLL copy.** For words misaki doesn't know, it falls back to espeak-ng through `phonemizer`. At load, `phonemizer` copies `espeak-ng.dll` from the `espeakng-loader` package into a fresh `tempfile.mkdtemp()` folder under `%TEMP%`, loads it from there and deletes it at exit. Give the server user a private `TEMP`, for example `set TEMP=C:\AtlasVoice\tmp` with an ACL for that user only, so no other account can plant a DLL there.
* **What touches sockets.** `urllib3` (imported by spaCy through `requests`) creates a socket and binds it to `::1` port 0 once at import to probe for IPv6. Nothing connects and nothing is sent. The isolation test records this and blocks every connect, DNS lookup, send and URL open. If the server's firewall rule is per-program, no outbound rule is needed for the voice.
* Memory: about 1.0 GB resident after load and 1.34 GB peak (measured on Linux; see `README.md` §7).

## 3. What does not change

* Wyoming protocol handling, admission and per-client limits.
* One synthesis at a time. The ONNX session isn't shared across threads, and `synth` is a plain generator, so keep the lock.
* The watchdog and the time cap per request. On the desktop a reply renders at about a tenth of real time (README), so existing caps sized for Piper (RTF ~0.04) still allow for long replies. A 600-character reply (about 40 s of speech) should render in about 5 s on the desktop.
* The rule that no text goes to logs. The backend prints and logs nothing.
* The text normaliser, apart from the optional rewrites in `PRONUNCIATION.md`.

## 4. Rollback

Keep `piper_synth` and its model. A config switch between the two factories is enough, because both return `(synth, sample_rate)` and the server now reads `sample_rate` instead of assuming 22050.
