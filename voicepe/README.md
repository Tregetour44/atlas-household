# Voice PE with an on-device "Hey Atlas" wake word

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
* Whether this unit enters download mode through esptool-js without pressing a button.
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

If step 4 cannot connect or does not reach the ESP32-S3 (NO DATA for this unit), stop. Do not try ESPHome Web unless a full wipe is acceptable. Use route C instead:

```
py -3.13 -m venv %USERPROFILE%\esphome-2026.9.1
%USERPROFILE%\esphome-2026.9.1\Scripts\pip install esphome==2026.9.1
cd atlas-household\voicepe
%USERPROFILE%\esphome-2026.9.1\Scripts\esphome upload hey-atlas-voice-pe.yaml --device <device IP from Home Assistant> --file images\atlas-voicepe-hey-atlas-26.9.0-atlas.1.OTA-app-only.bin
```

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
| `build/build-log.txt`, `build/build-log-repro.txt` | logs of the two clean builds |
| `build/README.md` | sizes, memory, partitions and reproducibility |
| `build/memory-report.txt`, `partitions.csv`, `dependencies.lock`, `sdkconfig.txt`, `build_info.json` | build outputs |
| `images/` | the two images, `SHA256SUMS`, `SIZES` |
| `lock/dependency-lock.json` | every fetched input with its hash |
| `recovery/` | the official 26.9.0 factory image's pinned URL, size and hashes |
| `tools/build.sh`, `esphome_repro.py`, `check_merged.py`, `selftest_check.py`, `make_lock.py` | how all of the above was made |
| `STATUS.md` | stage status |

Nothing was flashed or installed anywhere. The branch holds no secrets, household data or recordings.
