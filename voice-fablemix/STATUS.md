# voice-fablemix: status

**Updated:** 2026-10-20 16:20 UTC | **elapsed:** 2 h 05 m
**Stage:** 7–9 done (benchmarks, samples); final per-line scoring running; README and eval report next.
**Engine: ONNX Runtime 1.31 + onnx-community Kokoro-82M v1.0 fp32, misaki British G2P.** Parity with PyTorch Kokoro (which reproduces the scout's clips) shown on 38 lines.
**Speed here (4 vCPU Xeon 2.1 GHz, 4 threads, warm):** first audio 0.54 s (3 words), 1.08 s (15 words), 1.34 s (40 words); RTF 0.23; load 3.0 s; RSS 0.97 GB after load, 1.34 GB peak. Cold first call 1.25 s (15 words). PyTorch Kokoro on the same box: 1.36 s, RTF 0.27, load 5.9 s, peak 1.58 GB.
**Desktop estimate (scaled, NO DATA from the 9700X itself):** first audio ~0.3–0.55 s for 15 words; RTF ~0.07–0.12.
**Fixed in the backend:** short-reply prosody (flatter pack + style floor), real pauses between sentences (Kokoro adds none inside one inference), one-word sentences merged (alone they get a spurious "It's"/"I'm"), "timer" (lexicon, fixes "Timer set:" 8/8 and "Timer cancelled."), "a m"/"p m" → AM/PM, "Wind Down", "ensuite", "aircon", lexicon entries now also apply when capitalised.
**Samples:** `samples/` (audition lines, house lines, joined files) and `samples/fixes/` (14 before/after pairs), two-pass loudness-matched to −18 LUFS.
**Blockers:** none.
