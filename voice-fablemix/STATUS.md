# voice-fablemix: status

**Updated:** 2026-10-20 16:45 UTC | **elapsed:** 2 h 30 m
**Stage:** 5–7, weak spots done in the backend; final scoring and speed/RAM benchmarks running.
**Engine: ONNX Runtime 1.31 + onnx-community Kokoro-82M v1.0 fp32 ONNX, fed misaki's British phonemes** (parity with PyTorch Kokoro and the scout's renders shown on 38 lines; numbers in `eval/` to follow).
**Weak spots, fixed in `kokoro_backend.py`:**
- Short lines sound sing-song: a short-reply pack (same timbre; prosody half 50 % bm_fable + 50 % the fitted mature pack) with a style floor of 40 phonemes, fading to the normal pack by 60. On 19 short lines: F0 spread 5.70 → 3.95 st, p10–p90 range 15.9 → 10.5 st, median F0 unchanged (116 Hz), UTMOS 4.349 → 4.388, British 15/19 → 17/20. bm_george's prosody (the scout's idea) also flattened it but raised F0 by 17 Hz, so it was dropped.
- "Timer set:" heard as "Time a set" on 4 of 8 lines → "Timer's set" (0 of 8; "I've set a timer" also 0 of 8).
- misaki reads "a m" as "uh em" and drops the full stop after "p m." → AM / PM.
- "Wind Down" (as a name, "wɪnd") → phoneme override; "ensuite" ("ɛnsˈuːt") → lexicon "ɒnswˈiːt".
- Joins: Kokoro pads each piece with ~0.27 s + ~0.3 s of silence; trimmed, with pauses set by punctuation (0.3 s after a sentence, 0.15 s after a comma), so "Done: X. Checked." gets real pauses. Punctuation-only input no longer renders a click.
**Bad variants found:** fp16 ONNX gives all-NaN audio on 8 of 38 lines on CPU; int8 changes timing and isn't faster.
**Next:** final scores, benchmarks on an idle CPU, MP3 samples, README.
**Blockers:** none.
