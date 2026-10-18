# Hey Atlas wake word: training record

## Verdict (provisional: main run, checkpoint 26000)

**Provisional; candidate B (45,000 steps, extra rhyme negatives) is still training.** The model here is the main run's choice, made on validation only: checkpoint 26000, sliding window 3, cutoff 0.993. Validation recall 89.0% with 0 false accepts in 9.67 h; test recall 90.9% with 0 false accepts in 5.33 h (DiPCo). Hard-negative accepts are 3.0% (validation) and 4.6% (test). Phrases rhyming with "hey" + "Atlas" ("pay Atlas", "stay, Atlas") still trigger often. See `results/main/`.

### Pilot (1,000 positives, 10,000 steps)

Pilot, chosen on validation only (checkpoint 9000, sliding window 3, cutoff 0.97):

| Split | Recall (synthetic "Hey Atlas") | Hard-negative accepts | False accepts per hour (ambient) |
| --- | --- | --- | --- |
| train (sample) | 75.1% (601/800) | 1.4% (14/1000) | 0 in 2.0 h (CHiME-6 train sample) |
| validation | 76% (76/100) | 1.5% (3/200) | 0 in 9.67 h (dinner_party_eval, CHiME-6 dev/eval) |
| test | 73% (73/100) | 4.0% (8/200) | 0 in 5.33 h (dinner_party_eval, DiPCo) |

Worst confusables (test voices): "hi Atlas" 14/16 (probe-only, never trained on), "hey Ellis" 6/16, "my atlas" 4/16, "say Atlas" 4/16.

Full details, tools, hashes and settings follow in the final version.
