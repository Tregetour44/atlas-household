# voice-scout: status

**Updated:** 2026-10-20 13:10 UTC | **elapsed:** 3 h 25 m
**Stage:** 5, done. Report in `README.md`; samples in `samples/`.
**Verdict:**
1. **Qwen3-TTS "Fable-mature"**: the liked Chatterbox-Fable clip lowered 3 st and re-cloned by Qwen3-TTS 0.6B. 99 Hz, British 10/10, UTMOS 4.43. Not real time on CPU (est. RTF 1.3–2.0 on the 9700X with the int8 C engine), so distil it into Piper on the `voice-lewis-small` recipe.
2. **Kokoro "Fable-mix"**: a new split-half Kokoro pack (`voices/kokoro-fablemix.pt`). 108 Hz, British 8/10, UTMOS 4.47. Live on CPU today (est. RTF 0.11–0.19) via Kokoro-FastAPI → wyoming_openai.
3. **Pocket TTS `peter_yearsley`** (CC0 LibriVox reader, not Fable): 94 Hz, British 10/10, UTMOS 4.32. Live on CPU (est. RTF 0.25–0.34); a Wyoming server exists.
Baseline: the live Piper `lewis_small` scores UTMOS 4.02 on the same lines.
**NO DATA:** NeuTTS Air/Nano and Pocket TTS cloning (gated on Hugging Face); speed on the actual 9700X (estimates only); listening (all judgements are proxies).
**Blockers:** none. Stopped because the shortlist is clear.
