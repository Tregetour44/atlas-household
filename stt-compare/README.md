# Atlas speech-to-text: local engines compared (DRAFT verdict, results still coming in)

**Draft verdict (21 Oct, interim):** run **Qwen3-ASR 0.6B (int4 ONNX) with a fixed house-name prompt, on the CPU**, served by
**wyoming-faster-whisper 3.8.1** (`--stt-library qwen3-asr --initial-prompt "<house names>"`). Fallback choice if the PC bench shows it
too slow: **Parakeet TDT 0.6B v2 int8** (same server, `--stt-library sherpa`). Both leave the GPU entirely to Gemma.

Interim numbers (80 commands x AU clean / GB clean / room noise = 240 synthetic clips, sandbox 4-vCPU Xeon):

| engine | command accuracy | house words heard right | latency per 2-5 s command here | est. on Ryzen 7 9700X | RAM |
|---|---|---|---|---|---|
| Qwen3-ASR 0.6B int4 + house prompt | 82.9% | 89.6% | 0.89 s | ~0.3-0.5 s | 1.7 GB |
| Qwen3-ASR 0.6B int4, no prompt | 73.8% | 72.2% | 0.78 s | ~0.3-0.4 s | 1.5 GB |
| Parakeet TDT 0.6B v2 int8 | 72.5% | 79.2% | 0.29 s | ~0.1-0.15 s | 1.0 GB |
| faster-whisper (small.en, distil-large-v3, large-v3-turbo), Speech-to-Phrase, whisper.cpp | pending | | | | |

Today's HA Cloud hearing stage is 2.5-4 s (owner's measurement); a local engine plus HA's default 0.7 s end-of-speech wait should
land near 1 s. HA Cloud accuracy on this test set: NO DATA (no access from the sandbox).

Bench for the PC: `bench/bench_pc.ps1`. Status: `STATUS.md`.
