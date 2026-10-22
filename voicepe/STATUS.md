# Status: Hey Atlas v2 and 26.9.0-atlas.2 (branch voicepe-hey-atlas-v2)

Updated 2026-10-22 (UTC). No access to the house; nothing is flashed.

| Stage | State |
| --- | --- |
| 0. Set-up | **done**: branch made from `voicepe-hey-atlas` (`be50b3d`), with `wakeword/` from `wakeword-hey-atlas` (`fde5323`) beside it. v1's pinned toolchain rebuilt (generator checkpoint and config hashes match v1's record); negative feature sets fetched (same revision and zip hashes as v1). Disk allows only VOiCES *far* for speech negatives (v1 used far + mid) |
| 1. v1 at cut-offs 0.93 / 0.90 / 0.85 / 0.80 | **running**: v1's validation/test sets regenerated (v1 voices, templates and splits; new seeds), stream features being made |
| 2. v2 data (accented, far-field, hard negatives) | **running**: scripts in `wakeword/v2/scripts/`; synthesis queued (LibriTTS-R, Piper VCTK incl. the Australian and NZ speakers, Piper ARU and GB voices, Kokoro), simulated living rooms, MUSAN (CC BY 4.0) streaming |
| 3. v2 training (one run) and validation-only choice | pending |
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
