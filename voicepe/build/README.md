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

### Lock fix round, 2026-10-22: two clean builds with the enforced lock

Both builds ran `tools/build.sh` at commit `bbcea96` from nothing: new venvs, an empty ESP-IDF/PlatformIO/component cache (`OUT/work`), and `voicepe/.esphome` wiped.

| | Build A | Build B |
| --- | --- | --- |
| Source | this working tree | fresh `git clone`, checked out at `bbcea96`, other directory |
| `tools/build.sh` output (pip installs, every lock check) | `lock-enforced-build-A.txt` | `lock-enforced-build-B.txt` |
| ESPHome compile log | `build-log.txt` | `build-log-repro.txt` |
| Requests and downloads (fetch log) | `fetch-log-A.txt`: 84 entries, 40 files hashed, no violation | `fetch-log-B.txt`: the same 84 entries in another order (parallel downloads) |
| Factory image SHA-256 | `694a8948…4f6de9` | `694a8948…4f6de9` (`SHA256SUMS-repro`) |
| OTA image SHA-256 | `698f55d9…0d55c6a0` | `698f55d9…0d55c6a0` |

**Both equal the reviewed images byte for byte** (`cmp` against `../images/`). So the images are unchanged.

The other outputs were refreshed from build A:
* `check-report.txt`, `partitions.csv`, `build_info.json`, `dependencies.lock` and `memory-report.txt` are identical to the previous round's.
* `merged-config.yaml` has the same lines. Only `gain_factor` and `bits_per_sample` swap places in the two `voice_assistant` microphone entries. That order changes from run to run (A and B differ the same way), it does not reach the image, and the check report is identical.
* `sdkconfig.txt` has the same lines; only the order of the menu sections differs, as before (component discovery order). A and B are byte-identical.

### First round, 2026-10-21

Two clean builds (working tree; fresh clone at `1ee537a` with a new venv and an empty cache) gave the same SHA-256s as above, with unhashed Python environments.

### What makes the build reproducible

* **Build timestamp.** ESPHome 2026.9.1 writes `time.time()` into every image (`esphome/writer.py`, `get_build_info`), so two plain builds always differ in those bytes. `tools/esphome_repro.py` replaces only that function, using `SOURCE_DATE_EPOCH` = 1792540800 (2026-10-21 00:00:00 UTC, set in `tools/build.sh`). On the device this value is only shown as the compilation time and used as a lower bound for the clock. ESP-IDF's `CONFIG_APP_REPRODUCIBLE_BUILD` is already set by ESPHome, which strips paths and dates. ESPHome's `config_hash` is computed from relative paths, so the build directory does not matter.
* `dependencies.lock` (ESP component manager): the same components, versions and component hashes in every build. Only `manifest_hash` changes with the checkout directory, because the manifest includes the absolute local paths of three PlatformIO libraries.

## Lock enforcement

The review found that the ESP-IDF Python environment (34 packages, among them esptool 4.12.0) had versions but no artifact hashes, that its constraints file came from a mutable URL, and that `tools/build.sh` did not enforce the lock. Now every fetched input is hashed and checked before the compile, or, for the registry components that are downloaded inside the compile, before any image is written.

