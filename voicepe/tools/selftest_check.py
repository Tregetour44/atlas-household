"""Mutation self-test for check_merged.py: each broken config must fail.

Usage: python -I voicepe/tools/selftest_check.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
MERGED = TOOLS.parent / "build" / "merged-config.yaml"

UPDATE_CHANNEL = """
update:
  - platform: http_request
    id: update_http_request
    source: https://firmware.esphome.io/home-assistant-voice-pe/home-assistant-voice/manifest.json
"""

MUTATIONS = {
    "stock HTTP update channel added": lambda t: t + UPDATE_CHANNEL,
    "HTTP OTA platform added": lambda t: t.replace(
        "ota:\n  - platform: esphome\n", "ota:\n  - platform: http_request\n    id: ota_http_request\n  - platform: esphome\n", 1),
    "hey_atlas listed twice": lambda t: t.replace(
        "      id: hey_atlas\n", "      id: hey_atlas\n      internal: false\n    - model:\n        path: models/hey_atlas/hey_atlas.json\n        type: local\n      id: hey_atlas\n", 1),
    "stock okay_nabu dropped": lambda t: t.replace("      id: okay_nabu\n", "      id: okay_nabu_x\n", 1),
    "second Assist start in the wake handler": lambda t: t.replace(
        "  on_wake_word_detected:\n    then:\n", "  on_wake_word_detected:\n    then:\n      - voice_assistant.start: {}\n", 1),
    "voice_kit back on dev": lambda t: t.replace("      ref: 2644f4c794271d735d182ca7ebf899ed46164f4e\n", "      ref: dev\n", 1),
    "sound back on dev": lambda t: t.replace("2644f4c794271d735d182ca7ebf899ed46164f4e/sounds/jack_connected.flac", "dev/sounds/jack_connected.flac"),
    "API key in the image": lambda t: t.replace("  encryption: {}\n", "  encryption:\n    key: PLACEHOLDER_NOT_A_REAL_KEY\n", 1),
    "mute gate removed": lambda t: t.replace("              id: master_mute_switch\n          then:", "              id: wake_sound\n          then:", 1),
}


def run(path: Path) -> int:
    return subprocess.run([sys.executable, "-I", str(TOOLS / "check_merged.py"), str(path)],
                          capture_output=True, text=True).returncode


def main() -> int:
    text = MERGED.read_text()
    ok = run(MERGED) == 0
    print(f"{'PASS' if ok else 'FAIL'}  unmodified merged config passes")
    with tempfile.TemporaryDirectory() as tmp:
        for name, mutate in MUTATIONS.items():
            mutated = mutate(text)
            assert mutated != text, f"mutation '{name}' did not apply"
            p = Path(tmp) / "m.yaml"
            p.write_text(mutated)
            caught = run(p) != 0
            ok &= caught
            print(f"{'PASS' if caught else 'FAIL'}  check fails when: {name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
