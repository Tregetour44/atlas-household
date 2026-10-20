# Directive: Atlas energy advice must be reasoned from history, forecast and trends, not fixed lines (House AI leads; HA builds; Energy reviews) (18 Oct 2026, 22:25 by the system clock)

- **From:** PC Steward. **To:** House AI (prompt and benchmark), HA (fact cards, apply), Energy (read-only review of advice correctness).
- **Asked (PC Steward, 22:2x):** whether Atlas may end energy answers with one of four fixed time-of-day lines (fact-cards.mjs:50–53: start a big load now in 11–14; wait for 11:00 before; paid until tomorrow 14–18 and avoid 6–8 pm; avoid big loads until 8 pm in 18–20).
- **the owner's words (verbatim, 22:2x):** "no thats way too black and white - it should consider history, forecast, trends etc.. it can give advice on this basis but it has to be better than what you've proposed"

## Scope

1. **The four fixed conclusion lines are rejected.** They don't go live.
2. Atlas **may** give energy advice (for example when to run big loads, the evening credit, the battery), but it must be **reasoned from the readings**: battery level and the trend through the day, solar so far and the forecast for the rest of the day and tomorrow, recent history (similar days, typical evening use, past credit evenings), the free window and the evening credit rules, and the size of the load if known. It says what it's basing the advice on, briefly, and says plainly when the data is missing or uncertain. The house rules stay as facts, not a script.
3. House AI designs it (facts Atlas needs, prompt guidance) and benchmarks it on Codex 42's energy questions plus new cases where the fixed lines would be wrong (for example a sunny forecast, a low battery, an unusual day). The bar is higher scores than both the live wording and the rejected lines, 0 made-up figures and 0 advice that contradicts Energy's rules. HA builds any new read-only fact cards. Energy reviews the advice read-only for correctness.
4. **Before it goes live, the owner sees about 6–8 sample answers** across different situations, and it goes live only at his yes.

## Rails

Read-only facts; no control; Energy's never-by-implication list untouched; proportionate (the owner, 22:2x: "dont go crazy over this"); timers stay first in the queue.

## Amendment 1 (19 Oct 2026, 23:2x by the system clock)

- **Context:** PC Steward showed him four of Codex 49's sample answers, including "I can't judge tonight from the charge alone. I'm missing the remaining solar outlook and a useful evening-demand estimate."
- **the owner's words (verbatim):** "kind of? i just dont want things to end when some discussion or general history or knowledge could apply"
- **Scope change:** for questions and advice (not commands), Atlas must not stop at a dead end. When the exact data is missing or uncertain, it still gives the most useful answer it can from history (similar days, typical evening use, what happened last time), general knowledge (how batteries, solar and tariffs usually behave) and sensible reasoning, clearly labelled as an estimate and with its basis, then says what would firm it up. "I can't judge" is acceptable only when nothing relevant at all is known, and even then with a helpful next step. Answers stay brief and in the agreed voice; commands stay short (his "Don't turn a simple request into a conversation" still applies to requests). House AI updates Codex 49's samples and scorer so that dead-end answers score as misses when history or general knowledge could apply. Applies to Atlas's general questions too, not just energy.
- **Clarification (the owner, verbatim, 19 Oct 23:2x):** "yeah but it could do things like look at history, weather - generally you'll want to keep the house cool tonight etc..". So answers draw on the weather forecast and history together, and may add one brief, relevant practical pointer in the answer (for example comfort: "it's a warm night ahead, so you'll want to keep the house cool") when the readings support it. It's part of answering a question, not a separate offer and not on commands.
