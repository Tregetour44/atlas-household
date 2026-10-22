"""Check the merged ESPHome config of the Hey Atlas Voice PE image.

Usage: python -I voicepe/tools/check_merged.py [voicepe/build/merged-config.yaml]

Proves from the merged config (output of `esphome config`) that:
  * the stock wake models, VAD, stop model, mute handling and the wake handler
    are each present exactly once, and hey_atlas is added exactly once;
  * voice_assistant uses micro_wake_word: mww and nothing starts Assist twice;
  * the factory wrapper's HTTP update channel is absent;
  * every fetched input is pinned, and no secret is in the image config.
Also checks the vendored base YAML against the upstream git blob at 2644f4c.
Exits 1 if any check fails.

Needs PyYAML 6.0.3 (the version in the build's ESPHome venv, used for
build/check-report.txt). To rerun on any computer, install it with hashes from
voicepe/lock/requirements-check.txt (instructions at the top of that file).
"""

import hashlib
import re
import sys
from pathlib import Path

import yaml

VOICEPE = Path(__file__).resolve().parent.parent
RELEASE_SHA = "2644f4c794271d735d182ca7ebf899ed46164f4e"
# git ls-tree 2644f4c home-assistant-voice.yaml
UPSTREAM_BASE_BLOB = "dbf258e1e8c21999728fdaf3982d92a9c15d78e4"
PIN_LINE = f"      ref: {RELEASE_SHA}  # ATLAS-PIN: was \"dev\" upstream; pinned to the 26.9.0 release commit\n"
XMOS_URL = "https://github.com/esphome/voice-kit-xmos-firmware/releases/download/v1.3.1/ffva_v1.3.1_upgrade.bin"
XMOS_MD5 = "964635c5bf125529dab14a2472a15401"
FRAMEWORK_VERSION = "5.5.5"
PROJECT = ("Nabu Casa.Home Assistant Voice PE", "26.9.0-atlas.2-c090")

# Model files the image must embed (path relative to voicepe/, sha256).
MODEL_FILES = {
    "models/hey_atlas/hey_atlas.json": "054461040b0fa570b73d2c3fe299bc3a44c0c23ff1bb932689e7d401e6804082",
    "models/hey_atlas/hey_atlas.tflite": "2bb30e62dd388c7b4d17cc80808b707ca65c5205a59dac958a86c645f80ffba7",
    "models/stock/okay_nabu_20241226.3/okay_nabu.json": "f8026e2ce93a0855ca23483036fd2d74ee924a2588d9ea6a6c6c7478fbf4be57",
    "models/stock/okay_nabu_20241226.3/okay_nabu.tflite": "d89128c4d16a72de429119fb2254ce46649553c2a24f5dd840175c80d7b9d094",
    "models/stock/stop/stop.json": "bd13aeb1b83852649dc4fb6135cb160ff68716d14612b06f6a405342c57447aa",
    "models/stock/stop/stop.tflite": "b5a18c4ad681a89950dfade31011e1631bdcb333e93c84519a1a63ff4f071146",
    "models/stock/micro-wake-word-models/hey_jarvis.json": "b153867d818675d8abcc9dace474afe7f83551ae0d5a9b1d71a98681320185af",
    "models/stock/micro-wake-word-models/hey_jarvis.tflite": "21a7976add39ee24ec96c63d96b7aaa18e24d1d9824b963e451da8feb4b78b77",
    "models/stock/micro-wake-word-models/hey_mycroft.json": "57b2b06fe5fdbbe834a242fabc7af31e4194a550fc382b2c88636a6d62d0d57e",
    "models/stock/micro-wake-word-models/hey_mycroft.tflite": "c2a9b6ed51182db72e014781d5a4ece1929dc232a40b5b4be384f0295f0e1571",
    "models/stock/micro-wake-word-models/vad.json": "bd8c9cd4350814f761e651685ae5196e2a56521aaf5670071ba742927de58ed7",
    "models/stock/micro-wake-word-models/vad.tflite": "7aa4db6d5fb7c5358609f6931e7847d303c16a43d178638bc14104f50d7eff5f",
}
# Model id -> (manifest relative to voicepe/, internal)
EXPECTED_MODELS = {
    "okay_nabu": ("models/stock/okay_nabu_20241226.3/okay_nabu.json", False),
    "hey_jarvis": ("models/stock/micro-wake-word-models/hey_jarvis.json", False),
    "hey_mycroft": ("models/stock/micro-wake-word-models/hey_mycroft.json", False),
    "stop": ("models/stock/stop/stop.json", True),
    "hey_atlas": ("models/hey_atlas/hey_atlas.json", False),
}
VAD_MANIFEST = "models/stock/micro-wake-word-models/vad.json"


class Loader(yaml.SafeLoader):
    pass


def _any_tag(loader, _suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


Loader.add_multi_constructor("!", _any_tag)

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, evidence: str = "") -> None:
    results.append((bool(ok), name, evidence))