| Input | Locked as | Enforced by |
| --- | --- | --- |
| ESPHome venv, 83 packages + pip | `lock/requirements-esphome.txt`: one SHA-256 per package, the exact wheel or sdist (Linux x86_64, CPython 3.13) | `pip install --require-hashes --no-deps --no-build-isolation` into a new venv; then `tools/pylock.py check`: exactly these packages and versions, nothing else (before and after the compile) |
| ESP-IDF Python env (`penvs/5.5.5`), 60 packages + pip, incl. esptool 4.12.0 (sdist) | `lock/requirements-esp-idf.txt`, same form | the same, built by `build.sh` before ESPHome starts. `esphome_repro.py` replaces ESPHome's env step (pip or uv `--upgrade` from the online constraints) and accepts only this env |
| pip, setuptools | `lock/requirements-bootstrap.txt` | installed first into both venvs, hash-checked. pip from PyPI replaces the system Python's bundled copy, whose wheel differs. setuptools builds the four sdists (crcmod, esptool 5.3.1, esptool 4.12.0, paho-mqtt) without build isolation, so pip fetches nothing unhashed; it is then removed from the ESPHome venv, as in the first round's env |
| ESP-IDF constraints file | vendored `lock/espidf.constraints.v5.5.txt`, SHA-256 `6b53b3657a924b8ba10c5e4eea0628e1675d2dadb7b2f9ecc48c8d130a117aa1` (3,766 B; the URL still serves the same bytes) | hash-checked, then copied to where idf.py reads it. The URL is never fetched. Every ESP-IDF pin is checked against it (16 constrained packages) |
| ESP-IDF 5.5.5 tarball, 2 tool archives, 16 sounds, XMOS firmware, 3 PlatformIO library archives | `fetch_allowlist.artifacts` in `lock/dependency-lock.json` (23 URLs with SHA-256). Each equals the hash recorded independently in the lock's own section; `verify_lock.py pre` checks that both agree | `esphome_repro.py` hashes every file ESPHome downloads (`framework_helpers.download_with_resume`, `external_files.download_content`) and stops the build with status 97 unless the URL is a lock artifact with that SHA-256 |
| Any other request ESPHome makes | `fetch_allowlist.queries`: 3 PlatformIO registry lookups and PlatformIO's internet check, each with its reason | `esphome_repro.py` wraps `requests.Session.request` and stops the build on any URL that is not an artifact or a listed query |
| voice_kit external component (git) | repo, commit `2644f4c`, `voice_kit` tree id | `verify_lock.py git` after the config: one checkout, that remote, HEAD and tree, no local change |
| 12 ESP component registry components | name, version, component hash (`idf_components`) | `verify_lock.py post`: `dependencies.lock` equals the lock, `managed_components/` holds exactly these 12, and each one's files hash to the locked value (the component manager's own `validate_hash_eq_hashdir`) |
| Toolchain entries in tools.json | URL, SHA-256, size | `verify_lock.py post`; idf_tools.py and ESPHome also check the archive hashes against tools.json, which comes from the hashed tarball |
| Models, base YAML | SHA-256 | `verify_lock.py pre` |

Host tools that are not fetched are logged at the start of each build: Python 3.13.16, git 2.43.0, cmake 3.28.3, ninja 1.11.1.

**Negative tests** (`negative-test-log.txt`, from `tools/negative_test.sh`). Each test clones the branch, changes one hash's last digit and runs `build.sh`:

| Changed hash | Where the build stopped | Exit, images |
| --- | --- | --- |
| esptool 4.12.0 in `requirements-esp-idf.txt` | ESP-IDF env install: pip "THESE PACKAGES DO NOT MATCH THE HASHES … Expected sha256 …1030, Got …103c" | 1, none |
| ESP-IDF tarball in `dependency-lock.json` | compile, right after the download: "LOCK VIOLATION: …esp-idf-v5.5.5.tar.xz has SHA-256 …769a, the lock says …7690" | 1, none |
| espressif/esp-nn component hash in `dependency-lock.json` | after the compile (27 min), before any image is copied: `verify_lock.py post`, 2 checks FAIL (esp-nn's `dependencies.lock` entry, and its files' hash: `HashNotEqualError`) | 1, none |

## Other files

* `merged-config.yaml`: the full merged config (`esphome config --show-secrets`; there are no secrets in it).
* `check-report.txt`: `tools/check_merged.py` on it, 84/84 pass.
* `check-selftest.txt`: the check script fails, as it should, on nine broken variants (update channel added, HTTP OTA added, hey_atlas twice, okay_nabu dropped, second Assist start, voice_kit on dev, a sound on dev, an API key in the image, mute gate removed).
* `build_info.json`, `sdkconfig.txt`, `dependencies.lock`, `partitions.csv`: copied from the build directory.

To rebuild (Linux x86_64 with CPython 3.13, git, cmake and ninja; about 30 minutes on 4 cores; 3 GB in `OUT_DIR/work`, deleted afterwards): `voicepe/tools/build.sh OUT_DIR`, then compare `OUT_DIR/SHA256SUMS` with `../images/SHA256SUMS`. Network is needed for PyPI, the git clone of the voice_kit component, the sounds, the XMOS firmware, ESP-IDF and its tools, and the IDF and PlatformIO components. All of these are checked against `../lock/` as described above.
