# voice-scout: status

**Updated:** 2026-10-20 10:48 UTC | **elapsed:** 1 h 05 m
**Stage:** 2, shortlist screening (one line, L09 British vowels, per candidate), then full auditions.
**Findings so far** (sandbox 4 vCPU; UTMOS / median F0 / accent-classifier verdict):
- **Qwen3-TTS VoiceDesign 1.7B** (Apache-2.0): five text descriptions of a mature RP male gave UTMOS 4.27–4.42 and F0 84–117 Hz, but the accent classifier calls **all five American**. Useful as a timbre source, not as the voice.
- **Qwen3-TTS 0.6B Base, cloning the household's liked Chatterbox-on-Kokoro-bm_fable clip** (in-context mode): UTMOS **4.50**, England, 116 Hz. Mixing 50 % of a designed voice's speaker x-vector into the prompt: UTMOS 4.50, England, **103 Hz**. The best "evolve" lever so far. CPU RTF ~8 here (slow).
- **Chatterbox-Nano** (new, 110M, MIT) cloning the same clip: UTMOS 4.45, England, RTF **1.7 here** (likely ~real time or better on the 9700X).
- **KittenTTS 2** (new 1.7B ternary, Stellon community licence) cloning the same clip: UTMOS 4.41–4.44, British/Australian, but fast and sing-song (3.8 words/s, 6.5 st pitch spread). RTF ~10 here in PyTorch; there's a llama.cpp fork. All 19 of its built-in male voices score American.
- **Pocket TTS** built-ins (CC-BY-4.0 model, CC0 Voice-Zero LibriVox voices): `peter_yearsley` England, UTMOS 4.38, **92 Hz**, expressive; `stuart_bell` England, 4.37, 130 Hz. CPU-fast, Wyoming server exists. Note: these are real (consenting, CC0) LibriVox readers, not synthetic.
- **NeuTTS Air / Nano: NO DATA** (gated on Hugging Face; needs a token).
**Next:** x-vector grid for the Qwen-Fable evolution; Kokoro voice fitted to the evolved target; then full 10-line auditions of 5 voices.
**ETA:** auditions done ~15:00 UTC; report ~17:00 UTC.
**Blockers:** none.
