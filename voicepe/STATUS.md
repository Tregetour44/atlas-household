# Status: Voice PE "Hey Atlas" firmware

| Stage | State |
| --- | --- |
| 1. Build | **done**: overlay, merged config, check script 84/84 (plus a 9-mutation self-test), both images built; two clean builds give identical SHA-256s; lock written |
| 2. Recovery image | **done**: official 26.9.0 factory image, 3,315,584 B, SHA-256 matches the published `.sha256` and the firmware.esphome.io manifest (`recovery/`) |
| 3. Pairing and flashing | **done**: a secret-free image keeps the pairing if NVS is not erased. Route: USB in the browser with esptool-js, factory image at 0x0, no erase, nothing installed on the PC (README) |
| 4. Second model | **not done, on purpose**: one retrain is about 6¾ h of CPU plus about 6 GB of data, likely past the budget; the image and route are clear without it (README, "Stage 4") |

Verdict and day-one checks: `README.md`.
Nothing has been flashed or installed anywhere. No secrets, household data or recordings in this branch.
