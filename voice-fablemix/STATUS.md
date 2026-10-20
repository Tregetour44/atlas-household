# voice-fablemix: status

**Updated:** 2026-10-20 15:00 UTC | **elapsed:** 0 h 45 m
**Stage:** 1, engine comparison (in progress).
- Kokoro PyTorch (kokoro 0.9.4, misaki 0.9.4 `lang_code="b"`) reproduces the scout's Fable-mix render (L01: UTMOS 4.415 vs the scout's 4.413, ECAPA similarity to the scout's clip 0.992).
- ONNX route under test: onnx-community `Kokoro-82M-v1.0-ONNX` (fp32 / fp16 / int8) in onnxruntime 1.31, fed the **same misaki British phonemes** (not kokoro-onnx's espeak G2P). Its graph has no random operators, so it is deterministic.
- Windows lock drafted for the ONNX route: 75 wheels, 93.4 MiB, every hash from PyPI's JSON, and `pip download --platform win_amd64 --python-version 3.12 --only-binary :all: --no-deps --require-hashes` fetched and verified all 75. One wheel (spaCy's `en_core_web_sm` 3.8.0) is not on PyPI; it is pinned by URL + sha256 to spaCy's GitHub release. `docopt` (sdist-only) is left out: only num2words' CLI script uses it.
**Next:** parity scores on 38 lines, then the backend, tests and weak spots.
**Blockers:** none.
