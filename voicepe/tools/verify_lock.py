"""Check the build's inputs against voicepe/lock/ (called by tools/build.sh).

  python -I verify_lock.py pre
      vendored models, base YAML and ESP-IDF constraints file have their locked
      SHA-256; the lock's Python package lists equal the hashed requirement
      files; every ESP-IDF package pin satisfies the vendored constraints.
  python -I verify_lock.py git
      after `esphome config`: the one external component checkout is the locked
      repository at the locked commit and tree, with no local change.
  python -I verify_lock.py post BUILD_DIR PENV_PYTHON
      after the compile: the ESP component registry components in
      dependencies.lock and managed_components/ are exactly the locked set, each
      with its locked version and a component hash recomputed from the files on
      disk; the IDF tools.json entries equal the locked tool archives; the
      fetch log has no violation.

Exits 1 on any difference (VOICEPE_LOCK_MODE=record only reports).
"""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import yaml

VOICEPE = Path(__file__).resolve().parent.parent
LOCKDIR = VOICEPE / "lock"
LOCK = json.loads((LOCKDIR / "dependency-lock.json").read_text())
IDF_ROOT = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "esphome" / "idf"
problems: list[str] = []


def expect(ok: bool, msg: str) -> None:
    print(("ok    " if ok else "FAIL  ") + msg)
    if not ok:
        problems.append(msg)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_req(path: Path) -> list[dict]:
    """The hashed requirement file as [{url, name, version, sha256}] (format written by pylock.py)."""
    pattern = r"^# (\S+)\n([A-Za-z0-9_.\-]+)==(\S+) \\\n    --hash=sha256:([0-9a-f]{64})$"
    return [{"url": m[1], "name": m[2], "version": m[3], "sha256": m[4]}
            for m in re.finditer(pattern, path.read_text(), re.M)]


def pre() -> None:
    for model in LOCK["wake_word_models"]:
        path = VOICEPE.parent / model["path"]
        expect(path.is_file() and sha256(path) == model["sha256"], f"model {model['path']} sha256 {model['sha256'][:12]}")
    base = LOCK["upstream_voice_pe"]["vendored_base"]
    expect(sha256(VOICEPE.parent / base["path"]) == base["sha256"], f"base YAML {base['path']} sha256 {base['sha256'][:12]}")
    con = LOCK["esp_idf_python_constraints"]
    con_path = VOICEPE.parent / con["vendored"]
    expect(sha256(con_path) == con["sha256"], f"vendored constraints {con['vendored']} sha256 {con['sha256'][:12]}")

    for env, info in LOCK["python_environments"].items():
        req = read_req(VOICEPE.parent / info["requirements"])
        expect(req == info["packages"], f"lock python_environments.{env} equals {info['requirements']} ({len(req)} hashed artifacts)")

    # The allowlist the guard enforces must carry the same hashes as the lock's own sections
    sections = {x["url"]: x["sha256"] for x in LOCK["sounds"]}
    sections[LOCK["xmos_firmware"]["url"]] = LOCK["xmos_firmware"]["sha256"]
    sections[LOCK["esp_idf"]["url"]] = LOCK["esp_idf"]["sha256"]
    sections.update({t["url"]: t["sha256_in_tools_json"] for t in LOCK["esp_idf_tools_linux_amd64"]})
    sections.update({x["url"]: x["sha256"] for x in LOCK["platformio_libraries"]})
    allow = {a["url"]: a["sha256"] for a in LOCK["fetch_allowlist"]["artifacts"]}
    expect(allow == sections, f"fetch_allowlist has the same {len(sections)} artifacts and hashes as the lock sections")

    # Every ESP-IDF env pin must satisfy the vendored constraints file
    pins = {canonicalize_name(p["name"]): p["version"] for p in LOCK["python_environments"]["esp_idf"]["packages"]}
    checked = 0
    for line in con_path.read_text().splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        r = Requirement(line)
        if r.marker and not r.marker.evaluate():
            continue
        name = canonicalize_name(r.name)
        if name in pins:
            checked += 1
            if not r.specifier.contains(pins[name], prereleases=True):
                expect(False, f"{name}=={pins[name]} violates constraint '{line}'")
    expect(checked > 0, f"ESP-IDF pins satisfy the vendored constraints ({checked} constrained packages checked)")


