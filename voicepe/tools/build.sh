#!/usr/bin/env bash
# Clean, reproducible build of the Hey Atlas Voice PE image, with every fetched
# input held to the lock in voicepe/lock/.
#
# Usage: voicepe/tools/build.sh OUT_DIR
#   PYTHON     CPython 3.13 for both virtual environments (default: python3.13)
#   KEEP_WORK  set to 1 to keep OUT_DIR/work (venvs, ESP-IDF, caches) afterwards
#   VOICEPE_LOCK_MODE=record  only for writing a new lock (tools/make_lock.py):
#              logs every fetch without refusing; the output is marked NOT ENFORCED
#
# Everything is built from nothing in OUT_DIR/work, which is deleted first:
#  1. Both Python environments, with pip --require-hashes --no-deps from the
#     hashed requirement files: the ESPHome venv (requirements-esphome.txt) and
#     ESP-IDF's penvs/5.5.5 (requirements-esp-idf.txt, checked against the
#     vendored constraints file). pip and setuptools come first from
#     requirements-bootstrap.txt, so the four sdists build with
#     --no-build-isolation and nothing unhashed is fetched. Each env must then
#     hold exactly the locked packages.
#  2. Vendored inputs (models, base YAML, constraints file) checked against the lock.
#  3. Config and compile run under tools/esphome_repro.py, which refuses any
#     download or request that is not in the lock or whose SHA-256 differs, and
#     uses the env from step 1 instead of ESPHome's own pip/uv install.
#  4. After the config: the git checkout of the external component must be the
#     locked commit and tree. After the compile, before any image is written to
#     OUT_DIR: the ESP component registry components must be exactly the locked
#     set, each with the locked hash recomputed from the files on disk; the IDF
#     tool entries must match; both Python envs must be unchanged.
# Any failure stops the build with a non-zero status and no images in OUT_DIR.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/.." && pwd)
LOCKDIR=$HERE/lock
mkdir -p "$1"
OUT=$(cd "$1" && pwd)
WORK=$OUT/work
PYTHON=${PYTHON:-python3.13}
NAME=atlas-voicepe-hey-atlas-26.9.0-atlas.2

export TZ=UTC
export SOURCE_DATE_EPOCH=1792540800  # 2026-10-21T00:00:00Z, fixed so rebuilds match
export XDG_CACHE_HOME=$WORK/cache    # ESPHome puts ESP-IDF, its tools and penvs/ under esphome/idf here
export PLATFORMIO_CORE_DIR=$WORK/platformio
export VOICEPE_LOCK=$LOCKDIR/dependency-lock.json
export VOICEPE_FETCH_LOG=$OUT/fetch-log.txt
# Overrides that would point ESPHome at other sources or another install
unset ESPHOME_IDF_FRAMEWORK_MIRRORS ESP_IDF_CONSTRAINTS_MIRRORS ESPHOME_ESP_IDF_PREFIX \
  ESPHOME_IDF_DEFAULT_TARGETS ESPHOME_IDF_DEFAULT_TOOLS ESPHOME_IDF_DEFAULT_TOOLS_FORCE \
  ESPHOME_IDF_DEFAULT_FEATURES

