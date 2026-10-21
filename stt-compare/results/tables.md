### Core comparison: 80 commands x (AU clean, GB clean, room noise) = 240 clips

| engine (CPU, int8 unless noted) | WER clean | WER noise | cmd clean AU | cmd clean GB | cmd noise | **cmd all** | house words | owner phrasings | latency p50 / p95 here | est. on 9700X | peak RAM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fw-large-v3-turbo-int8+prompt | 6.5% | 4.8% | 76.2% | 91.2% | 88.8% | **85.4%** | 90.3% | 83.3% | 4.60 / 5.16 s | 1.53-3.29 s | 2075 MB |
| fw-small.en-int8+prompt | 6.8% | 10.0% | 78.8% | 92.5% | 82.5% | **84.6%** | 95.8% | 78.8% | 1.60 / 1.87 s | 0.53-1.14 s | 914 MB |
| fw-small.en-int8+prompt-beam1-vadfilter | 6.8% | 11.4% | 78.8% | 91.2% | 81.2% | **83.8%** | 94.4% | 78.8% | 1.47 / 1.81 s | 0.49-1.05 s | 1289 MB |
| fw-small.en-int8+prompt-beam1 | 7.0% | 11.2% | 78.8% | 91.2% | 81.2% | **83.8%** | 94.4% | 78.8% | 1.76 / 1.92 s | 0.59-1.26 s | 1253 MB |
| qwen3asr-0.6b-int4+prompt | 7.1% | 8.4% | 71.2% | 93.8% | 83.8% | **82.9%** | 89.6% | 86.4% | 0.89 / 1.19 s | 0.30-0.63 s | 1721 MB |
| fw-large-v3-turbo-int8 | 6.8% | 6.2% | 68.8% | 95.0% | 83.8% | **82.5%** | 86.8% | 84.8% | 4.26 / 4.85 s | 1.42-3.05 s | 2075 MB |
| fw-small.en-int8 | 9.2% | 15.4% | 61.3% | 93.8% | 67.5% | **74.2%** | 81.2% | 78.8% | 1.50 / 1.82 s | 0.50-1.07 s | 787 MB |
| qwen3asr-0.6b-int4 | 10.6% | 9.2% | 52.5% | 92.5% | 76.2% | **73.8%** | 72.2% | 80.3% | 0.78 / 1.16 s | 0.26-0.56 s | 1503 MB |
| fw-distil-large-v3-int8 | 10.1% | 12.0% | 57.5% | 88.8% | 72.5% | **72.9%** | 77.1% | 72.7% | 4.45 / 5.01 s | 1.48-3.18 s | 1945 MB |
| parakeet-v2-int8 | 10.4% | 14.8% | 61.3% | 91.2% | 65.0% | **72.5%** | 79.2% | 74.2% | 0.29 / 0.40 s | 0.10-0.20 s | 981 MB |
| parakeet-v3-int8 | 9.5% | 20.4% | 60.0% | 92.5% | 65.0% | **72.5%** | 75.0% | 81.8% | 0.37 / 0.73 s | 0.12-0.26 s | 1031 MB |
| kroko-streaming | 13.8% | 15.2% | 48.8% | 85.0% | 63.7% | **65.8%** | 74.3% | 77.3% | 0.32 / 0.61 s | 0.11-0.23 s | 276 MB |
| speech-to-phrase-tuned | 48.1% | 47.5% | 51.2% | 58.8% | 58.8% | **56.2%** | 63.2% | 28.8% | 0.95 / 1.81 s | 0.32-0.68 s | 981 MB |
| speech-to-phrase-default | 76.0% | 74.5% | 30.0% | 27.5% | 27.5% | **28.3%** | 29.2% | 24.2% | 0.43 / 0.94 s | 0.14-0.31 s | 982 MB |

### All 604 clips incl. far-field (engines that ran on everything)

| engine | WER clean | WER noise | WER far-field | cmd clean | cmd noise | cmd far-field | cmd all (604 clips) |
|---|---|---|---|---|---|---|---|
| kroko-streaming | 13.6% | 19.0% | 29.9% | 66.9% | 57.6% | 42.4% | 58.4% |
| parakeet-v2-int8 | 9.3% | 17.6% | 21.1% | 77.2% | 60.9% | 56.3% | 67.9% |
| parakeet-v3-int8 | 9.1% | 19.6% | 28.8% | 75.5% | 62.9% | 47.0% | 65.2% |

### Vocabulary prompting (house names as initial prompt / Qwen3-ASR context)

| engine | cmd all: no prompt -> house prompt | house words | WER clean | WER noise |
|---|---|---|---|---|
| fw-large-v3-turbo-int8 | 82.5% -> 85.4% | 86.8% -> 90.3% | 6.8% -> 6.5% | 6.2% -> 4.8% |
| fw-small.en-int8 | 74.2% -> 84.6% | 81.2% -> 95.8% | 9.2% -> 6.8% | 15.4% -> 10.0% |
| qwen3asr-0.6b-int4 | 73.8% -> 82.9% | 72.2% -> 89.6% | 10.6% -> 7.1% | 9.2% -> 8.4% |

### Accent control: AU speakers with and without the approximate vowel shift (clean)

| engine | cmd acc: AU voices, vowel-shifted | cmd acc: same AU voices, no shift | cmd acc: GB voices | WER shifted / unshifted |
|---|---|---|---|---|
| parakeet-v2-int8 (151 clips) | 60.9% | 74.2% | 93.4% | 15.0% / 9.6% |
| qwen3asr-0.6b-int4+prompt (80 clips) | 71.2% | 80.0% | 93.8% | 11.8% / 8.2% |