def git_check() -> None:
    up = LOCK["upstream_voice_pe"]
    repos = [p for p in (VOICEPE / ".esphome" / "external_components").iterdir() if p.is_dir()]
    expect(len(repos) == 1, f"one external component checkout ({[p.name for p in repos]})")
    repo = repos[0]

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    expect(git("remote", "get-url", "origin").removesuffix(".git") == up["repo"], f"external component from {up['repo']}")
    expect(git("rev-parse", "HEAD") == up["commit"], f"external component at commit {up['commit'][:12]}")
    expect(git("rev-parse", "HEAD:esphome/components/voice_kit") == up["esphome/components/voice_kit_tree"],
           f"voice_kit tree {up['esphome/components/voice_kit_tree'][:12]}")
    expect(git("status", "--porcelain", "--untracked-files=no") == "", "external component checkout has no local change")


def post(build_dir: Path, penv_python: str) -> None:
    locked = {c["name"]: c for c in LOCK["idf_components"]["components"]}
    deps = yaml.safe_load((build_dir / "dependencies.lock").read_text())["dependencies"]
    got = {n: {"name": n, "version": d.get("version"), "component_hash": d.get("component_hash"),
               "source": (d.get("source") or {}).get("registry_url") or (d.get("source") or {}).get("type")}
           for n, d in deps.items()}
    for n in sorted(set(locked) | set(got)):
        expect(locked.get(n) == got.get(n), f"dependencies.lock {n} {(got.get(n) or {}).get('version')} as locked")

    # Recompute each downloaded component's hash from its files, with the
    # component manager's own function, and compare with the lock.
    registry = {n: c for n, c in locked.items() if c["component_hash"]}
    managed = build_dir / "managed_components"
    dirs = {p.name for p in managed.iterdir() if p.is_dir()} if managed.is_dir() else set()
    expect(dirs == {n.replace("/", "__") for n in registry}, f"managed_components holds exactly the {len(registry)} locked registry components")
    # validate_hash_eq_hashdir hashes the files with the component's own
    # manifest include/exclude rules, as the registry does.
    script = ("import sys\nfrom idf_component_tools.hash_tools.validate import validate_hash_eq_hashdir\n"
              "for path, expected in zip(sys.argv[1::2], sys.argv[2::2]):\n"
              "    try:\n        validate_hash_eq_hashdir(path, expected); print('match')\n"
              "    except Exception as err:\n        print('differs:', type(err).__name__)")
    args = [x for n in sorted(registry) for x in (str(managed / n.replace("/", "__")), registry[n]["component_hash"])]
    results = subprocess.run([penv_python, "-I", "-c", script, *args], check=True, capture_output=True,
                             text=True).stdout.splitlines()
    for n, r in zip(sorted(registry), results, strict=True):
        expect(r == "match", f"{n} files hash to the locked {registry[n]['component_hash'][:12]} ({r})")

    tools_json = json.loads((IDF_ROOT / "frameworks" / LOCK["esp_idf"]["version"] / "tools" / "tools.json").read_text())
    for t in LOCK["esp_idf_tools_linux_amd64"]:
        tool = next(x for x in tools_json["tools"] if x["name"] == t["name"])
        ver = next(v for v in tool["versions"] if v["name"] == t["version"])
        dl = ver.get("linux-amd64") or ver.get("any")
        expect((dl["url"], dl["sha256"], dl["size"]) == (t["url"], t["sha256_in_tools_json"], t["size"]),
               f"tools.json {t['name']} {t['version']} as locked")
    installed = sorted(p.name for p in (IDF_ROOT / "tools").iterdir() if p.is_dir())
    expect(installed == sorted(t["name"] for t in LOCK["esp_idf_tools_linux_amd64"]), f"installed IDF tools {installed}")

    log = Path(os.environ["VOICEPE_FETCH_LOG"]).read_text().splitlines()
    files = [line for line in log if line.startswith("FILE ")]
    expect(not any(line.startswith("VIOLATION") for line in log), f"fetch log: {len(log)} entries, {len(files)} files hashed, no violation")
    fetched = {line.split()[1] for line in files}
    unused = [a["url"] for a in LOCK["fetch_allowlist"]["artifacts"] if a["url"] not in fetched]
    print(f"note  lock artifacts not fetched by this build: {unused or 'none'}")


if __name__ == "__main__":
    {"pre": pre, "git": git_check}.get(sys.argv[1], lambda: post(Path(sys.argv[2]), sys.argv[3]))()
    if problems:
        print(f"LOCK VIOLATION: {len(problems)} check(s) failed", file=sys.stderr)
        sys.exit(0 if os.environ.get("VOICEPE_LOCK_MODE") == "record" else 1)
