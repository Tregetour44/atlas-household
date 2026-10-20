# Ready-made open voices: audition (no training)

Target: a mature, slightly deeper British male with Fable's accent, natural and warm, not youthful. All of these are built-in voices, voice packs or weighted blends. No reference cloning was used.

Each voice says the 4 sample lines (`-S1`…`-S4`) and the 10 audition lines (`-L01`…`-L10`, text in `../corpus/audition/audition_lines.txt`). `-joined-L01-L10.mp3` has all ten lines with 0.5 s gaps. The MP3s are mono, 96 kbps and loudness-matched to −18 LUFS.

**Scores (median F0, UTMOS, accent, WER, CPU RTF) and a top 3 will be added here once the deeper-Fable renders finish**; the CPU is busy with them now.

| Family | Voices | Licence |
|---|---|---|
| Kokoro-82M v1.0 (`hexgrad/Kokoro-82M` @ `f3ff3571`), speed 0.95 | `bm_fable`, `bm_george`, `bm_daniel`; blends fable/george 70/30 and 50/50, fable/daniel 70/30, fable/lewis 70/30 (weighted sums of the built-in style vectors) | Apache-2.0 |
| Piper (piper-tts 1.8) en_GB medium | `alan`; `northern_english_male`; `vctk` speakers p226, p232, p243, p254, p258, p274 (VCTK's southern/RP-ish English male speakers) | alan: Mimic 3 voice, licence unclear; northern_english_male: CC BY-SA 4.0 data; VCTK: CC BY 4.0 data (that checkpoint was fine-tuned from lessac) |
| Pocket TTS 3.3 (Kyutai) catalog voices | `charles` (VCTK p254), `paul` (VCTK p259), `javert` and `marius` (CC0 voice donations) | model CC BY 4.0; voices CC BY 4.0 / CC0 |
| XTTS-v2 (coqui-tts 0.27) built-in studio speakers | `Marcos Rudaski`, `Wulf Carlevaro` | Coqui Public Model License: **non-commercial only** |

Not rendered:
- **MeloTTS EN-BR.** Its British English speaker is female.
