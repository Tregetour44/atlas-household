# voice-scout: status

**Updated:** 2026-10-20 11:55 UTC | **elapsed:** 2 h 10 m
**Stage:** 4, evolving the top two (Qwen-Fable, Kokoro fable-mix). Stage 3 auditions done (5 voices × 10 lines).
**Audition averages over the 10 lines** (sandbox 4 vCPU; UTMOS / median F0 / accent-classifier lines England-or-Australia vs US):

| voice | UTMOS | F0 | pitch spread | WER | British / US lines | RTF here |
|---|---|---|---|---|---|---|
| Qwen3-TTS 0.6B cloning the liked Chatterbox-Fable clip | 4.45 | 116 Hz | 4.0 st | 0.7 % | 10 / 0 | ~8.5 |
| Kokoro "fable-mix" (Fable prosody half; timbre half 50 % Fable + 50 % a pack fitted to the mature-Fable target) | 4.47 | 108 Hz | 5.5 st | 0 % | 8 / 2 | ~0.4 |
| KittenTTS 2 cloning the same clip | 4.44 | 119 Hz | 5.7 st (sing-song on short lines) | 1.3 % | 10 / 0 | ~10.5 |
| Pocket TTS `peter_yearsley` (CC0 LibriVox reader, built-in) | 4.32 | 94 Hz | 4.0 st | 0.7 % | 10 / 0 | to be measured |
| Chatterbox-Nano cloning the same clip | 4.43 | 125 Hz | 6.2 st | 3 % | 4 / 6 (drifts American) | ~1.7 |

**Deeper/mature lever that works:** lower the liked clip's pitch 3 semitones and its formants 5 % with the WORLD vocoder, then let Qwen clone it. Qwen cleans up the vocoder texture (UTMOS 3.8 → 4.45), F0 drops to ~95–100 Hz, and the accent stays English.
**Next:** evolved renders; KVoiceWalk for Kokoro; Qwen C-engine (int8) CPU timing; held-out house lines for the top 2; MP3s; README.
**ETA:** report ~16:00 UTC.
**Blockers:** none.
