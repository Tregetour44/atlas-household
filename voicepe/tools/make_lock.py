"""Write voicepe/lock/dependency-lock.json: every fetched input of the build, with hashes.

Usage (needs network):
  VOICEPE_LOCK_MODE=record KEEP_WORK=1 voicepe/tools/build.sh OUT
  OUT/work/esphome-venv/bin/python -I voicepe/tools/make_lock.py OUT

Each fetched URL is downloaded again here and hashed, and where the source
publishes its own hash (the PlatformIO registry, ESP-IDF tools.json, the ESP
component registry, git object ids) that is recorded too, and compared where
the two can be compared. The Python packages come from the hashed requirement
files in voicepe/lock/ (written by tools/pylock.py). fetch_allowlist, which
tools/esphome_repro.py enforces, is built from OUT/fetch-log.txt: every file
ESPHome downloaded becomes an artifact only if its SHA-256 equals the one
recorded independently in the sections below; every other request becomes a
metadata query.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

VOICEPE = Path(__file__).resolve().parent.parent
RELEASE_SHA = "2644f4c794271d735d182ca7ebf899ed46164f4e"
MWW_MODELS_SHA = "05b65922cc433c9df13e98e32a7fe520758c837e"
IDF_VERSION = "5.5.5"
IDF_URL = f"https://github.com/esphome-libs/esp-idf/releases/download/v{IDF_VERSION}/esp-idf-v{IDF_VERSION}.tar.xz"
IDF_CONSTRAINTS_URL = "https://dl.espressif.com/dl/esp-idf/espidf.constraints.v5.5.txt"
IDF_TOOLS = {"xtensa-esp-elf": "esp-14.2.0_20260121", "esp-rom-elfs": "20241011"}
PIO_LIBRARIES = [("improv", "Improv", "1.2.7"), ("esphome", "noise-c", "0.1.30"), ("esphome", "libsodium", "1.10021.11")]
SOUND_FILES = [
    "jack_connected.flac", "jack_disconnected.flac", "mute_switch_on.flac", "mute_switch_off.flac",
    "timer_finished.flac", "wake_word_triggered.flac", "center_button_press.flac",
    "center_button_double_press.flac", "center_button_triple_press.flac", "center_button_long_press.flac",
    "factory_reset_initiated.mp3", "factory_reset_cancelled.mp3", "factory_reset_confirmed.mp3",
    "easter_egg_tick.mp3", "easter_egg_tada.mp3", "error_cloud_expired.mp3",
]
XMOS_URL = "https://github.com/esphome/voice-kit-xmos-firmware/releases/download/v1.3.1/ffva_v1.3.1_upgrade.bin"
MODEL_SOURCES = {
    "models/stock/okay_nabu_20241226.3/okay_nabu.json": "https://github.com/kahrendt/microWakeWord/releases/download/okay_nabu_20241226.3/okay_nabu.json",
    "models/stock/okay_nabu_20241226.3/okay_nabu.tflite": "https://github.com/kahrendt/microWakeWord/releases/download/okay_nabu_20241226.3/okay_nabu.tflite",
    "models/stock/stop/stop.json": "https://github.com/kahrendt/microWakeWord/releases/download/stop/stop.json",
    "models/stock/stop/stop.tflite": "https://github.com/kahrendt/microWakeWord/releases/download/stop/stop.tflite",
}
for _m in ("hey_jarvis", "hey_mycroft", "vad"):
    for _ext in ("json", "tflite"):
        MODEL_SOURCES[f"models/stock/micro-wake-word-models/{_m}.{_ext}"] = (
            f"https://raw.githubusercontent.com/esphome/micro-wake-word-models/{MWW_MODELS_SHA}/models/v2/{_m}.{_ext}"
        )
MODEL_SOURCES["models/hey_atlas/hey_atlas.json"] = "git: Tregetour44/atlas-household branch wakeword-hey-atlas (commit fde53232dd583cfc64c727adfd40a2c0e679e511) with probability_cutoff 0.93 -> 0.90 (branch voicepe-hey-atlas-v2), hey_atlas.json"
MODEL_SOURCES["models/hey_atlas/hey_atlas.tflite"] = "git: Tregetour44/atlas-household branch wakeword-hey-atlas (commit fde53232dd583cfc64c727adfd40a2c0e679e511) with probability_cutoff 0.93 -> 0.90 (branch voicepe-hey-atlas-v2), hey_atlas.tflite"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=600) as resp:
        return resp.read()


def fetch_hash(url: str) -> dict:
    """Stream a download and return its sha256 and size."""
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(url, timeout=1800) as resp:
        while chunk := resp.read(1 << 20):
            h.update(chunk)
            size += len(chunk)
    return {"url": url, "sha256": h.hexdigest(), "size": size}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def read_req(path: Path) -> list[dict]:
    """A hashed requirement file (format written by pylock.py) as [{url, name, version, sha256}]."""
    pattern = r"^# (\S+)\n([A-Za-z0-9_.\-]+)==(\S+) \\\n    --hash=sha256:([0-9a-f]{64})$"
    return [{"url": m[1], "name": m[2], "version": m[3], "sha256": m[4]}
            for m in re.finditer(pattern, path.read_text(), re.M)]


def python_envs() -> dict:
    envs = {}
    for env, stem in (("bootstrap", "bootstrap"), ("esphome", "esphome"), ("esp_idf", "esp-idf")):
        rel = f"lock/requirements-{stem}.txt"
        envs[env] = {"requirements": f"voicepe/{rel}", "packages": read_req(VOICEPE / rel)}
    return envs


def main() -> int:
    build_out = Path(sys.argv[1]).resolve()
    esphome_dir = VOICEPE / ".esphome"
    idf_root = build_out / "work" / "cache" / "esphome" / "idf"
    lock: dict = {"about": __doc__.strip().splitlines()[0]}

    # ESPHome and its Python environment
    import esphome.const

    lock["esphome"] = {"version": esphome.const.__version__, "install": "pip install esphome==2026.9.1"}
    lock["python_environments"] = python_envs()

    # Base YAML and external component: a git checkout at the release commit
    ext_dirs = [p for p in (esphome_dir / "external_components").iterdir() if p.is_dir()]
    assert len(ext_dirs) == 1, ext_dirs
    repo = ext_dirs[0]
    head = git(repo, "rev-parse", "HEAD")
    assert head == RELEASE_SHA, head
    base_blob = git(repo, "rev-parse", f"{RELEASE_SHA}:home-assistant-voice.yaml")
    lock["upstream_voice_pe"] = {
        "repo": "https://github.com/esphome/home-assistant-voice-pe",
        "tag": "26.9.0",
        "commit": head,
        "home-assistant-voice.yaml_blob": base_blob,
        "home-assistant-voice.factory.yaml_blob": git(repo, "rev-parse", f"{RELEASE_SHA}:home-assistant-voice.factory.yaml"),
        "esphome/components/voice_kit_tree": git(repo, "rev-parse", f"{RELEASE_SHA}:esphome/components/voice_kit"),
        "vendored_base": {
            "path": "voicepe/base/home-assistant-voice.yaml",
            "sha256": sha256_bytes((VOICEPE / "base" / "home-assistant-voice.yaml").read_bytes()),
            "differs_from_upstream_blob_by": "voicepe/base/home-assistant-voice.yaml.patch (one line: voice_kit ref dev -> 2644f4c)",
        },
        "external_component": {"url": "https://github.com/esphome/home-assistant-voice-pe", "ref": RELEASE_SHA, "components": ["voice_kit"]},
    }

    # Sounds: download, hash, and compare with the git blob in the release commit
    sounds = []
    for name in SOUND_FILES:
        url = f"https://raw.githubusercontent.com/esphome/home-assistant-voice-pe/{RELEASE_SHA}/sounds/{name}"
        data = fetch(url)
        blob = git(repo, "rev-parse", f"{RELEASE_SHA}:sounds/{name}")
        local = (repo / "sounds" / name).read_bytes()
        sounds.append({"url": url, "sha256": sha256_bytes(data), "size": len(data), "git_blob": blob,
                       "matches_git_checkout": data == local})
    lock["sounds"] = sounds

    xmos = fetch(XMOS_URL)
    lock["xmos_firmware"] = {"url": XMOS_URL, "version": "1.3.1", "sha256": sha256_bytes(xmos), "size": len(xmos),
                             "md5": hashlib.md5(xmos).hexdigest(), "md5_in_yaml": "964635c5bf125529dab14a2472a15401"}

    # Wake word models: vendored files, re-fetched from their sources and compared
    models = []
    for rel, src in MODEL_SOURCES.items():
        local = (VOICEPE / rel).read_bytes()
        entry = {"path": f"voicepe/{rel}", "sha256": sha256_bytes(local), "size": len(local), "source": src}
        if src.startswith("https://"):
            entry["source_sha256"] = sha256_bytes(fetch(src))
            entry["matches_source"] = entry["source_sha256"] == entry["sha256"]
        models.append(entry)
    lock["wake_word_models"] = models

    # ESP-IDF framework, tools and Python constraints
    lock["esp_idf"] = {"version": IDF_VERSION, "toolchain": "esphome native esp-idf", **fetch_hash(IDF_URL)}
    tools_json = json.loads((idf_root / "frameworks" / IDF_VERSION / "tools" / "tools.json").read_text())
    tools = []
    for tool in tools_json["tools"]:
        if tool["name"] in IDF_TOOLS:
            ver = next(v for v in tool["versions"] if v["name"] == IDF_TOOLS[tool["name"]])
            dl = ver.get("linux-amd64") or ver.get("any")
            tools.append({"name": tool["name"], "version": ver["name"], "url": dl["url"],
                          "sha256_in_tools_json": dl["sha256"], "size": dl["size"]})
    lock["esp_idf_tools_linux_amd64"] = tools
    vendored = (VOICEPE / "lock" / "espidf.constraints.v5.5.txt").read_bytes()
    lock["esp_idf_python_constraints"] = {
        "url": IDF_CONSTRAINTS_URL, "vendored": "voicepe/lock/espidf.constraints.v5.5.txt",
        "sha256": sha256_bytes(vendored), "size": len(vendored),
        "url_sha256_now": sha256_bytes(fetch(IDF_CONSTRAINTS_URL)),
        "note": "the URL is unversioned; the build never fetches it and uses the vendored copy",
    }

    # ESP component registry components, as resolved by this build
    deps = yaml.safe_load((build_out / "dependencies.lock").read_text())
    comps = []
    for name, d in sorted(deps["dependencies"].items()):
        src = d.get("source", {})
        comps.append({"name": name, "version": d.get("version"), "component_hash": d.get("component_hash"),
                      "source": src.get("registry_url") or src.get("type")})
    lock["idf_components"] = {"manifest_hash": deps.get("manifest_hash"), "target": deps.get("target"),
                              "components": comps}

    # PlatformIO registry libraries (downloaded by ESPHome, built as IDF components)
    libs = []
    for owner, name, version in PIO_LIBRARIES:
        meta = json.loads(fetch(f"https://api.registry.platformio.org/v3/packages/{owner}/library/{name}"))
        files = next(v for v in meta["versions"] if v["name"] == version)["files"]
        for f in files:
            got = fetch_hash(f["download_url"])
            libs.append({"name": f"{owner}/{name}", "version": version, "url": f["download_url"],
                         "sha256": got["sha256"], "registry_sha256": f["checksum"]["sha256"],
                         "matches_registry": got["sha256"] == f["checksum"]["sha256"]})
    lock["platformio_libraries"] = libs

    # What tools/esphome_repro.py lets ESPHome fetch: each downloaded file must
    # already be hashed independently above, with the same SHA-256.
    known = {s["url"]: s["sha256"] for s in sounds}
    known[XMOS_URL] = lock["xmos_firmware"]["sha256"]
    known[IDF_URL] = lock["esp_idf"]["sha256"]
    known.update({t["url"]: t["sha256_in_tools_json"] for t in tools})
    known.update({lib["url"]: lib["sha256"] for lib in libs})
    log = (build_out / "fetch-log.txt").read_text().splitlines()
    files = {}
    for line in log:
        if line.startswith("FILE "):
            _, url, sha, size = line.split()
            files[url] = {"url": url, "sha256": sha.removeprefix("sha256="), "size": int(size.removeprefix("size="))}
    artifacts, bad_fetch = [], []
    for url, f in sorted(files.items()):
        if known.get(url) == f["sha256"]:
            artifacts.append(f)
        else:
            bad_fetch.append(f"{url} (fetched {f['sha256']}, independent {known.get(url)})")
    requests_made = sorted({line.split(" ", 1)[1] for line in log if line.split(" ", 1)[0] in ("GET", "HEAD", "POST")})
    def why(url: str) -> str:
        if url.startswith("https://api.registry.platformio.org/v3/packages/"):
            return "PlatformIO registry metadata used to pick the library version; the archive is a locked artifact"
        if url == "http://185.199.110.153":
            return "PlatformIO's internet check (a GitHub IP in platformio/__init__.py); the response is not used"
        raise SystemExit(f"unexplained request in the fetch log: {url}")

    queries = [{"url": u, "why": why(u)} for u in requests_made if u not in files]
    lock["fetch_allowlist"] = {
        "about": "Enforced by tools/esphome_repro.py: ESPHome may request only these URLs, and every file it "
                 "downloads must be one of the artifacts with this SHA-256. Queries are registry and "
                 "update-check requests whose responses are not build inputs.",
        "artifacts": artifacts, "queries": queries,
    }

    out = VOICEPE / "lock" / "dependency-lock.json"
    out.write_text(json.dumps(lock, indent=1) + "\n")
    bad = [m["path"] for m in models if m.get("matches_source") is False] + bad_fetch
    if lock["esp_idf_python_constraints"]["url_sha256_now"] != lock["esp_idf_python_constraints"]["sha256"]:
        print("note: the constraints URL now serves different content than the vendored copy")
    bad += [s["url"] for s in sounds if not s["matches_git_checkout"]]
    bad += [lib["url"] for lib in libs if not lib["matches_registry"]]
    if lock["xmos_firmware"]["md5"] != lock["xmos_firmware"]["md5_in_yaml"]:
        bad.append(XMOS_URL)
    print(f"wrote {out}; mismatches: {bad or 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