### whisper.cpp vs the others on the 60-clip PC subset (sandbox CPU)

| engine (sandbox CPU, 4 threads) | cmd acc (60 clips) | WER | latency p50 / p95 | peak RAM |
|---|---|---|---|---|
| kroko-streaming | 46.7% | 23.6% | 0.31 / 0.67 s | 276 MB |
| parakeet-v2-int8 | 58.3% | 18.4% | 0.28 / 0.35 s | 981 MB |
| parakeet-v3-int8 | 58.3% | 24.2% | 0.37 / 0.71 s | 1031 MB |
| wcpp-turbo-q5_0-cpu | 70.0% | 10.9% | 25.60 / 27.34 s | 1050 MB |

### Speech-to-Phrase v2.2 on the core 240 clips

| grammar | accepted | accepted & right | **accepted & wrong (wrong action)** | rejected -> fallback | S2P latency p50 here | S2P alone cmd acc | front + fallback: cmd acc (fallback engine alone) |
|---|---|---|---|---|---|---|---|
| default (450 templates) | 31.2% | 28.3% | **2.9%** | 68.8% | 0.34 s | 28.3% | fw-small.en-int8+prompt: 87.9% (84.6%); parakeet-v2-int8: 78.3% (72.5%); qwen3asr-0.6b-int4+prompt: 86.7% (82.9%); fw-large-v3-turbo-int8: 86.2% (82.5%) |
| tuned (236 templates) | 60.8% | 56.2% | **4.6%** | 39.2% | 0.75 s | 56.2% | fw-small.en-int8+prompt: 88.8% (84.6%); parakeet-v2-int8: 85.0% (72.5%); qwen3asr-0.6b-int4+prompt: 89.6% (82.9%); fw-large-v3-turbo-int8: 88.3% (82.5%) |

### No speech: noise-only clips (does a name prompt make the engine invent a command?)

| engine | fan / hum / kitchen noise (9 clips): any text | ... with a house word or command | TV babble (3 clips): any text | example outputs |
|---|---|---|---|---|
| fw-large-v3-turbo-int8+prompt | 9/9 | 0/9 | 3/3 | " Oh, how is the home?"; " Thank you."; " What timers do I have?"; " What's the weather like tomorrow?" |
| fw-small.en-int8+prompt-beam1-vadfilter | 0/9 | 0/9 | 3/3 | " How is the home?"; " What time is it do I have?"; " What's the weather like tomorrow?" |
| fw-small.en-int8+prompt-beam1 | 0/9 | 0/9 | 3/3 | " How is the home?"; " What time is it do I have?"; " What's the weather like tomorrow?" |
| fw-small.en-int8+prompt-vadfilter | 0/9 | 0/9 | 3/3 | " How is the home?"; " What time is it do I have?"; " What's the weather like tomorrow?" |
| fw-small.en-int8+prompt | 1/9 | 0/9 | 3/3 | " How is the home?"; " This is the end of this video, thank you so much for watching, if you enjoyed this video, please like, comment and subscribe, thanks for watching, see you next time."; " What time is it do I have?"; " What's the weather like tomorrow?" |
| fw-small.en-int8 | 6/9 | 0/9 | 3/3 | " How is the home?"; " What time is it do I have?"; " What's the weather like tomorrow?"; " You" |
| parakeet-v2-int8 | 0/9 | 0/9 | 3/3 | "Time do that."; "What timers do I have?"; "What's the weather like tomorrow?" |
| qwen3asr-0.6b-int4+prompt | 9/9 | 9/9 | 3/3 | "Atlas, Good Night, Wind Down, ZeroCharge, kWh, atrium, pergola, ensuite, loft, laundry, porch, patio, study, garage, hallway, kitchen, dining room, living room, guest bedroom, master bedroom, upstairs, downstairs, ground floor, outside, atrium blind, living room door blind, living room window blind, atrium spotlight, pergola floodlight, pergola spotlight, ensuite downlight, robe downlight, loft lamp, laundry downlight, kitchen chandelier, living room chandelier, range hood, fountain spotlight, mirror ambiance, wall floodlight, wall light, garden spotlight, garage ceiling, porch downlight."; "How is the home?"; "What timers do I have?"; "What's the weather like tomorrow? One p.m." |
| qwen3asr-0.6b-int4+vocabprompt | 9/9 | 9/9 | 3/3 | "Atlas, Good Night, Wind Down, ZeroCharge, kWh, atrium, pergola, ensuite, loft, laundry, porch, patio, study, garage, hallway, kitchen, dining room, living room, guest bedroom, master bedroom, upstairs, downstairs, ground floor, outside, atrium blind, living room door blind, living room window blind, atrium spotlight, pergola floodlight, pergola spotlight, ensuite downlight, robe downlight, loft lamp, laundry downlight, kitchen chandelier, living room chandelier, range hood, fountain spotlight, mirror ambiance, wall floodlight, wall light, garden spotlight, garage ceiling, porch downlight."; "How is the home?"; "Vocabulary: Atlas, Good Night, Wind Down, ZeroCharge, kWh, atrium, pergola, ensuite, loft, laundry, porch, patio, study, garage, hallway, kitchen, dining room, living room, guest bedroom, master bedroom, upstairs, downstairs, ground floor, outside, atrium blind, living room door blind, living room window blind, atrium spotlight, pergola floodlight, pergola spotlight, ensuite downlight, robe downlight, loft lamp, laundry downlight, kitchen chandelier, living room chandelier, range hood, fountain spotlight, mirror ambiance, wall floodlight, wall light, garden spotlight, garage ceiling, porch downlight."; "What timers do I have?" |
