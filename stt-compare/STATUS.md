# stt-compare: STATUS

Stage 0 (21 Oct 2026): started. Branch `stt-compare` created from `atlas-current-input`.

Plan:
1. Test set: ~150 commands/questions (house names from `voice-lewis-small` corpus, owner phrasings), rendered with open AU/GB TTS voices; clean, room-noise and far-field versions.
2. Candidates on this sandbox CPU (4 vCPU Xeon 2.1 GHz, no GPU): faster-whisper int8 (small.en, medium.en, distil-large-v3, large-v3-turbo), whisper.cpp (CPU build; Vulkan speed estimated from published figures), Parakeet TDT (ONNX), Moonshine, Speech-to-Phrase.
3. Metrics: WER, command accuracy, RTF, latency after end of speech, RAM; vocabulary prompting on/off.
4. README verdict + Windows bench script.

Nothing is installed in the house. Synthetic voices and the owner's text phrasings only.
