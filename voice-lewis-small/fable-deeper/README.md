# Fable, a bit deeper: teacher samples

The same teacher recipe as Lewis is used throughout: Chatterbox 0.1.7, exaggeration 0.4, cfg_weight 0.4, other settings default, and `torch.manual_seed(7)` before every line. Only the 10-second reference clip changes. The starting reference is the synthetic Kokoro `bm_fable` clip, `voice-samples/refs/kokoro-bm_fable.wav` (sha256 `e50c03e6…6fd47`, verified). No human voice is involved.

Each voice says the 4 sample lines (`-S1`…`-S4`) and the owner's 10 audition lines (`-L01`…`-L10`). `-joined-L01-L10.mp3` has all ten lines with 0.5 s gaps. The MP3s are mono, 96 kbps and loudness-matched to −18 LUFS. The deepened reference clips are in `refs/` (FLAC).

**I could not listen to any of this; the numbers below are proxies. Pick by ear.**

## What was done

| File prefix | Reference clip | How it was made (ffmpeg `rubberband` filter, `window=long`) |
|---|---|---|
| `fable-normal` | original bm_fable | unchanged. This re-render matches the earlier `voice-samples` Fable (median F0 115.5 vs 115.7 Hz) |
| `fable-minus1st` | −1 semitone | `pitch=0.9439:formant=preserved` |
| `fable-minus2st` | −2 st | `pitch=0.8909:formant=preserved` |
| `fable-minus3st` | −3 st | `pitch=0.8409:formant=preserved` |
| `fable-minus4st` | −4 st (optional) | `pitch=0.7937:formant=preserved` |
| `fable-minus2st-mature` | −2 st pitch, **formants ~4% lower** | `pitch=0.9604:formant=shifted` (pitch and formants −0.7 st), then `pitch=0.9278:formant=preserved` (pitch −1.3 st more) |
| `fable-formants-minus6pct` | pitch unchanged, **formants 6% lower** ("bigger vocal tract") | formants down 1.07 st, then pitch back up 1.07 st with formants preserved |
| `fable-formants-minus10pct` | pitch unchanged, formants 10% lower | the same with 1.82 st |
| `fable-normal-postshift-minus2st` | (crude comparison) normal Fable *output* pitch-shifted −2 st afterwards | `pitch=0.8909:formant=preserved` on the rendered audio |

## Measurements

The first F0 column covers the 4 sample lines only, for a like-for-like comparison with Lewis. On those lines the owner's chosen Lewis samples measure **115.3 Hz** and normal Fable **115.5 Hz**: they have the *same* median pitch. (Lewis's "99 Hz" in the round-1 README is from a different set of lines.)

The other columns cover all 14 lines:
- **UTMOS:** predicted naturalness, 1–5.
- **WER:** Whisper small.en.
- **sim → Fable:** ECAPA cosine to the original bm_fable reference. Normal Fable scores 0.81; another voice scores below 0.3.
- **England − US:** CommonAccent ECAPA score; higher means more English.

| Voice | F0, 4 sample lines | F0, all 14 lines | UTMOS | WER | sim → Fable | England − US |
|---|---|---|---|---|---|---|
| Lewis teacher (for reference) | 115.3 Hz | — | — | — | — | — |
| **fable-normal** | 115.5 Hz | 106.6 Hz | **4.36** | 1.8% | **0.81** | 0.28 |
| fable-minus1st | 104.5 Hz | 110.0 Hz | 4.34 | 10.3% * | 0.66 | 0.20 |
| fable-minus2st | 110.7 Hz | 104.0 Hz | 4.23 | 6.0% * | 0.47 | 0.30 |
| fable-minus3st | **97.1 Hz** | **95.3 Hz** | 4.11 | 0.5% | 0.28 | 0.30 |
| fable-minus4st | 91.2 Hz | 90.9 Hz | 3.91 | 0.3% | 0.20 | 0.22 |
| fable-minus2st-mature | 112.0 Hz | 104.6 Hz | 4.20 | 6.4% * | 0.48 | 0.36 |
| fable-formants-minus6pct | 122.8 Hz | 118.6 Hz | 4.35 | 3.6% | 0.78 | **0.38** |
| fable-formants-minus10pct | 115.4 Hz | 116.9 Hz | 4.21 | 5.4% | 0.64 | 0.33 |
| fable-normal-postshift-minus2st | 102.9 Hz | 100.7 Hz | 2.89 | 5.8% | 0.45 | 0.20 |

\* The higher WERs are Whisper slips on otherwise correct speech: "dry" for "dryer", "I take" for "I'd take", and "Dumb" for "Done" (a known Chatterbox habit, also heard in the Lewis samples).

## What the numbers say

- **Chatterbox only partly follows a deeper reference.** At −1 and −2 st the output is barely lower over the 14 lines (−1.4 and −0.9 st). −3 st is the first step that is clearly deeper: −1.9 st on all lines, about −3 st on the sample lines.
- **The cost of depth is identity.** Similarity to Fable falls quickly (0.81 → 0.66 → 0.47 → 0.28), and naturalness eases down (4.36 → 4.11 at −3 st). By −3 and −4 st it is measurably a different speaker, though still English-accented.
- **Lowering formants alone keeps Fable** (similarity 0.78 at −6%, the best English-accent score of all, UTMOS 4.35), **but Chatterbox then raises the pitch** (+1–2 st). It may sound "bigger" or older in timbre rather than lower.
- **The crude post-shift sounds processed** (UTMOS 2.89). It's included only for comparison and isn't recommended.
- The "youthful" quality seems to be timbre and delivery more than pitch, since Fable and Lewis share the same median F0.

## Suggested listening order

1. `fable-minus2st-mature`: modest depth plus slightly older timbre; still accented, about halfway between Fable and a new voice.
2. `fable-minus3st`: the first clearly deeper variant; most natural of the deep ones; drifts furthest from Fable that is still acceptable.
3. `fable-formants-minus6pct`: Fable's identity and accent intact with a fuller timbre, but not lower in pitch.

Then `fable-normal` for comparison. If one of these is right, round 2 distils it with the same recipe as Lewis: corpus, filters, house lines and held-out names, then the student.