rm -rf "$WORK" "$OUT"/*.bin "$OUT/SHA256SUMS" "$OUT/SIZES" "$VOICEPE_FETCH_LOG" "$OUT/NOT-ENFORCED"
mkdir -p "$WORK"
if [ "${VOICEPE_LOCK_MODE:-}" = record ]; then
  echo "RECORD MODE: the lock is NOT enforced; for tools/make_lock.py only" | tee "$OUT/NOT-ENFORCED" >&2
elif [ -n "${VOICEPE_LOCK_MODE:-}" ]; then
  echo "unknown VOICEPE_LOCK_MODE=$VOICEPE_LOCK_MODE" >&2; exit 1
fi

step() { echo "== $*"; }

pyver=$("$PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
case $pyver in 3.13.*) ;; *) echo "need CPython 3.13 (the lock's wheels are cp313), got $pyver" >&2; exit 1 ;; esac
step "host tools (not fetched): python $pyver, $(git --version), $(cmake --version | head -1), ninja $(ninja --version)"

# venv DIR REQUIREMENTS: a new venv holding exactly the hashed artifacts
locked_venv() {
  local pip=("$1/bin/python" -m pip install --no-cache-dir --disable-pip-version-check
             --require-hashes --no-deps --no-build-isolation)
  "$PYTHON" -m venv "$1"
  "${pip[@]}" --force-reinstall -r "$LOCKDIR/requirements-bootstrap.txt"
  "${pip[@]}" -r "$2"
}

step "ESPHome venv from lock/requirements-esphome.txt"
VENV=$WORK/esphome-venv
locked_venv "$VENV" "$LOCKDIR/requirements-esphome.txt"
"$VENV/bin/python" -m pip uninstall --yes --disable-pip-version-check setuptools  # build backend only
PY=$VENV/bin/python
"$PY" -I "$HERE/tools/pylock.py" check "$PY" "$LOCKDIR/requirements-esphome.txt" --allow pip==26.2.1

step "ESP-IDF 5.5.5 Python env from lock/requirements-esp-idf.txt"
PENV=$XDG_CACHE_HOME/esphome/idf/penvs/5.5.5
locked_venv "$PENV" "$LOCKDIR/requirements-esp-idf.txt"
"$PY" -I "$HERE/tools/pylock.py" check "$PENV/bin/python" "$LOCKDIR/requirements-esp-idf.txt" --allow pip==26.2.1
echo "built by tools/build.sh from lock/requirements-esp-idf.txt (sha256 $(sha256sum < "$LOCKDIR/requirements-esp-idf.txt" | cut -c1-64)) with pip --require-hashes --no-deps" > "$PENV/.voicepe-lock"

ver=$("$VENV/bin/esphome" version)
[ "$ver" = "Version: 2026.9.1" ] || { echo "need ESPHome 2026.9.1, got: $ver" >&2; exit 1; }

cd "$HERE"
rm -rf .esphome

step "vendored inputs and constraints against the lock"
"$PY" -I tools/verify_lock.py pre
# idf.py reads the constraints file from IDF_TOOLS_PATH: give it the vendored,
# hash-checked copy (ESPHome would download the unversioned URL).
cp lock/espidf.constraints.v5.5.txt "$XDG_CACHE_HOME/esphome/idf/"

step "config"
"$PY" -I tools/esphome_repro.py config --show-secrets hey-atlas-voice-pe.yaml > "$OUT/merged-config.yaml"
"$PY" -I tools/check_merged.py "$OUT/merged-config.yaml" > "$OUT/check-report.txt" \
  || { cat "$OUT/check-report.txt"; echo "check failed" >&2; exit 1; }
"$PY" -I tools/verify_lock.py git

step "compile"
"$PY" -I tools/esphome_repro.py compile hey-atlas-voice-pe.yaml > "$OUT/build-log.txt" 2>&1 \
  || { tail -50 "$OUT/build-log.txt"; exit 1; }

B=.esphome/build/home-assistant-voice
step "built inputs against the lock"
"$PY" -I tools/verify_lock.py post "$B" "$PENV/bin/python"
"$PY" -I tools/pylock.py check "$PY" "$LOCKDIR/requirements-esphome.txt" --allow pip==26.2.1
"$PY" -I tools/pylock.py check "$PENV/bin/python" "$LOCKDIR/requirements-esp-idf.txt" --allow pip==26.2.1

# Two images, named so they cannot be confused:
#   OTA      = application only; for an over-the-air update. Never write it over USB at 0x0.
#   FACTORY  = bootloader + partition table + otadata + application; for USB at offset 0x0.
cp "$B/build/firmware.ota.bin" "$OUT/$NAME.OTA-app-only.bin"
cp "$B/build/firmware.factory.bin" "$OUT/$NAME.FACTORY-usb-offset-0x0.bin"
cp "$B/partitions.csv" "$B/dependencies.lock" "$B/build_info.json" "$OUT/"
cp "$B/sdkconfig.home-assistant-voice" "$OUT/sdkconfig.txt"

# Memory and size report: ESP-IDF's summary (from the log) plus the largest archives.
{
  echo "# idf.py size summary (from the build log)"
  sed 's/\x1b\[[0-9;]*[A-Za-z]//g' "$OUT/build-log.txt" | sed -n '/Memory Type\/Section/,/Flash: \[/p'
  echo
  echo "# Largest 25 archives (esp_idf_size --archives)"
  "$PENV/bin/python" -m esp_idf_size --archives --format text "$B/build/home-assistant-voice.map" > "$OUT/.archives.txt" 2>&1
  sed 's/\x1b\[[0-9;]*[A-Za-z]//g' "$OUT/.archives.txt" | sed -n '1,32p'
  rm -f "$OUT/.archives.txt"
} > "$OUT/memory-report.txt"

[ "${KEEP_WORK:-0}" = 1 ] || rm -rf "$WORK"
(cd "$OUT" && sha256sum "$NAME".*.bin > SHA256SUMS && stat -c '%s %n' "$NAME".*.bin > SIZES)
cat "$OUT/SHA256SUMS" "$OUT/SIZES"
