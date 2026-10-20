# voice-fablemix: status

**Updated:** 2026-10-20 16:25 UTC | **elapsed:** 2 h 10 m
**Stage:** done. Report in `README.md` (verdict first); integration in `INTEGRATION.md`; fix list in `PRONUNCIATION.md`; per-line numbers in `eval/README.md`; samples in `samples/`.
**Verdict:** ready to deploy, after a 5-minute speed check on the desktop (`eval/bench.py`) and a listen.
- **Engine:** ONNX Runtime 1.31 + onnx-community Kokoro-82M v1.0 fp32 ONNX, fed misaki British phonemes; parity with PyTorch Kokoro / the scout's clips shown on 38 lines. fp16 (NaN audio) and int8 (changed timing) rejected.
- **First audio:** 1.08 s here for 15 words (4 vCPU Xeon 2.1 GHz); estimated 0.3–0.55 s on the 9700X. RTF 0.23 here, est. 0.07–0.12 there.
- **RAM:** 0.97 GB after load, 1.34 GB peak. Load 3.0 s.
- **Install:** 75 hash-pinned win_amd64 wheels (93.4 MiB), verified with `pip download --require-hashes`; 311 MiB model bundle via `fetch_bundle.py`. No admin rights, no system espeak, no Docker, no runtime network.
- **Fixed:** short-reply sing-song (F0 range −32 %, UTMOS +0.04), real pauses between sentences, "Timer" (0/8 misheard, wording unchanged), AM/PM, Wind Down, ensuite, aircon, capitalised lexicon entries, one-word pieces, punctuation-only clicks, the export's +3.4 dB.
- **Tests:** 17 offline tests pass (54 s), including hash-mismatch fail-closed and an audit-hook proof of no network.
**Left / NO DATA:** desktop speed, thread count and Windows working set (estimates only); the Windows install itself; listening; one-word replies are weak in Kokoro; no pause before a one-word closing sentence ("…on. Checked.").
**Blockers:** none.
