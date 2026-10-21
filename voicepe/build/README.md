# Build record

Built on 2026-10-21 in a Linux cloud container (x86_64, 4 cores) with ESPHome **2026.9.1** from PyPI, ESPHome's native ESP-IDF toolchain, and ESP-IDF **5.5.5**.

## Images (`../images/`)

| File | Use | Size (bytes) | SHA-256 |
| --- | --- | --- | --- |
| `atlas-voicepe-hey-atlas-26.9.0-atlas.1.FACTORY-usb-offset-0x0.bin` | **USB**, written at offset **0x0** (bootloader + partition table + otadata + app) | 3,322,192 | `694a8948fc44b47731e596922936d6e0845435f8058015d0a97164cf1b4f6de9` |
| `atlas-voicepe-hey-atlas-26.9.0-atlas.1.OTA-app-only.bin` | **OTA only** (application). Never write it over USB at 0x0: there is no bootloader in it. | 3,256,656 | `698f55d9acc103e015cc2437856359d32547290c946870d03239629c0d55c6a0` |

The factory image is the OTA image placed at 0x10000, behind the bootloader (0x0), the partition table (0x8000) and blank otadata. It ends at 0x32B150, far below NVS at 0xF90000.

## Size, memory and partitions

* Application: 3,256,539 bytes used of the 8,126,464-byte app slot (**40.1%**). Stock 26.9.0's app image is 3,250,048 bytes, so ours is 6,608 bytes larger. The Hey Atlas model adds 69,624 bytes; the rest of the difference comes from ESPHome 2026.9.1 versus 2026.6.0.
* Internal RAM (DIRAM), static: 174,759 of 341,760 bytes (51.1%). Model tensor arenas are allocated at run time by ESPHome's `RAMAllocator`, which prefers PSRAM. ESPHome 2026.9.1 probes each model's real arena size at load (`streaming_model.cpp`: log line "Probed tensor arena size: … bytes"); the manifest's 38,912 B for Hey Atlas is only the fallback. On-device use: **NO DATA**.
* Full report: `memory-report.txt` (idf.py size summary plus the largest archives).
* `partitions.csv`: app0 0x10000 / app1 0x7D0000 (0x7C0000 each), otadata 0x9000, phy_init 0xB000, nvs 0xF90000 (0x70000). **The partition-table sector (0x8000–0x8FFF) is byte-identical to the official 26.9.0 factory image**, checked byte for byte. So an OTA from stock, or a USB write without erase, leaves NVS (Wi-Fi, API key, settings) where the firmware expects it. The bootloader bytes differ from stock (ESP-IDF 5.5.5 here). An OTA does not replace the bootloader; a USB factory write does.

## Reproducibility

Two clean builds gave **the same SHA-256 for both images**:

| | Build A | Build B |
| --- | --- | --- |
| Source | this working tree, `voicepe/.esphome` wiped | fresh `git clone` of this branch at `1ee537a`, other directory |
| ESPHome | venv from PyPI | **new** venv, `pip install --no-cache-dir esphome==2026.9.1` |
| ESP-IDF, toolchain, IDF Python env | cache from an earlier build | **empty** cache (`XDG_CACHE_HOME` set to a new directory): everything downloaded again |
| Log | `build-log.txt` | `build-log-repro.txt` |
| Factory image SHA-256 | `694a8948…4f6de9` | `694a8948…4f6de9` (`SHA256SUMS-repro`) |
| OTA image SHA-256 | `698f55d9…0d55c6a0` | `698f55d9…0d55c6a0` |

What made it reproducible, and the remaining differences:

* **Build timestamp.** ESPHome 2026.9.1 writes `time.time()` into every image (`esphome/writer.py`, `get_build_info`), so two plain builds always differ in those bytes. `tools/esphome_repro.py` replaces only that function, using `SOURCE_DATE_EPOCH` = 1792540800 (2026-10-21 00:00:00 UTC, set in `tools/build.sh`). On the device this value is only shown as the compilation time and used as a lower bound for the clock. Everything else is ESPHome's normal compile. ESP-IDF's `CONFIG_APP_REPRODUCIBLE_BUILD` is already set by ESPHome, which strips paths and dates. ESPHome's `config_hash` is computed from relative paths, so the build directory does not matter.
* `dependencies.lock` (ESP component manager): the same components, versions and component hashes in both builds. Only `manifest_hash` differs, because the manifest includes the absolute local paths of three PlatformIO libraries.
* `sdkconfig.txt`: the same set of options; only the order of the menu sections differs (component discovery order).
* `merged-config.yaml`: identical apart from the absolute paths of the local model files.

## Other files

* `merged-config.yaml`: the full merged config (`esphome config --show-secrets`; there are no secrets in it).
* `check-report.txt`: `tools/check_merged.py` on it, 84/84 pass.
* `check-selftest.txt`: the check script fails, as it should, on nine broken variants (update channel added, HTTP OTA added, hey_atlas twice, okay_nabu dropped, second Assist start, voice_kit on dev, a sound on dev, an API key in the image, mute gate removed).
* `build_info.json`, `sdkconfig.txt`, `dependencies.lock`, `partitions.csv`: copied from the build directory.

To rebuild: `ESPHOME=/path/to/venv/bin/esphome voicepe/tools/build.sh OUT_DIR`, then compare `OUT_DIR/SHA256SUMS` with `../images/SHA256SUMS`. Network is needed for the git clone of the voice_kit component, the sounds, the XMOS firmware, ESP-IDF and its tools, and the IDF and PlatformIO components. All of these are listed with hashes in `../lock/dependency-lock.json`.

**Drift note.** ESPHome pins every direct IDF component and library to an exact version. The resolution actually used is in `dependencies.lock`. Two inputs are not version-addressed: ESP-IDF's Python constraints file (`espidf.constraints.v5.5.txt`, an unversioned URL) and the IDF Python environment it produces. Both are recorded in the lock (hash and `pip freeze`). They affect build tools, not the image.
