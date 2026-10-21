# Recovery image: official Voice PE 26.9.0

The way back to stock is the official 26.9.0 factory image, flashed over USB.
The binary is **not committed**: it is Nabu Casa / ESPHome's release (ESPHome core is GPL-3.0, the sounds CC BY 4.0, the models Apache-2.0), it is published on two official hosts, and a pinned URL plus its hash is enough. This folder holds only the published hash files and the release manifest.

## Pinned file

| | |
| --- | --- |
| URL (GitHub release asset) | https://github.com/esphome/home-assistant-voice-pe/releases/download/26.9.0/home-assistant-voice-esp32s3.factory.bin |
| Mirror (official OTA host, versioned path) | https://firmware.esphome.io/home-assistant-voice-pe/home-assistant-voice/26.9.0/home-assistant-voice-esp32s3.factory.bin |
| Size | **3,315,584 bytes** (as expected) |
| SHA-256, measured here | `98b7e304e6e91335384a66eaa73aa2bd2dd43c55460cce8694d40e6a7fb9d9da` |
| SHA-256, published (`home-assistant-voice-esp32s3.factory.bin.sha256`, release asset) | `98b7e304e6e91335384a66eaa73aa2bd2dd43c55460cce8694d40e6a7fb9d9da`: **match** |
| SHA-256 in the firmware.esphome.io 26.9.0 manifest | `98b7e304e6e91335384a66eaa73aa2bd2dd43c55460cce8694d40e6a7fb9d9da`: **match** |
| MD5, measured / published | `caa37bc133319f4a6d4423b5d7fc7f88` / `caa37bc133319f4a6d4423b5d7fc7f88`: **match** |
| Built from | tag 26.9.0 = commit `2644f4c794271d735d182ca7ebf899ed46164f4e`, with ESPHome **2026.6.0** (the repo's `.github/workflows/build.yml` at that commit sets `esphome-version: 2026.6.0`) |

Both downloads (GitHub and firmware.esphome.io) were byte-identical. The official OTA (app-only) image is 3,250,048 bytes, SHA-256 `557651452f49f335bc38e7dbed793547e535ee920b660fcbe860a2e3f1d1a842` (published `.sha256` and manifest match).

Files here: `home-assistant-voice-esp32s3.factory.bin.sha256`, `.factory.bin.md5`, `.ota.bin.sha256` (the release's own hash files, unmodified), and `firmware.esphome.io-26.9.0-manifest.json` (the versioned manifest, unmodified).

Do not use the unversioned `.../home-assistant-voice/manifest.json`. It moves to each new release.

## Flash layout facts (measured from this image)

| Region | Offset | Size | In the 3.3 MB image? |
| --- | --- | --- | --- |
| bootloader | 0x0 | | yes |
| partition table | 0x8000 | | yes |
| otadata | 0x9000 | 0x2000 | yes, as 0xFF (boot from app0) |
| phy_init | 0xB000 | 0x1000 | yes, as 0xFF |
| app0 | 0x10000 | 0x7C0000 | yes |
| app1 | 0x7D0000 | 0x7C0000 | no |
| **nvs** (Wi-Fi, HA API key, settings) | **0xF90000** | 0x70000 | **no** |

So writing this image at 0x0 **without erasing** leaves NVS alone: the device keeps its Wi-Fi and its Home Assistant pairing. ESPHome Web's "Install" with an uploaded file always erases first, which clears NVS too (see the main README).

## How to recover (Windows PC, Chrome or Edge, no installs)

**First choice, keeps pairing: the official installer pinned to 26.9.0.**
1. Connect the Voice PE to the PC with a USB-C data cable.
2. Open https://esphome.github.io/home-assistant-voice-pe/?version=26.9.0 (the `?version=` parameter makes the page use the versioned manifest `firmware.esphome.io/.../26.9.0/manifest.json`; `static/index.html` at 2644f4c).
3. Click Connect and pick the port. The page loads esp-web-tools 10.4.0. It reads the device over Improv Serial; the Atlas image reports the stock project name `Nabu Casa.Home Assistant Voice PE`. So the page offers **"Update Nabu Casa.Home Assistant Voice PE"**, which installs **without erasing** (esp-web-tools `install-dialog.js`: `if (this._isSameFirmware) this._startInstall(false)`, where `_isSameFirmware` is `info.firmware === manifest.name`). Wi-Fi, the Home Assistant key and the settings stay.
4. If the page offers "Install" instead of "Update" (for example, Improv did not answer), that path **erases** the flash. You can accept that (then see "after an erase" below), or use the manual route.

**Manual route, also keeps pairing.**
1. Download the factory image from the URL above. Check it in PowerShell: `Get-FileHash .\home-assistant-voice-esp32s3.factory.bin -Algorithm SHA256` must print `98B7E304E6E91335384A66EAA73AA2BD2DD43C55460CCE8694D40E6A7FB9D9DA`.
2. Open https://espressif.github.io/esptool-js/, Connect, and pick the port.
3. Add one file row: offset `0x0`, this file. Leave mode, frequency and size on "keep". Click **Program**. Do **not** click "Erase Flash".

**Full reset (erases everything).** On https://web.esphome.io: Connect, Install, choose the file. ESPHome Web always erases first when you upload a file (`web.esphome.io/src/install-upload/install-upload-dialog.ts`: `erase: true`).

**After an erase:** connect Wi-Fi with ESPHome Web's "Configure Wi-Fi" (Improv Serial) or over BLE from the Home Assistant app. Home Assistant then raises a re-authentication for the device ("disabled transport encryption … confirm that you want to remove the encryption key"). Confirm it. On the next connect, Home Assistant provisions a key again (its stored key for this device if it has one, otherwise a new one). The device entry, its area and its pipeline stay, because they belong to the same config entry. On-device settings (volume, sensitivity, LED, chosen wake word) return to defaults.

After recovery to stock, the stock firmware offers its own update channel again (the "Firmware" update entity in Home Assistant).
