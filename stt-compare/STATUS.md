# stt-compare: STATUS

Stage 0 (21 Oct 2026): started. Branch `stt-compare` created from `atlas-current-input`.

Plan:
1. Test set: ~150 commands/questions (house names from `voice-lewis-small` corpus, owner phrasings), rendered with open AU/GB TTS voices; clean, room-noise and far-field versions.
2. Candidates on this sandbox CPU (4 vCPU Xeon 2.1 GHz, no GPU): faster-whisper int8 (small.en, medium.en, distil-large-v3, large-v3-turbo), whisper.cpp (CPU build; Vulkan speed estimated from published figures), Parakeet TDT (ONNX), Moonshine, Speech-to-Phrase.
3. Metrics: WER, command accuracy, RTF, latency after end of speech, RAM; vocabulary prompting on/off.
4. README verdict + Windows bench script.

Nothing is installed in the house. Synthetic voices and the owner's text phrasings only.

Stage 1 (21 Oct): test set done.
- `testset/commands.jsonl`: 151 commands/questions (30 lights, 15 brightness, 20 timers, 8 scenes, 12 blinds, 22 energy, 12 climate, 10 status, 22 owner phrasings).
- `testset/audio/`: 604 clips, 27 min, 16 kHz FLAC: 302 clean (each command by one AU and one GB voice), 151 room noise (5-15 dB SNR), 151 far-field (simulated room, 2.5-5 m, RT60 0.35-0.8 s).
- Voices: Piper VCTK p326/p374/p225 + jenny_dioco with an approximate Australian vowel shift; Kokoro bm_george/bf_emma/bm_lewis/bf_isabella, Piper northern_english_male/cori/alan (British).
- Harness: candidates run through the real Wyoming server (`wyoming-faster-whisper` 3.8.1, which now also serves Parakeet, Qwen3-ASR and onnx-asr models).
Next: run the candidate matrix.
