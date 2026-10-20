# Timing (L06, 8.5–10.6 s of audio, after a warm-up render, nothing else running; 4-vCPU Xeon @ 2.8 GHz sandbox)

| engine | 4 threads: s / RTF | 2 threads: s / RTF | 2→4 gain | est. 9700X RTF |
|---|---|---|---|---|
| Qwen3-TTS 0.6B Base, PyTorch fp32 (qwen-tts) | 74.2 s / 8.13 | 109.3 s / 11.99 | 1.47 | 2.5–4.2 |
| Qwen3-TTS 0.6B Base, C engine int8 (generation only*) | 27.6 s / 3.52 | 32.8 s / 4.18 | 1.19 | 1.3–2.0 |
| KittenTTS 2, PyTorch (packed weights, default decoder) | 86.4 s / 10.0 | 140.1 s / 15.7 | 1.57 | 2.9–5.0 |
| Chatterbox-Nano | 17.3 s / 1.62 | 23.5 s / 2.21 | 1.36 | 0.54–0.87 |
| Pocket TTS (english, built-in voice) | 7.5 s / 0.83 | 5.0 s / 0.55 | (2 threads best) | 0.25–0.34 |
| Kokoro-82M (PyTorch) | 4.3 s / 0.41 | 7.6 s / 0.72 | 1.76 | 0.11–0.19 |

\* talker + code predictor + speech decoder from the engine's own log; each CLI call also spent ~60 s encoding the
reference clip (a server caches this once per voice). See `qwen_c_breakdown.txt`.

Estimate: 9700X RTF = RTF(4 thr) ÷ (per-core factor 1.6–2.2) ÷ (4→8-core gain between √gain(2→4) and gain(2→4)).
These are not measurements on the desktop.
