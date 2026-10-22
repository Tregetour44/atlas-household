# Voice PE with an on-device "Hey Atlas" wake word

## 26.9.0-atlas.2 (2026-10-22): verdict

**Flash `images/atlas-voicepe-hey-atlas-26.9.0-atlas.2.FACTORY-usb-offset-0x0.bin`**
(3,322,192 bytes, SHA-256 `73b876824c06ba32eea82e4c7e142641247ef84cf745923eb5548bb6aebf4fe2`), with the same route as before: USB, esptool-js, **factory image at offset 0x0, no erase** ([steps](#steps-for-2690-atlas2)). Wi-Fi, the Home Assistant pairing, the area and the pipeline stay.

* **v1 against v2: v1 wins, so the model is unchanged.** The new v2 model (more accents, far-field rooms, TV/music/kitchen noise, 2,000 "Atlas" mid-sentence negatives) is worse at its validation-only choice. It detects 54% of v1's test "Hey Atlas" clips against v1's 90%, and 28% against 27% on the new far-field set. It only gets fewer hard-negative accepts by being deaf. Details: `../wakeword/v2/TRAINING.md`.
* **Chosen cut-off: 0.85** (from 0.93), for v1. The image is atlas.1 with only the Hey Atlas manifest's `probability_cutoff` changed and the version bumped. In the app image that is one byte (threshold 237 → 216), the version string, ESPHome's config hash and the image's own checksums: 73 bytes in all (`build-atlas.2/image-diff-OTA-vs-atlas.1.txt`).
* **Expected trade-off (synthetic speech, simulated rooms; real-device numbers are NO DATA):**
  * Misses drop from about **1 in 10 to 1 in 15** when spoken near the device (test recall 90.1% → 93.6%).
  * Across a noisy room it still misses most attempts. On the new simulated far-field set (2–5 m, TV/music/kitchen at 0–20 dB, accented held-out voices), recall goes from **27% to 32%**. The cut-off helps a little; it does not fix far-field. Speaking up, facing the device or lowering the TV will matter more than any cut-off.
  * **Extra false wakes: about one more per 4 hours of lively conversation in the room.** Over 15 h of recorded dinner-party audio (CHiME-6 and DiPCo) there are 5 false accepts at 0.85 against 1 at 0.93 (0.33 /h against 0.07 /h). DiPCo alone stays at 1 in 5.33 h (0.19 /h). There were none in 4 h of simulated TV.
  * Saying the name in passing wakes it a bit more often (new test voices, near field): "hi Atlas" 59% (was 50%), "pay Atlas" 62% (58%), "hey Alice" 22% (17%), "hey Alex" 14% (8%). Far field, "Atlas" mid-sentence: 5 of 484 sentences (2).
* **Fallback, one step back towards today:** `images/atlas-voicepe-hey-atlas-26.9.0-atlas.2-c090.FACTORY-usb-offset-0x0.bin` (cut-off 0.90, SHA-256 `a67397f3f5c770ad37429449802d2b5442f67740f17cea642aed81bc7271238d`). It gives 91.8% / 29% recall, with 3 false accepts in 15 h of dinner-party audio. To go back fully, flash atlas.1 (`images/…atlas.1.FACTORY…`, `694a8948…4f6de9`) the same way.
* **Builds:** two clean builds each on branch `voicepe-hey-atlas`'s enforced lock (`tools/build.sh`, `pip --require-hashes`, every fetch hash-checked), with identical SHA-256s (A in the working tree, B in a fresh clone). The 84-check script passes 84/84, and its self-test still fails all nine broken variants. The merged config differs from atlas.1's only in the version line (`build-atlas.2/merged-config-diff.txt`).

### v1 operating points (TFLite Micro, ESPHome's runtime; W = 3)

| Cut-off (device threshold) | Recall, near (v1 test, 3,600) | Recall, far-field accented (1,850) | False accepts, CHiME-6 val 9.67 h | False accepts, DiPCo test 5.33 h | False accepts, TV 4 h | Hard-negative accepts (v1 test / far-field) |
| --- | --- | --- | --- | --- | --- | --- |
| 0.93 (237), atlas.1 | 90.1% | 27.2% | 0 | 1 (0.19 /h) | 0 | 5.5% / 6.6% |
| 0.90 (229), fallback | 91.8% | 29.0% | 2 (0.21 /h) | 1 (0.19 /h) | 0 | 6.9% / 7.4% |
| **0.85 (216), atlas.2** | **93.6%** | **31.7%** | 4 (0.41 /h) | 1 (0.19 /h) | 0 | 8.5% / 8.3% |
| 0.80 (204) | 94.5% | 34.2% | 6 (0.62 /h) | 4 (0.75 /h) | 1 | 10.1% / 9.1% |

Why 0.85 and not 0.80: from 0.85 to 0.80, DiPCo false accepts go from 1 to 4 and the first TV false accept appears, for about one more point of recall. The threshold is `int(cutoff × 255)`, read from ESPHome 2026.9.1's source (the wheel hash in the lock), so 0.85 is exactly 216 on the device. v1's own recorded figures reproduce on the regenerated sets (90.1% against 90.5% test recall; the same single DiPCo false accept at 0.93).

### v1 against v2 (same test sets, each at its validation-only choice, LiteRT)

| | v1 (W 3, 0.93) | v2 (checkpoint 24000, W 5, 0.95) |
| --- | --- | --- |
| Recall, v1 test (near) | **90.1%** | 54.2% |
| Recall, far-field accented test | 27.1% | 28.2% |
| … the held-out Australian voice (VCTK p326) | **17.1%** (36/211) | 11.8% (25/211) |
| Hard-negative accepts, v1 test / far-field test | 5.6% / 6.6% | **0.9% / 3.9%** |
| False accepts, DiPCo 5.33 h / TV 2 h | 0 / 0 | 0 / 0 |

v2's choice rule was fixed before any v2 checkpoint was scored. With a looser cap matching v1's own hard-negative rate, its best validation recall is still only 70% near-field against v1's 91% (`../wakeword/v2/TRAINING.md`). Per-accent, per-engine and per-phrase tables: `../wakeword/v2/results/`.

### Steps for 26.9.0-atlas.2

The device is on 26.9.0-atlas.1 today. The route and the safety facts are unchanged: USB at 0x0 without erase keeps NVS (Wi-Fi, API key, settings) at 0xF90000, and the partition table is identical (`build-atlas.2/partitions.csv`, byte-identical to atlas.1's and to stock's).

1. On the PC, download `voicepe/images/atlas-voicepe-hey-atlas-26.9.0-atlas.2.FACTORY-usb-offset-0x0.bin` from branch `voicepe-hey-atlas-v2`. In PowerShell run `Get-FileHash <file> -Algorithm SHA256`. It must print `73B876824C06BA32EEA82E4C7E142641247EF84CF745923EB5548BB6AEBF4FE2`. Use the file whose name contains **FACTORY**, never **OTA-app-only**.
2. Check that the device is online in Home Assistant.
3. Connect it to the PC with a USB-C **data** cable.
4. In Chrome or Edge, open https://espressif.github.io/esptool-js/, leave the baud rate, click **Connect**, and pick the USB serial / JTAG device. The log shows an ESP32-S3. If it cannot connect, use the manual download mode below (hold the centre button while plugging in).
5. Keep one row in the flash table: **Flash Address `0x0`** (it defaults to 0x1000; change it), with the FACTORY file.
6. Click **Program**. Do **not** click "Erase Flash". Wait for the write and verify.
7. Unplug, then power it normally. Within about a minute it should come back online in Home Assistant by itself, showing firmware **26.9.0-atlas.2 (ESPHome 2026.9.1)**. The Wake word setting should still be **Hey Atlas**. If it shows Okay Nabu, set it to Hey Atlas again. The log line `Enabled wake word: Hey Atlas` appears, and the model's start-up dump prints `Probability cutoff: 0.85` (216/255).
8. Then the earlier day-one checks 3–5 below (area and pipeline kept, stock features work, no allocation errors or reboots in 10 minutes of logs). Try "Hey Atlas" near the device and from across the room.

Manual download mode, the route-C fallback (OTA with the ESPHome CLI, which must use `images\atlas-voicepe-hey-atlas-26.9.0-atlas.2.OTA-app-only.bin`, SHA-256 `23085856bba25dd34f601c7b76e33343612d614421a4e3a1162b8acc8b8830b0`) and recovery are as described for atlas.1 below. They apply unchanged. The Home Assistant "Wake word sensitivity" select still changes only the stock models; Hey Atlas uses its manifest cut-off.

### Build record (26.9.0-atlas.2)

| Image | Size | SHA-256, build A | SHA-256, build B |
| --- | --- | --- | --- |
| `atlas-voicepe-hey-atlas-26.9.0-atlas.2.FACTORY-usb-offset-0x0.bin` | 3,322,192 | `73b876824c06ba32eea82e4c7e142641247ef84cf745923eb5548bb6aebf4fe2` | same |
| `atlas-voicepe-hey-atlas-26.9.0-atlas.2.OTA-app-only.bin` | 3,256,656 | `23085856bba25dd34f601c7b76e33343612d614421a4e3a1162b8acc8b8830b0` | same |
| `atlas-voicepe-hey-atlas-26.9.0-atlas.2-c090.FACTORY-usb-offset-0x0.bin` (fallback) | 3,322,224 | `a67397f3f5c770ad37429449802d2b5442f67740f17cea642aed81bc7271238d` | same |
| `atlas-voicepe-hey-atlas-26.9.0-atlas.2-c090.OTA-app-only.bin` (fallback) | 3,256,688 | `4017abae77e20d94859a099c8fbe4739e9fbf61ede570e47ef92e95fb56851c0` | same |

* Inputs: atlas.2 at commit `1971793`, fallback at commit `5ef499d`. The only input changes from atlas.1 (`tools/set_model.py`): `models/hey_atlas/hey_atlas.json` (`probability_cutoff` only; SHA-256 `2f2204ab…aeac4` for atlas.2, `05446104…04082` for the fallback), the version in `hey-atlas-voice-pe.yaml`, and the matching lock entries, expected hashes and image name in `lock/dependency-lock.json`, `tools/check_merged.py`, `tools/make_lock.py` and `tools/build.sh`. `hey_atlas.tflite` is byte-identical (`2bb30e62…0ffba7`).
* Build A ran in the working tree, build B in a fresh clone of that commit, both from nothing (`tools/build.sh`: new venvs from hashed requirements, empty caches). Each took about 10 minutes. Fetch logs: 84 entries, no lock violation.
* `partitions.csv`, `sdkconfig.txt` and `dependencies.lock` are identical to atlas.1's. `build_info.json` differs only in `config_hash`.
* Records: `build-atlas.2/` (atlas.2) and `build-atlas.2-c090/` (fallback). Each holds `lock-enforced-build-{A,B}.txt`, `build-log-{A,B}.txt`, `fetch-log-{A,B}.txt`, `SHA256SUMS-{A,B}`, `check-report.txt`, `check-selftest.txt`, `merged-config.yaml`, `merged-config-diff.txt`, `partitions.csv`, `sdkconfig.txt`, `dependencies.lock`, `build_info.json` and `memory-report.txt`. `build-atlas.2/` also has `image-diff-OTA-vs-atlas.1.txt` (from `tools/image_diff.py`). The fallback image is 32 bytes longer than atlas.2 because of its longer version string, so it has no byte-for-byte diff. Its merged config differs from atlas.1's and atlas.2's only in the version line, and its 84 checks and self-test pass too. The atlas.1 records in `build/` are untouched.

### Budget, and what was not done

* No paid cloud service was used; everything ran in this session's 4-core container with no GPU. Cloud spend cannot be measured from inside the session. Wall clock was about 5¼ h (11:10–16:30 UTC), less than v1's 6¾ h: v2 data and one kept training run plus one aborted attempt, v1 rescoring, and four image builds.
* v2 was not retrained a second time (the brief allows one run). Its likely problems (a 2.4 s window, heavy far-field noise in 65% of positives, and only one VOiCES speech-negative set because of disk) are listed in `../wakeword/v2/TRAINING.md` for a later session.
* **NO DATA:** real voices, the owner's accent, the real room, the TV, and the Voice PE's microphones and XMOS front end (beamforming, echo cancellation, gain). The far-field set is a simulation without that front end. Nothing was flashed, and the house was not accessed.

# Earlier record: 26.9.0-atlas.1 (superseded by 26.9.0-atlas.2 above; kept for reference)

Everything below describes 26.9.0-atlas.1. Its pairing, route, recovery and lock facts still hold for 26.9.0-atlas.2, which differs only in the Hey Atlas manifest's cut-off and the version. **To flash, use the atlas.2 file and steps above, not the atlas.1 file named below.**

## Lock fix round (2026-10-22): images unchanged

**Images unchanged. The reviewed image stands.** Two clean rebuilds with the now complete and enforced lock give byte-for-byte the reviewed images:

| Image | Size (bytes) | SHA-256, reviewed | SHA-256, enforced build A | SHA-256, enforced build B |
| --- | --- | --- | --- | --- |
| `FACTORY-usb-offset-0x0` | 3,322,192 | `694a8948fc44b47731e596922936d6e0845435f8058015d0a97164cf1b4f6de9` | same | same |
| `OTA-app-only` | 3,256,656 | `698f55d9acc103e015cc2437856359d32547290c946870d03239629c0d55c6a0` | same | same |

The files in `images/` are not touched by this round.

What the review found and what changed (details: `build/README.md`, "Lock enforcement"):
* **Every Python package now has an artifact hash.** That covers both environments, including esptool 4.12.0 in the ESP-IDF one: one SHA-256 per package, of the exact wheel or sdist used (`lock/requirements-esphome.txt`, 83 + pip; `lock/requirements-esp-idf.txt`, 60 + pip; `lock/requirements-bootstrap.txt`, pip and setuptools).
* **The constraints file is vendored** (`lock/espidf.constraints.v5.5.txt`, SHA-256 `6b53b365…7aa1`, unchanged at the URL on 2026-10-22). The build never fetches the URL; idf.py reads the vendored copy.
* **`tools/build.sh` enforces the lock before compiling.** It builds both venvs from nothing with `pip install --require-hashes --no-deps --no-build-isolation`, and each env must then hold exactly the locked packages. ESPHome runs under `tools/esphome_repro.py`, which stops the build on any request or download that is not in the lock or has another SHA-256, and which uses the locked ESP-IDF env instead of ESPHome's own pip/uv install. The git commit, the models, the framework, the tools and the registry components are checked against the lock before any image is written.
* **Negative tests** (`build/negative-test-log.txt`, `tools/negative_test.sh`), each changing one hash by one digit. Every one refuses with exit status 1 and no image:
  * esptool 4.12.0's hash: pip refuses ("THESE PACKAGES DO NOT MATCH THE HASHES");
  * the ESP-IDF tarball's hash: the guard refuses the download ("LOCK VIOLATION");
  * espressif/esp-nn's component hash: the post-compile check refuses.
* **Manual download mode** is added to the [steps](#steps-recommended-route): hold the centre button while plugging in USB.
* **PyYAML 6.0.3** is recorded, with hashes for every platform (`lock/requirements-check.txt`), so the 84-check script reruns on any computer.

## Verdict

**Image to flash:** `images/atlas-voicepe-hey-atlas-26.9.0-atlas.1.FACTORY-usb-offset-0x0.bin`
(3,322,192 bytes, SHA-256 `694a8948fc44b47731e596922936d6e0845435f8058015d0a97164cf1b4f6de9`).
It is the official Voice PE 26.9.0 firmware (commit `2644f4c`) plus the Hey Atlas model, built with ESPHome 2026.9.1. The HTTP update channel is removed. Every input is pinned, and two clean builds give the same hash.

**Route: USB from the Windows PC, in Chrome or Edge, with Espressif's web flasher (esptool-js). Write the factory image at offset 0x0 and do not erase.** Nothing is installed on the PC. The device keeps its Wi-Fi, its Home Assistant pairing (API key), its area, its pipeline and its settings. Two facts make that true:
* NVS, which holds them, sits at 0xF90000, far beyond the end of the image (0x32B150).
* The partition table is byte-identical to stock 26.9.0.

Exact steps: [below](#steps-recommended-route).

**Do not use ESPHome Web's "Install" with this file** unless a full wipe is intended. For an uploaded file it always erases the whole flash first.

**Way back to stock:** the official installer pinned to 26.9.0 (`https://esphome.github.io/home-assistant-voice-pe/?version=26.9.0`). It recognises this image as the same firmware and offers "Update", which does not erase. Details: [`recovery/RECOVERY.md`](recovery/RECOVERY.md).

**Stays NO DATA until the real device:**
* Hey Atlas recall and false accepts with real voices, the household's accents, TV and radio, through the Voice PE's microphones and XMOS front end (all training and test speech was synthetic).
* Run-time memory: the real tensor-arena use and free PSRAM and heap with five models loaded.
* CPU load and wake latency.
* Whether this unit enters download mode through esptool-js without pressing a button. If it does not, the manual steps (hold the centre button while plugging in USB) are in [Steps](#steps-recommended-route).
* Whether ESPHome 2026.9.1, rather than the 2026.6.0 that built stock 26.9.0, changes any stock behaviour on this hardware.
* The household's Home Assistant version (it matters only after an erase).

**Day-one checks**, in order:
1. Before flashing: the device is adopted on stock firmware, and "Okay Nabu", the centre button and the mute switch work. Note the device's area and its Assist pipeline in Home Assistant.
2. Flash as below. Within about a minute: the LED ring goes from start-up to idle, and in Home Assistant the device comes back **online on its own**. That shows Wi-Fi reconnected and the API reconnected with the stored key, with no "reconfigure" or re-authentication prompt. The device page shows firmware **26.9.0-atlas.1 (ESPHome 2026.9.1)**.
3. **Area and pipeline kept**: the same device in the same area, with the same Assistant/pipeline selection, and its entities not renamed.
4. **Stock still works**: "Okay Nabu" wakes it and Assist answers once (one wake sound, one response). A centre-button press starts Assist. The mute switch silences the microphones (red LEDs), and "Okay Nabu" is ignored while muted. "Stop" ends a long answer or a ringing timer.
5. **Logs** (Settings, then Devices, then the device's ESPHome page, then Logs; or the ESPHome add-on's log view if it is installed) over at least 10 minutes of idle plus a few commands. **None** of these should appear:
   * `Could not allocate the streaming model's tensor arena`, `Failed to allocate tensors`, `Arena size probe failed`, `Encountered an error allocating buffers`, `Encountered an error while performing an inference`;
   * `Not enough free bytes in ring buffer` (audio was dropped before the wake detector);
   * `Read error` from the microphone, `Partial DMA write` or `ISR event queue overflow` from the speaker;
   * a reboot. The `debug` component reports the reset reason at boot; it must not be a watchdog or panic reset.
   Expected and fine: `Probed tensor arena size: … bytes` once per model.
6. Only then, in Home Assistant, set the device's **Wake word** to **Hey Atlas**. The device allows one active wake word (`max_active_wake_words = 1`), so this turns Okay Nabu off. The log shows `Enabled wake word: Hey Atlas (id=hey_atlas)`. Then try "Hey Atlas" from across the room, and expect the weak spots below.

**Known weak spots of the Hey Atlas model** (synthetic tests, `wakeword/TRAINING.md` on branch `wakeword-hey-atlas`):
* About 9 in 10 "Hey Atlas" detected; 0.19 false accepts per hour on DiPCo.
* "hi Atlas" triggers it 88% of the time and "pay Atlas" 72%. "Atlas" inside a sentence triggers it 30–40% of the time. In this house, saying the assistant's name in conversation will sometimes wake the device.
* The "Wake word sensitivity" select only changes the stock models. Hey Atlas uses its manifest cutoff 0.93. The cutoff 0.95 option in TRAINING.md would need a manifest edit and a rebuild, which gives a new hash.

## What the image is

`hey-atlas-voice-pe.yaml` is the overlay. ESPHome expands it into `build/merged-config.yaml`.

| Part | Stock 26.9.0 factory image | This image |
| --- | --- | --- |
| Base YAML | `home-assistant-voice.yaml` via the factory wrapper | the same file at `2644f4c`, vendored (`base/`), byte-identical except one line (next row) |
| voice_kit external component | git `ref: dev` | `ref: 2644f4c…` (`base/home-assistant-voice.yaml.patch`) |
| Sounds | `…/raw/dev/sounds/…` | `raw.githubusercontent.com/…/2644f4c…/sounds/…` |
| Wake models | okay_nabu (release 20241226.3), hey_jarvis, hey_mycroft (repo `main`), stop (internal) | the same files, vendored and hashed (`models/stock/`), the same ids, plus **hey_atlas** (`models/hey_atlas/`) |
| VAD | default `vad` (repo `main`) | the same file, vendored |
| Wake handler, mute gate, stop-word scripts, Assist start | from the base | unchanged: the overlay only replaces model sources (`!extend`) |
| Framework | `recommended` | ESP-IDF `5.5.5` (what `recommended` means in 2026.9.1), toolchain `esp-idf`, both written out |
| Improv (BLE and USB), BLE/API start-up order | factory wrapper | copied from the factory wrapper |
| `update: http_request`, `ota: http_request`, `http_request:`, "Beta firmware" switch, `dashboard_import` | present | **absent** |
| Project | `Nabu Casa.Home Assistant Voice PE` / release version | same name / **`26.9.0-atlas.1`** |
| ESPHome | 2026.6.0 (the repo's CI at `2644f4c`) | 2026.9.1 (as specified) |

Why the base YAML is vendored rather than pulled as a remote package: ESPHome concatenates `external_components` lists from packages, and the entries have no `id`. So an overlay cannot replace or `!remove` upstream's `ref: dev` entry, and the `dev` clone would still be fetched. A byte-identical copy with that one line changed is the smallest change that fetches only `2644f4c`. `tools/check_merged.py` proves the copy restores to upstream's git blob `dbf258e1…`.

**Proved from the merged config** by `tools/check_merged.py` (84/84, `build/check-report.txt`; the self-test `build/check-selftest.txt` shows it fails on nine broken variants):
* the five models are each present exactly once, with the right internal flags and file hashes;
* one VAD and one `on_wake_word_detected` handler, which is gated by `master_mute_switch` and contains exactly one `voice_assistant.start`;
* `master_mute_switch` and `hardware_mute_switch` are defined once each;
* `voice_assistant.micro_wake_word: mww` and `use_wake_word: false` (no server-side wake word, so no second start path);
* the counts of `voice_assistant.start`, `micro_wake_word.start`, `enable_model` and `disable_model` equal stock;
* the BLE wait runs first on connect;
* no `update`, `http_request` or `dashboard_import`, a single `esphome` OTA, and no firmware.esphome.io URL;
* every URL is pinned to `2644f4c` (or is the md5-checked XMOS release), and the framework is 5.5.5;
* no API key, OTA password, Wi-Fi network or `!secret`.

Build facts (`build/README.md`):
* OTA image 3,256,656 B, 40.1% of the 8 MB app slot. Static internal RAM 51.1%.
* The partition table equals stock; the bootloader differs (ESP-IDF 5.5.5).
* `lock/dependency-lock.json` lists every fetched URL, commit and hash, and each was re-downloaded and matched: the ESPHome Python environment with PyPI hashes, the upstream commit and blobs, the 16 sounds, the XMOS firmware, the model sources, the ESP-IDF tarball, the toolchain, the IDF components and the PlatformIO libraries.

## Pairing

**Can a secret-free image keep the pairing made at adoption? Yes, as long as the flash's NVS partition is not erased.**

* **API encryption key.** Stock 26.9.0 has `api: encryption:` with no key. Home Assistant sets the key at adoption, and ESPHome stores it in NVS under preference key `88491486` (ESPHome 2026.6.0 `components/api/api_server.cpp`: `uint32_t hash = 88491486UL`; 2026.9.1: `NOISE_PSK_PREF_HASH = 88491486UL`; the same 32-byte `SavedNoisePsk` struct). This image also has `encryption:` with no key (`encryption: {}` in the merged config), so it does not define `USE_API_NOISE_PSK_FROM_YAML` and loads the saved key at boot ("Loaded saved Noise PSK"). On ESP32 the NVS entry is keyed by that number alone (`components/esp32/preferences.cpp`: `backend.key = type`), so a different firmware build reads the same entry.
* **Wi-Fi.** With no networks in the YAML, both versions keep the Improv-provisioned credentials under the fixed key `88491487` (`wifi_component.cpp`: `has_sta() ? App.get_config_version_hash() : 88491487UL`). This image compiles no networks (`networks: []`).
* **OTA password.** Stock has none, and neither does this image. The stock device (ESPHome 2026.6.0) accepts unauthenticated OTA on port 3232. This image (2026.9.1) logs "Encryption: offered, plaintext accepted" (`USE_OTA_ENCRYPTION_PROVISIONED`, not `…_REQUIRED`), so it also accepts the plain upload the ESPHome CLI makes. That is stock behaviour, not a regression. Requiring encryption would need a key in the image, which is out of scope.
* **What keeps NVS:** an OTA, or a USB write at 0x0 without erase. The image covers 0x0–0x32B150, and NVS is 0xF90000–0xFFFFFF (`build/partitions.csv`, identical to stock's partition table).
* **What loses it:** any erase. That includes ESPHome Web's "Install" of an uploaded file (`web.esphome.io/src/install-upload/install-upload-dialog.ts` in `esphome/dashboard` at `72b9b1b`: `erase: true`), esptool-js's "Erase Flash" button, and a factory reset from the device.

**If NVS is ever erased, the smallest safe local step** involves no secret in the repo and none typed into a file:
1. Give the device Wi-Fi with Improv: ESPHome Web's "Configure Wi-Fi" right after flashing (Improv Serial), or the Home Assistant app over BLE. Both are in the image.
2. Home Assistant sees the device without encryption and starts a re-authentication: "The ESPHome device … disabled transport encryption. Please confirm that you want to remove the encryption key…". Confirm it. On the next connection, Home Assistant provisions a key again, its stored key for this device if it has one, otherwise a new one. It sends it over a zero-PSK Noise connection on recent versions (`homeassistant/components/esphome/manager.py` `_handle_dynamic_encryption_key` and `config_flow.py` `reauth_encryption_removed_confirm`, core `dev` at `101263217a1a`, 2026.11.0.dev). The config entry is kept, so the area and pipeline stay. On-device settings (volume, sensitivity, LED, chosen wake word) go back to defaults. The household's HA version is NO DATA; if its prompt differs, deleting and re-adding the device also works but loses the area and pipeline assignment.

**No placeholder is needed.** The image has no key, password or network. Do not add one. If someone ever builds a variant with a compiled key, it belongs in a `secrets.yaml` next to the YAML (ignored by `voicepe/.gitignore`), never in git.

## Flashing routes compared

| | A. USB in the browser | B. OTA from Home Assistant (ESPHome integration or Device Builder add-on) | C. ESPHome CLI on the PC |
| --- | --- | --- | --- |
| Installs on the Windows PC | **none** (Chrome or Edge; Windows 10/11 has the USB serial driver for the ESP32-S3's native USB) | none on the PC; the **Device Builder add-on on Home Assistant** | Python 3.11+ and `pip install esphome==2026.9.1` (84 packages) |
| Flashes the audited image? | yes, the factory image as built | **no**. The ESPHome integration cannot upload a prebuilt `.bin`; the add-on recompiles the YAML with *its* ESPHome version (2026.10.x today), which gives a different, unchecked image | yes, the OTA image (`esphome upload … --file`) |
| Keeps pairing and settings | **yes with esptool-js** (no erase). **No with ESPHome Web** (always erases) | yes (OTA) | yes (OTA) |
| Cable | USB-C to the PC | none | none |
| Other risks | esptool-js's first row defaults to offset `0x1000`; it must be `0x0`. Do not press "Erase Flash" | the add-on is a new service in the house, copying the folder into `/config/esphome`, and a long build on HA hardware | the CLI validates the YAML before uploading, so it needs the same network fetches as a build |

**Recommendation: A with esptool-js.** It has the fewest installs (none), flashes exactly the audited bytes, and keeps the pairing. C is the fallback if USB download mode cannot be reached. B is not recommended for this image.

## Steps (recommended route)

1. On the PC, download the branch's `voicepe/images/atlas-voicepe-hey-atlas-26.9.0-atlas.1.FACTORY-usb-offset-0x0.bin`. In PowerShell run `Get-FileHash <file> -Algorithm SHA256`. It must print `694A8948FC44B47731E596922936D6E0845435F8058015D0A97164CF1B4F6DE9`. Use the file whose name contains **FACTORY**, never the **OTA-app-only** one.
2. Check that the device is online in Home Assistant on stock firmware (day-one check 1).
3. Connect the Voice PE to the PC with a USB-C **data** cable.
4. In Chrome or Edge, open https://espressif.github.io/esptool-js/. Leave the baud rate at its default and click **Connect**. Pick the device's port (a USB serial / JTAG device). The log shows the chip as ESP32-S3.
5. In the flash table, keep one row only. Set **Flash Address `0x0`** (it defaults to 0x1000; change it) and choose the FACTORY file. Leave flash mode, frequency and size on "keep" if they are shown.
6. Click **Program**. Do **not** click "Erase Flash". Wait for the write and verify to finish.
7. Unplug the USB cable, then plug the device back into its normal power. Go through day-one checks 2–6.

**If step 4 cannot connect or does not reach the ESP32-S3** (automatic entry into download mode is NO DATA for this unit), put the device into download mode by hand and try again:

a. Unplug the USB-C cable from the Voice PE. The device has no other power, so it is now off.
b. Press and hold the **centre button** (the button in the middle of the dial on top). It is wired to GPIO0, the ESP32-S3's boot-mode strap pin (`base/home-assistant-voice.yaml`, `center_button`: `number: GPIO0`, inverted). Held down at power-up, it starts the chip's ROM bootloader instead of the firmware.
c. Still holding it, plug the USB-C cable from the PC back into the Voice PE. Keep holding for about 2–3 seconds, then release. In download mode the LED ring stays dark and there is no start-up sound, because the firmware is not running.
d. Repeat step 4 (**Connect**). In download mode the port may appear under a different COM number; pick the USB serial / JTAG device again. Then continue with steps 5–7. Step 7 (unplug and replug **without** holding the button) leaves download mode and starts the new firmware.

Safe because: holding the button at power-up erases nothing; it only selects the boot mode. The firmware's factory reset needs the button held for **22 seconds while the firmware is running**, with a warning sound and LED effect at 10 seconds (`base/home-assistant-voice.yaml`, `on_multi_click`: "ON for at least 10s", then "ON for at least 22s"). So if the LED ring lights up and the "factory reset coming up" sound plays, the device booted normally instead: **release the button at once** (releasing before 22 s cancels the reset), unplug, and try steps a–c again.

If it still cannot connect after the manual steps, stop. Do not try ESPHome Web unless a full wipe is acceptable. Use route C instead:

```
py -3.13 -m venv %USERPROFILE%\esphome-2026.9.1
%USERPROFILE%\esphome-2026.9.1\Scripts\pip install esphome==2026.9.1
cd atlas-household\voicepe
%USERPROFILE%\esphome-2026.9.1\Scripts\esphome upload hey-atlas-voice-pe.yaml --device <device IP from Home Assistant> --file images\atlas-voicepe-hey-atlas-26.9.0-atlas.1.OTA-app-only.bin
```

Here the CLI only uploads the prebuilt, hash-checked OTA image; it compiles nothing, so its own packages cannot change the image bytes. The hashed lock in `lock/requirements-esphome.txt` is for the Linux x86_64 build and its wheels do not install on Windows, which is why this step uses a plain `pip install`.

## Recovery

* **Back to stock 26.9.0, keeping pairing:** open `https://esphome.github.io/home-assistant-voice-pe/?version=26.9.0` over USB, then **Update**. This works because esp-web-tools 10.4.0 treats an Improv device reporting the same project name as "same firmware" and installs without erasing. Or use the same esptool-js steps with the official factory image (URL and SHA-256 `98b7e304…d9da` in `recovery/RECOVERY.md`).
* **If the Atlas image crashes after an OTA (route C):** ESP-IDF app rollback is on in this image (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y` in `build/sdkconfig.txt`), and also by ESPHome default in stock. `safe_mode` marks a new app good only after it has run for 1 minute. An app that keeps crashing before that is rolled back by the bootloader to the previous one. An app that runs but misbehaves is not; use the stock recovery above. After a USB factory write there is no previous app to fall back to.
* **If the device will not boot at all:** the USB routes still work, because the ROM bootloader is in silicon. A full erase plus the official image (ESPHome Web, Install) is the last resort; then follow "after an erase" in [Pairing](#pairing).
* Afterwards the stock firmware's own update channel is back.

## Stage 4 (second model): not done

Skipped on purpose. The brief allows it only if stages 1–3 used under half the budget, and I cannot measure cloud spend from inside the session. More decisive, one retrain costs about what the whole first training did: about 6¾ hours on a 4-core CPU, plus about 6 GB of negative data and the trainer environment rebuilt from scratch (`wakeword/TRAINING.md`, "Run time"). It also needs a public TV/radio speech set with acceptable terms, which has not been vetted. That would very likely pass the US$25 ceiling. The image and the route are clear without it.

The plan for a later session, unchanged from the brief:
* Add about 2,000 synthetic sentences that use "Atlas" mid-sentence ("ask Atlas about…", "the atlas on the shelf", "Atlas said…") and the rhyme family, as training negatives.
* Add a vetted broadcast-speech negative set.
* Keep the same splits, evaluation and validation-only choice, and the 3% hard-negative cap.
* Ship a second image only if validation false accepts improve with recall within 3 points.

## Files

| Path | What |
| --- | --- |
| `hey-atlas-voice-pe.yaml` | the overlay (build this) |
| `base/home-assistant-voice.yaml`, `.patch` | upstream base at `2644f4c`, one line pinned |
| `models/` | hey_atlas (from branch `wakeword-hey-atlas`, `fde5323`) and the vendored stock models (Apache-2.0, `LICENSE`) |
| `build/merged-config.yaml` | the full merged config |
| `build/check-report.txt`, `build/check-selftest.txt` | the check script's results |
| `build/build-log.txt`, `build/build-log-repro.txt` | ESPHome compile logs of the two clean, lock-enforced builds (A in the working tree, B in a fresh clone) |
| `build/lock-enforced-build-A.txt`, `-B.txt` | the whole `tools/build.sh` output of each: hash-checked pip installs, every lock check, image hashes |
| `build/fetch-log-A.txt`, `-B.txt` | every request ESPHome made and every file it downloaded, with SHA-256 |
| `build/negative-test-log.txt` | the three negative tests (one changed hash each; the build refuses) |
| `build/README.md` | sizes, memory, partitions and reproducibility |
| `build/memory-report.txt`, `partitions.csv`, `dependencies.lock`, `sdkconfig.txt`, `build_info.json` | build outputs |
| `images/` | the two images, `SHA256SUMS`, `SIZES` |
| `lock/dependency-lock.json` | every fetched input with its hash, and the fetch allowlist the build enforces |
| `lock/requirements-*.txt` | hashed Python packages: `esphome`, `esp-idf`, `bootstrap` (all used by the build), `check` (PyYAML 6.0.3 for the check script) |
| `lock/espidf.constraints.v5.5.txt` | ESP-IDF's Python constraints file, vendored |
| `recovery/` | the official 26.9.0 factory image's pinned URL, size and hashes |
| `tools/build.sh`, `esphome_repro.py`, `verify_lock.py`, `pylock.py`, `check_merged.py`, `selftest_check.py`, `make_lock.py`, `negative_test.sh` | how all of the above was made and checked |
| `STATUS.md` | stage status |

Nothing was flashed or installed anywhere. The branch holds no secrets, household data or recordings.
