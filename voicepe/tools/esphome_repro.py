"""Run the ESPHome CLI with the build timestamp fixed and every fetch held to the lock.

Build time. ESPHome 2026.9.1 stamps time.time() into every image
(ESPHOME_BUILD_TIME and its string form, see esphome/writer.py
get_build_info). That is the only clock input; ESP-IDF's
CONFIG_APP_REPRODUCIBLE_BUILD is already on. Fixing it makes two clean builds
byte-identical. On the device the value is only reported as the compilation
time and used as a lower bound for the clock.

Lock guard. Every network fetch ESPHome makes goes through `requests`,
archives through framework_helpers.download_with_resume (ESP-IDF tarball, IDF
tool archives, PlatformIO library archives) and remote files through
external_files.download_content (sounds, XMOS firmware). The guard:
  * refuses any HTTP request whose URL is not in the lock's fetch_allowlist
    (artifacts or metadata queries);
  * hashes every downloaded archive and remote file and refuses it unless the
    URL is a lock artifact with that SHA-256;
  * replaces ESPHome's ESP-IDF Python environment step (pip or uv install from
    the online constraints file) with a check that tools/build.sh already built
    that environment from lock/requirements-esp-idf.txt with --require-hashes.
A refusal prints LOCK VIOLATION and ends the process at once with status 97
(os._exit, so no caller inside ESPHome can catch it). Every request and file
is also written to VOICEPE_FETCH_LOG.

VOICEPE_LOCK_MODE=record (used only to write a new lock) logs without refusing.

Usage: SOURCE_DATE_EPOCH=<seconds> VOICEPE_LOCK=<dependency-lock.json>
       VOICEPE_FETCH_LOG=<file> python -I esphome_repro.py compile <config.yaml>
"""

import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

import requests

import esphome.espidf.framework
import esphome.external_files
import esphome.framework_helpers
import esphome.writer
from esphome.core import CORE

EPOCH = int(os.environ["SOURCE_DATE_EPOCH"])
LOCK = json.loads(Path(os.environ["VOICEPE_LOCK"]).read_text())
ALLOW = LOCK["fetch_allowlist"]
ARTIFACTS = {a["url"]: a["sha256"] for a in ALLOW["artifacts"]}
QUERIES = {q["url"] for q in ALLOW["queries"]}
RECORD = os.environ.get("VOICEPE_LOCK_MODE") == "record"
_log_lock = threading.Lock()


def get_build_info() -> tuple[int, int, str, str]:
    build_time_str = time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime(EPOCH))
    return CORE.config_hash, EPOCH, build_time_str, CORE.comment or ""


def log(line: str) -> None:
    with _log_lock, open(os.environ["VOICEPE_FETCH_LOG"], "a") as f:
        f.write(line + "\n")


def violation(msg: str) -> None:
    log(f"VIOLATION {msg}")
    if RECORD:
        return
    print(f"LOCK VIOLATION: {msg}", file=sys.stderr, flush=True)
    os._exit(97)


def check_file(url: str, path) -> None:
    data = Path(path).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    log(f"FILE {url} sha256={sha} size={len(data)}")
    if url not in ARTIFACTS:
        violation(f"{url} was downloaded but is not a lock artifact")
    elif ARTIFACTS[url] != sha:
        Path(path).unlink(missing_ok=True)
        violation(f"{url} has SHA-256 {sha}, the lock says {ARTIFACTS[url]}")


_request = requests.Session.request


def guarded_request(self, method, url, *args, **kwargs):
    log(f"{method.upper()} {url}")
    if url not in ARTIFACTS and url not in QUERIES:
        violation(f"{method.upper()} {url} is not in the lock's fetch_allowlist")
    return _request(self, method, url, *args, **kwargs)


_download_with_resume = esphome.framework_helpers.download_with_resume


def guarded_download_with_resume(url, dest, *args, **kwargs):
    _download_with_resume(url, dest, *args, **kwargs)
    check_file(url, dest)


_download_content = esphome.external_files.download_content


def guarded_download_content(url, path, *args, **kwargs):
    result = _download_content(url, path, *args, **kwargs)
    check_file(url, path)
    return result


def locked_idf_python_env(version, features, force=False, env=None):
    path = esphome.espidf.framework._get_python_env_path(version)
    marker = path / ".voicepe-lock"
    if sorted(set(features)) != ["core"] or not marker.is_file():
        violation(f"ESP-IDF Python environment {path} (features {features}) was not built from the lock by tools/build.sh")
    print(f"INFO ESP-IDF {version} Python environment: {marker.read_text().strip()}", flush=True)
    return path, False


esphome.writer.get_build_info = get_build_info
requests.Session.request = guarded_request
esphome.framework_helpers.download_with_resume = guarded_download_with_resume
esphome.external_files.download_content = guarded_download_content
esphome.espidf.framework._check_esp_idf_python_env_install = locked_idf_python_env

from esphome.__main__ import main  # noqa: E402

sys.exit(main())
