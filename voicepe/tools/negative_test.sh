#!/usr/bin/env bash
# Negative tests for the enforced lock. Each test changes one locked hash in a
# throwaway clone of the committed branch, runs tools/build.sh there, and
# passes only if the build refuses: non-zero exit status and no image written.
#
# Usage: voicepe/tools/negative_test.sh WORK_DIR [TEST ...]   (default: all tests)
#   pip-hash        esptool 4.12.0's hash in requirements-esp-idf.txt (pip must refuse)
#   framework-hash  the ESP-IDF 5.5.5 tarball's hash in dependency-lock.json (the guard must refuse the download)
#   component-hash  espressif/esp-nn's component hash in dependency-lock.json (the post-compile check must refuse)
set -uo pipefail

REPO=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$1"
W=$(cd "$1" && pwd)
shift
if [ $# -gt 0 ]; then TESTS=("$@"); else TESTS=(pip-hash framework-hash component-hash); fi
HEAD=$(git -C "$REPO" rev-parse HEAD)

# mutate FILE OLD NEW COUNT: replace OLD by NEW, which must occur exactly COUNT times
mutate() {
  python3 -I - "$@" <<'EOF'
import sys
path, old, new, count = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
text = open(path).read()
assert text.count(old) == count, f"{old} occurs {text.count(old)} times in {path}, expected {count}"
open(path, "w").write(text.replace(old, new))
EOF
}

failed=0
for t in "${TESTS[@]}"; do
  case $t in
    pip-hash)       file=voicepe/lock/requirements-esp-idf.txt; n=1
                    old=d797f6529d582173508baf0572542ddadf53aae8c92c84ea9f420f242464103c ;;
    framework-hash) file=voicepe/lock/dependency-lock.json; n=2  # esp_idf and fetch_allowlist
                    old=d8696df2173146775ac4e5c00cf63ee86c7e04c231530db40f34a4362cbe769a ;;
    component-hash) file=voicepe/lock/dependency-lock.json; n=1
                    old=f4633a02f05fef53b80de65ade1f733ebdef637e4c8b8be4eb11f5e27f6d9f3e ;;
    *) echo "unknown test $t" >&2; exit 2 ;;
  esac
  new=${old:0:63}$( [ "${old:63}" = 0 ] && echo 1 || echo 0 )  # change the last hex digit
  dir=$W/$t
  rm -rf "$dir"
  git clone -q "$REPO" "$dir/src" && git -C "$dir/src" checkout -q "$HEAD"
  echo "######## test $t: branch commit ${HEAD:0:12}, one hash changed in $file"
  mutate "$dir/src/$file" "$old" "$new" "$n" || exit 2
  git -C "$dir/src" diff --stat
  git -C "$dir/src" diff -U0 | grep '^[-+] *\(--hash\|"sha256\|"component_hash\)'
  start=$(date +%s)
  "$dir/src/voicepe/tools/build.sh" "$dir/out" > "$dir/build-output.txt" 2>&1
  status=$?
  images=$(find "$dir/out" -maxdepth 1 -name '*.bin' | wc -l)
  echo "-- build.sh exit status $status after $(( $(date +%s) - start )) s; images written to OUT: $images"
  echo "-- where it stopped (last step and the refusal):"
  grep '^== ' "$dir/build-output.txt" | tail -1
  grep -h -A3 'THESE PACKAGES DO NOT MATCH\|LOCK VIOLATION\|^FAIL' "$dir/build-output.txt" "$dir/out/build-log.txt" 2>/dev/null \
    | grep -v '^--$' | head -12
  if [ "$status" -ne 0 ] && [ "$images" -eq 0 ]; then
    echo "PASS  $t: the build refused"
  else
    echo "FAIL  $t: the build did not refuse"; failed=1
  fi
  rm -rf "$dir/out/work" "$dir/src/voicepe/.esphome"
  echo
done
exit $failed