def walk(node, path=""):
    """Yield (path, key, value) for every mapping entry."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else str(k)
            yield p, k, v
            yield from walk(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def action_paths(node, action):
    return [p for p, k, _ in walk(node) if k == action]


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)


def rel(path: str) -> str:
    """Path relative to voicepe/, whichever machine wrote the merged config."""
    s = str(path).replace("\\", "/")
    i = s.rfind("/voicepe/")
    return s[i + len("/voicepe/"):] if i >= 0 else s


def main() -> int:
    merged_path = Path(sys.argv[1]) if len(sys.argv) > 1 else VOICEPE / "build" / "merged-config.yaml"
    text = merged_path.read_text(encoding="utf-8")
    cfg = yaml.load(text, Loader=Loader)
    base_text = (VOICEPE / "base" / "home-assistant-voice.yaml").read_text(encoding="utf-8")
    base = yaml.load(base_text, Loader=Loader)

    # --- top-level keys appear once (a duplicated key would be silently merged by a YAML parser)
    top = re.findall(r"^([a-z_0-9]+):", text, flags=re.M)
    dupes = sorted({k for k in top if top.count(k) > 1})
    check(not dupes, "every top-level component key appears once", f"duplicates: {dupes or 'none'}")

    # --- micro_wake_word: models, VAD, stop, handler
    mww = cfg["micro_wake_word"]
    check(isinstance(mww, dict) and mww.get("id") == "mww", "one micro_wake_word block, id mww", f"id={mww.get('id')}")
    models = mww.get("models", [])
    ids = [m.get("id") for m in models]
    check(sorted(ids) == sorted(EXPECTED_MODELS) and len(ids) == len(set(ids)),
          "wake models: okay_nabu, hey_jarvis, hey_mycroft, stop, hey_atlas, each exactly once", f"ids={ids}")
    for m in models:
        mid = m.get("id")
        if mid not in EXPECTED_MODELS:
            continue
        want_manifest, want_internal = EXPECTED_MODELS[mid]
        src = m.get("model", {})
        check(src.get("type") == "local" and rel(src.get("path", "")) == want_manifest,
              f"model {mid} is the pinned local file", f"{src.get('type')}:{rel(src.get('path', ''))}")
        check(bool(m.get("internal")) == want_internal, f"model {mid} internal={want_internal}", f"internal={m.get('internal')}")
    vad = mww.get("vad")
    check(isinstance(vad, dict) and vad.get("model", {}).get("type") == "local"
          and rel(vad["model"].get("path", "")) == VAD_MANIFEST, "VAD present once, pinned local model",
          f"{vad.get('model') if isinstance(vad, dict) else vad}")
    check(text.count("\n  vad:") == 1, "exactly one vad block", f"count={text.count(chr(10) + '  vad:')}")

    handlers = action_paths(cfg, "on_wake_word_detected")
    check(handlers == ["micro_wake_word.on_wake_word_detected"],
          "exactly one wake handler (micro_wake_word.on_wake_word_detected)", f"{handlers}")
    handler = mww.get("on_wake_word_detected", {})
    starts_in_handler = action_paths(handler, "voice_assistant.start")
    check(len(starts_in_handler) == 1, "wake handler starts Assist exactly once", f"{starts_in_handler}")
    then = handler.get("then", [])
    gate = then[0]["if"]["condition"] if len(then) == 1 and "if" in then[0] else None
    check(gate == {"switch.is_off": {"id": "master_mute_switch"}},
          "wake handler is gated by master_mute_switch (mute handling kept)", f"condition={gate}")

    # --- mute handling defined once
    sw_ids = [s.get("id") for s in cfg.get("switch", [])]
    bs_ids = [b.get("id") for b in cfg.get("binary_sensor", [])]
    check(sw_ids.count("master_mute_switch") == 1, "master_mute_switch defined exactly once", f"count={sw_ids.count('master_mute_switch')}")
    check(bs_ids.count("hardware_mute_switch") == 1, "hardware_mute_switch defined exactly once", f"count={bs_ids.count('hardware_mute_switch')}")

    # --- Assist start paths: same as stock (the overlay adds none)
    va = cfg["voice_assistant"]
    check(va.get("micro_wake_word") == "mww", "voice_assistant.micro_wake_word: mww", f"{va.get('micro_wake_word')}")
    check(va.get("use_wake_word") is False, "voice_assistant.use_wake_word: false (no server-side wake word)", f"{va.get('use_wake_word')}")
    check("on_wake_word_detected" not in va, "no second wake handler on voice_assistant", "")
    for action in ("voice_assistant.start", "voice_assistant.start_continuous", "micro_wake_word.start",
                   "micro_wake_word.stop", "micro_wake_word.enable_model", "micro_wake_word.disable_model"):
        got, want = action_paths(cfg, action), action_paths(base, action)
        check(len(got) == len(want), f"{action}: same count as stock base ({len(want)})",
              f"merged={len(got)} at {got}")
    occ = va.get("on_client_connected", {}).get("then", [])
    check(len(occ) >= 2 and "wait_until" in occ[0] and occ[1] == {"delay": "2s"}
          and occ[0]["wait_until"]["condition"] == {"not": {"ble.enabled": {}}},
          "factory BLE wait runs first in on_client_connected (as in the factory wrapper)", f"first={occ[:2]}")

    # --- update channel absent
    for key in ("update", "http_request", "dashboard_import"):
        check(key not in cfg, f"no top-level '{key}'", "")
    ota = cfg.get("ota", [])
    check(len(ota) == 1 and ota[0].get("platform") == "esphome", "OTA: only the local esphome platform",
          f"{[o.get('platform') for o in ota]}")
    joined = "\n".join(strings(cfg))
    for needle in ("firmware.esphome.io", "manifest.json", "manifest-beta.json", "beta_firmware",
                   "update_http_request", "ota_http_request", "update.perform", "ota.http_request"):
        check(needle not in joined, f"no '{needle}' anywhere", "")

    # --- pins
    urls = sorted(set(re.findall(r"https?://[^\s'\"]+", joined)))
    bad = []
    for u in urls:
        if u == XMOS_URL:
            continue
        if RELEASE_SHA in u:
            continue
        if u == "https://github.com/esphome/home-assistant-voice-pe":
            continue  # git source of the voice_kit external component; its ref is checked below
        if u.startswith("https://www.home-assistant.io/") or u.startswith("https://esphome.io/"):
            continue  # documentation links in comments/strings, never fetched
        bad.append(u)
    check(not bad, "every fetched URL is pinned to 2644f4c (or is the md5-checked XMOS release)",
          f"{len(urls)} URLs; unpinned: {bad or 'none'}")
    for u in urls:
        check(not re.search(r"/(dev|main|master)/|@(dev|main|master)\b", u), f"no branch ref in {u}", "")
    vk = cfg["voice_kit"]["firmware"]
    check(vk.get("url") == XMOS_URL and vk.get("md5") == XMOS_MD5, "XMOS firmware URL and md5 as stock", f"{vk}")
    ext = cfg.get("external_components", [])
    refs = [(e["source"].get("url"), e["source"].get("ref")) for e in ext]
    check(len(ext) == 1 and refs[0] == ("https://github.com/esphome/home-assistant-voice-pe", RELEASE_SHA),
          "voice_kit external component pinned to 2644f4c (single source)", f"{refs}")
    fw = cfg["esp32"]["framework"]
    check(fw.get("type") == "esp-idf" and str(fw.get("version")) == FRAMEWORK_VERSION,
          f"framework esp-idf {FRAMEWORK_VERSION}", f"{fw.get('type')} {fw.get('version')}")
    check(cfg["esp32"].get("toolchain") == "esp-idf", "toolchain esp-idf", f"{cfg['esp32'].get('toolchain')}")
    for relpath, want in MODEL_FILES.items():
        got = hashlib.sha256((VOICEPE / relpath).read_bytes()).hexdigest()
        check(got == want, f"sha256 {relpath}", got)

    # --- vendored base == upstream blob except the one pinned line
    pinned_count = base_text.count(PIN_LINE)
    restored = base_text.replace(PIN_LINE, "      ref: dev\n").encode()
    blob = hashlib.sha1(b"blob %d\0" % len(restored) + restored).hexdigest()
    check(pinned_count == 1 and blob == UPSTREAM_BASE_BLOB,
          "base/home-assistant-voice.yaml == upstream 2644f4c blob except the one pinned ref line",
          f"pinned lines={pinned_count}, restored blob={blob}")

    # --- no secrets
    api = cfg["api"]
    check(api.get("encryption") == {}, "api.encryption has no key (key stays the one HA set on the device)", f"{api.get('encryption')}")
    check(all("password" not in o for o in ota), "OTA has no password", "")
    wifi = cfg["wifi"]
    check(wifi.get("networks") == [] and not any(k in wifi for k in ("ssid", "password", "ap", "manual_ip")),
          "wifi has no networks, password, AP or address (credentials come from NVS / Improv)",
          f"networks={wifi.get('networks')}")
    srcs = [VOICEPE / "hey-atlas-voice-pe.yaml", VOICEPE / "base" / "home-assistant-voice.yaml"]
    check(not any("!secret" in p.read_text() for p in srcs), "no !secret in the sources", "")

    # --- project
    proj = cfg["esphome"].get("project", {})
    check((proj.get("name"), proj.get("version")) == PROJECT, "project name and custom version", f"{proj}")
    check(cfg["esphome"].get("name") == "home-assistant-voice" and cfg["esphome"].get("name_add_mac_suffix") is True,
          "device name as stock (home-assistant-voice-xxxxxx)", f"{cfg['esphome'].get('name')}")

    width = max(len(n) for _, n, _ in results)
    for ok, name, ev in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {ev}")
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
