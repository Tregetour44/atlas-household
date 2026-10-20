# voice-fablemix: status

**Updated:** 2026-10-20 15:55 UTC | **elapsed:** 1 h 40 m
**Stage:** 2–5, backend, tests and weak spots (in progress).
**Engine (provisional): ONNX Runtime 1.31 + onnx-community Kokoro-82M v1.0 fp32 ONNX, fed misaki's British phonemes.**
- Parity with PyTorch Kokoro (which reproduces the scout's renders) on 38 lines (10 audition, 8 house, 20 Atlas shapes): UTMOS 4.472 / 4.451 / 4.456 vs PyTorch 4.472 / 4.464 / 4.459; median F0, F0 spread, WER, accent and ECAPA similarity all within PyTorch's own seed-to-seed spread.
- The ONNX export is a constant +3.4 dB louder than PyTorch (peaks to 0.985); the backend scales by 0.678 to match.
- **fp16 ONNX is unusable on CPU**: all-NaN audio on 8 of 38 lines. **int8** changes durations and is not faster. fp32 only.
- Windows lock (ONNX route): 75 wheels, 93.4 MiB, hashes from PyPI JSON, verified by `pip download --platform win_amd64 --require-hashes --no-deps --only-binary :all:`.
**Found so far:** misaki reads the normaliser's "a m" as "uh em" and drops the full stop after "p m."/"p.m." (fixed in the backend: AM/PM); "Wind Down" as a name becomes "wɪnd" (fixed: phoneme override); "ensuite" → "ɛnsˈuːt" (fixed: lexicon "ɒnswˈiːt"); punctuation-only text rendered a click (fixed: skipped).
**Next:** short-line and "Timer set" scores, speed/RAM benchmarks on an idle CPU, samples, INTEGRATION.md, README.
**Blockers:** none.
