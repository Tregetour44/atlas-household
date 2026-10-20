# Pronunciation fixes for Kokoro Fable-mix

Every fix below is already applied inside `kokoro_backend.py`, so **the normaliser needs no change** to get them. Fixes written in misaki's phoneme alphabet stay in the backend on purpose. That way the normaliser never has to emit phoneme syntax, and the reply text can't inject phonemes (the backend turns square brackets into parentheses before G2P). The "normaliser alternative" column is for a team that would rather keep these rules with the normaliser's other rules.

Evidence is Whisper small.en's transcript of the rendered audio, plus misaki's phonemes. "Before" is Kokoro Fable-mix as the scout ran it. Samples are in `samples/fixes/<name>-<line>-before.mp3` and `-after.mp3`, loudness-matched.

| # | Text | Problem (before) | Fix in the backend | After | Normaliser alternative | Samples |
|---|---|---|---|---|---|---|
| 1 | "Timer set: …", "Timer cancelled.", any "timer" | misaki `tˈImə`; the final schwa sounds like a separate word. Whisper heard "**Time a set**" on 4 of 8 "Timer set:" lines and "**Time are** cancelled" | `LEXICON["timer"] = "tˈImˌə"` (same vowels, a secondary stress holds the schwa inside the word) | "Timer set" 8 of 8, "Timer cancelled." correct; the wording is unchanged | Rewrite `Timer set:` → `Timer's set:` (also 0 of 8 misheard) or `I've set a timer:` (0 of 8) | `timer-H03`, `timer-F01` |
| 2 | "seven a m", "six forty-five a m tomorrow" | misaki reads the article: `ɐ ˈɛm`, "**uh em**" | `REWRITES`: `a m` / `a.m.` / `p m` / `p.m.` → `AM` / `PM` (`ˌAˈɛm`, `pˌiːˈɛm`) | "AM" read as letters | Emit `AM` / `PM` (capitals, no spaces or dots) instead of `a m` / `p m` | `ampm-F02` |
| 3 | "… eleven p m. Everything's off." | misaki drops the full stop after `p m.` and `p.m.`, so the sentence ran on into the next with no falling end | Same rewrite, plus the backend restores a closing `.`/`!`/`?` that misaki dropped | Sentence ends, then a 0.3 s pause | As 2 | `pmstop-W09` |
| 4 | "Wind Down" (the scene) | As a name (`NNP`) misaki says `wˈɪnd`, the breeze ("Shall I run Wind Down now?") | `REWRITES`: `wind down` → `[Wind](/wˈInd/) Down` | `wˈInd dˌWn`; Whisper writes "wind down" (and "Wine Down" when the two d's merge, which is normal speech) | None needed | `winddown-W02` |
| 5 | "ensuite" | misaki `ɛnsˈuːt`; Whisper heard "**N-suit**", "ensuit" | `LEXICON["ensuite"] = "ɒnswˈiːt"` (British "on-SWEET") | "on-suite" / "ensuite" | Write "en suite" (misaki then says `ˈɛn swˈiːt`, "en sweet": closer, but the backend's `ɒn` is the usual British vowel) | `ensuite-H04` |
| 6 | "aircon" | misaki `ˈAəkən`; Whisper heard "**ayakin**" | `LEXICON["aircon"] = "ˈɛːkɒn"` | "aircon" | Write "air-con" (misaki `ˌɛːkˈɒn`) | `aircon-A12` |
| 7 | Capitalised words | misaki keeps separate lexicon entries for "Ensuite" and "ensuite", so a fix for one silently missed the other | The backend writes both forms | Fixes apply at the start of a sentence too | — | — |
| 8 | "9:05", "7:30am" (digits with a colon) | misaki: `nˈIn:zˈiəɹQ fˈIv`, "nine: zero five" | None; the normaliser already spells times out | — | **Keep** spelling times out ("nine oh five p m"); never pass `H:MM` | — |

## Checked and fine as they are

misaki British, read by Whisper on the house lines (`samples/fablemix-H*.mp3`, `-W*.mp3`):

| Word | misaki phonemes | Whisper heard |
|---|---|---|
| Good Night (scene) | `ɡˈʊd nˈIt` | "Good night" |
| pergola | `pˈɜːɡələ` | "Pergola" |
| atrium | `ˈAtɹɪəm` | "Atrium" |
| kilowatt hours | `kˈɪləwɒt ˈWəz` | "kilowatt hours" |
| ZeroCharge | `zˌɪəɹQʧˈɑːʤ` (stress on "charge") | "Zero charge". If the household says "ZERO-charge", add `LEXICON["ZeroCharge"] = "zˈɪəɹQʧˌɑːʤ"` (keyed in that exact casing; checked) |
| ambiance | `ˈambiəns` | "ambience" (same sound in British English) |
| chandelier | `ʃˌandəlˈɪə` | "chandelier" |
| Robe Downlight | `ɹˈQb dˈWnlIt` | "robe downlight" |
| floodlight | `flˈʌdlIt` | "floodlight" |
| theatrical | `θɪˈatɹɪkᵊl` | "theatrical" |
| garage | `ɡˈaɹɑːʤ` (British) | "garage" |
| "Close the atrium blind?" | `klˈQz` (the verb) | "Close" |

## Not pronunciation, but fixed in the same pass

* **Short replies sound sing-song.** A flatter short-reply pack plus a style floor. See `README.md`, "Short lines".
* **"Done: X. Checked." ran together.** Kokoro leaves no silence (none over 80 ms) at a full stop inside one inference. The backend now renders each sentence separately, trims Kokoro's own padding, and inserts 0.3 s after a sentence and 0.15–0.25 s after a clause. A one-word sentence ("Checked.", "Done.") still rides with its neighbour, because alone it gets a spurious onset ("I'm checked", "It's done"). So "Done: Fountain Spotlight on. Checked." keeps a short pause before "Checked.", while "Good morning. Coffee weather, I'd say." gets a full one. Samples: `pauses-L05`, `pauses-A07`.
* **A one-word reply on its own** ("Done.") renders from a longer style row (80) of the short pack. Whisper then hears "Done." instead of "It's done.", but its naturalness score is low (UTMOS 3.1): Kokoro is weak on single words. If Atlas ever replies with one word, "All done." or "Done, then." will sound better. Sample: `oneword-F05`.
* **Punctuation-only text** ("...") used to render a breath or click; it now yields nothing.
