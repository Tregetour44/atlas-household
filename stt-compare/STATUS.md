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

Stage 2 (21 Oct, ~04:50 UTC): budget cut received from PC Steward (ceiling ~US$15, was 30). Acknowledged here (this session cannot message other sessions).
- Already done before the cut: full test set (151 commands, 604 clips, committed); Parakeet TDT 0.6B v2/v3 int8 and Kroko streaming on all 604 clips.
- Remaining runs trimmed to 80 commands x (AU clean, GB clean, room noise) = 240 clips (`testset/audio/manifest_core.jsonl`): Qwen3-ASR 0.6B (with/without house prompt), faster-whisper small.en / large-v3-turbo (with/without prompt) / distil-large-v3 (int8, CPU), then Speech-to-Phrase v2.2 and whisper.cpp CPU (60 clips). Dropped: medium.en, base.en, far-field for those runs.
- Early leader: Parakeet TDT 0.6B v2 int8 on CPU (sherpa-onnx through wyoming-faster-whisper 3.8.1): 77% command accuracy on clean clips, 0.29 s p50 per 2-5 s command on this 4-vCPU Xeon.
- Pushed: `bench/bench_pc.ps1` (owner's PC bench) and a draft README verdict (to be refined).
Deployment gotchas found so far: faster-whisper 1.2.1 breaks with PyAV >= 17 (pin av==16.1.0); onnxruntime 1.31 rejects Qwen3-ASR's external weights when reached through the HF cache symlinks (use a plain model folder).

Stage 3 (21 Oct, ~07:10 UTC): FINAL. Recommendation is clear; stopping here (budget).
- Verdict: faster-whisper small.en int8 on the CPU + house-name initial prompt + --vad-filter, via wyoming-faster-whisper 3.8.1.
  84.6% command accuracy, 95.8% house words (240 clips), 0/9 inventions on noise-only audio, est. 0.5-1.1 s STT on the 9700X
  (hearing stage ~1.2-1.8 s vs 2.5-4 s today), 0 VRAM. Fast fallback: Parakeet TDT 0.6B v2 int8 (72.5%, est. 0.1-0.2 s).
- Rejected: Qwen3-ASR 0.6B + prompt (82.9%, fast) because it echoes its prompt on noise-only audio (9/9) and inserted "Good night"
  into TV babble; Speech-to-Phrase in front (wrong-action accepts 2.9-4.6%: drops "at <time>", fifteen -> fifty).
- whisper.cpp Vulkan turbo is the later GPU upgrade (published ~0.2 s on a 9070 XT; q5_0 accuracy = faster-whisper int8 turbo here).
- HA Cloud accuracy on this set: NO DATA (no account). GPU speed in the sandbox: NO DATA (published figures used).
- Next: owner runs bench/bench_pc.ps1 on the PC; local team deploys after the owner's yes.
