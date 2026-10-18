# Hey Atlas wake word: training record

## Verdict (provisional: mid-run model, main run step 14,000 of 30,000)

**The model in this folder is a mid-run checkpoint of the main run (36,000 positives), pushed to keep progress safe. It is not the final choice.** On validation it reaches 82.2% recall with 0 false accepts in 9.67 h; on test, 85.1% recall and 0 false accepts in 5.33 h (DiPCo), sliding window 7, cutoff 0.97 (`results/main_midrun/`). The pilot results below are kept for reference. This file is replaced when the run finishes.

### Pilot (1,000 positives, 10,000 steps)

Pilot, chosen on validation only (checkpoint 9000, sliding window 3, cutoff 0.97):

| Split | Recall (synthetic "Hey Atlas") | Hard-negative accepts | False accepts per hour (ambient) |
| --- | --- | --- | --- |
| train (sample) | 75.1% (601/800) | 1.4% (14/1000) | 0 in 2.0 h (CHiME-6 train sample) |
| validation | 76% (76/100) | 1.5% (3/200) | 0 in 9.67 h (dinner_party_eval, CHiME-6 dev/eval) |
| test | 73% (73/100) | 4.0% (8/200) | 0 in 5.33 h (dinner_party_eval, DiPCo) |

Worst confusables (test voices): "hi Atlas" 14/16 (probe-only, never trained on), "hey Ellis" 6/16, "my atlas" 4/16, "say Atlas" 4/16.

Full details, tools, hashes and settings follow in the final version.
