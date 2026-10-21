#!/usr/bin/env bash
# Clean, reproducible build of the Hey Atlas Voice PE image.
#
# Usage: ESPHOME=/path/to/venv/bin/esphome voicepe/tools/build.sh OUT_DIR
#   ESPHOME  the esphome 2026.9.1 CLI (default: esphome on PATH)
#
# Steps: wipe voicepe/.esphome, write the merged config, run the check script
# (stops on any failure), compile with the build time fixed, then copy the two
# images, the partition table, the IDF dependency lock, the sdkconfig, the
# memory report and SHA-256s into OUT_DIR.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$1"
OUT=$(cd "$1" && pwd)
ESPHOME=${ESPHOME:-esphome}
PY=$(dirname "$(command -v "$ESPHOME")")/python
NAME=atlas-voicepe-hey-atlas-26.9.0-atlas.1

export TZ=UTC
export SOURCE_DATE_EPOCH=1792540800  # 2026-10-21T00:00:00Z, fixed so rebuilds match

ver=$("$ESPHOME" version)
[ "$ver" = "Version: 2026.9.1" ] || { echo "need ESPHome 2026.9.1, got: $ver" >&2; exit 1; }

cd "$HERE"
rm -rf .esphome

"$ESPHOME" config --show-secrets hey-atlas-voice-pe.yaml > "$OUT/merged-config.yaml"
"$PY" -I tools/check_merged.py "$OUT/merged-config.yaml" > "$OUT/check-report.txt" \
  || { cat "$OUT/check-report.txt"; echo "check failed" >&2; exit 1; }

"$PY" -I tools/esphome_repro.py compile hey-atlas-voice-pe.yaml > "$OUT/build-log.txt" 2>&1 \
  || { tail -50 "$OUT/build-log.txt"; exit 1; }

B=.esphome/build/home-assistant-voice
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
  IDFPY=$(ls -d "${XDG_CACHE_HOME:-$HOME/.cache}"/esphome/idf/penvs/*/bin/python | head -1)
  "$IDFPY" -m esp_idf_size --archives --format text "$B/build/home-assistant-voice.map" > "$OUT/.archives.txt" 2>&1
  sed 's/\x1b\[[0-9;]*[A-Za-z]//g' "$OUT/.archives.txt" | sed -n '1,32p'
  rm -f "$OUT/.archives.txt"
} > "$OUT/memory-report.txt"

(cd "$OUT" && sha256sum "$NAME".*.bin > SHA256SUMS && stat -c '%s %n' "$NAME".*.bin > SIZES)
cat "$OUT/SHA256SUMS" "$OUT/SIZES"
