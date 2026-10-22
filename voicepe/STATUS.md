# Status: Hey Atlas v2 and 26.9.0-atlas.2 (branch voicepe-hey-atlas-v2)

Updated 2026-10-22 (UTC). No access to the house; nothing is flashed.

| Stage | State |
| --- | --- |
| 0. Set-up | **done**: branch made from `voicepe-hey-atlas` (`be50b3d`), with `wakeword/` from `wakeword-hey-atlas` (`fde5323`) beside it. v1's pinned toolchain rebuilt (generator checkpoint and config hashes match v1's record); negative feature sets fetched (same revision and zip hashes as v1). Disk allows only VOiCES *far* for speech negatives (v1 used far + mid) |
| 1. v1 at cut-offs 0.93 / 0.90 / 0.85 / 0.80 | **done on v1's own (regenerated) sets**, TFLite Micro, W=3 (`wakeword/v2/results/v1/v1_ops_tflm.csv`). Recall val/test: 91.0/90.1% at 0.93, 92.6/91.8% at 0.90, 94.0/93.6% at 0.85, 95.0/94.5% at 0.80. False accepts, CHiME-6 val 9.67 h / DiPCo 5.33 h: 0/1, 2/1, 4/1, 6/4. v1's recorded figures reproduce (90.4% test recall, 1 DiPCo FA at 0.93). On the new far-field accented test set (2-5 m, TV/music/kitchen noise, held-out voices) v1 detects only **27%** at 0.93 (34% at 0.80); 0 false accepts in 2 h of simulated TV at 0.93-0.85 (`v1all_ops_litert.csv`, `v1all_breakdown_093.json`) |
| 2. v2 data (accented, far-field, hard negatives) | **done**: 38,000 training positives (LibriTTS-R 20,000; Piper VCTK 9,000 incl. Australian p374 and NZ p335; Kokoro 4,000; Piper ARU 3,000; Piper alba and northern-English 2,000), 21,500 hard negatives (2,050 'Atlas' mid-sentence sentences, hi/pay Atlas, hey Alice/Alex, at last, v1's confusables), 100 simulated living rooms (2-5 m talker, TV/music/kitchen/babble scenes from MUSAN CC BY 4.0 and synthetic sources), new far-field accented validation/test sets (1,850 positives each, held-out voices incl. Australian p326), 2 h simulated-TV ambient streams for validation and test |
| 3. v2 training (one run) and validation-only choice | **running** (started 14:19 UTC). A first attempt was **aborted at step 14,000**: with 4.0 s positive renders its 378-frame window always contained the audio frontend's 1-1.5 s start-up transient, so the model keyed on clip starts (streamed recall collapsed to 14%). Same data, window now 240 frames (2.4 s) starting at least 1.5 s into each clip; checked on checkpoint 3000 (recall no longer depends on lead-in length). Record: `wakeword/v2/results/aborted_run1/` |
| 4. v1 against v2 tables, cut-off recommendation | pending |
| 5. Images 26.9.0-atlas.2 (two clean builds each), config diff, 84 checks | pending |

---

# Earlier status (26.9.0-atlas.1, branch voicepe-hey-atlas)

# Status: Voice PE "Hey Atlas" firmware

| Stage | State |
| --- | --- |
| 1. Build | **done**: overlay, merged config, check script 84/84 (plus a 9-mutation self-test), both images built; two clean builds give identical SHA-256s; lock written |
| 2. Recovery image | **done**: official 26.9.0 factory image, 3,315,584 B, SHA-256 matches the published `.sha256` and the firmware.esphome.io manifest (`recovery/`) |
| 3. Pairing and flashing | **done**: a secret-free image keeps the pairing if NVS is not erased. Route: USB in the browser with esptool-js, factory image at 0x0, no erase, nothing installed on the PC (README) |
| Lock fix (review round, 2026-10-22) | **done: images unchanged.** Every Python package in both environments now has its artifact SHA-256 (esptool 4.12.0 included), the constraints file is vendored, and `tools/build.sh` enforces the whole lock before compiling. Two clean enforced builds give the reviewed hashes: factory `694a8948fc44b47731e596922936d6e0845435f8058015d0a97164cf1b4f6de9` (3,322,192 B), OTA `698f55d9acc103e015cc2437856359d32547290c946870d03239629c0d55c6a0` (3,256,656 B). 3 of 3 negative tests refuse (one changed hash each: pip, framework, component). Manual download-mode steps and PyYAML 6.0.3 recorded (README, `build/README.md`) |
| 4. Second model | **not done, on purpose**: one retrain is about 6¾ h of CPU plus about 6 GB of data, likely past the budget; the image and route are clear without it (README, "Stage 4") |

Verdict and day-one checks: `README.md`.
Nothing has been flashed or installed anywhere. No secrets, household data or recordings in this branch.
