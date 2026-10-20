"""Download and verify the Kokoro Fable-mix model bundle into a folder. Run once at install; the server never does.

    py -3.12 fetch_bundle.py C:\\AtlasVoice\\kokoro

Reads bundle/manifest.json next to this script. Each file is fetched from its pinned URL (Hugging Face URLs name an
exact commit), or copied from this repository when its source is a path, into a temporary name, checked against its
sha256, and only then moved into place. A file already present with the right hash is left alone. Any mismatch
deletes the download and exits non-zero. Standard library only; nothing here is imported by the server.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def fetch(entry: dict[str, str], dest: Path) -> None:
    tmp = dest.with_name(dest.name + ".part")
    source = entry["source"]
    if source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": "atlas-fetch-bundle"})
        with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as out:
            shutil.copyfileobj(r, out, CHUNK)
    else:
        shutil.copyfile(HERE / source, tmp)
    got = sha256_of(tmp)
    if got != entry["sha256"]:
        tmp.unlink()
        raise SystemExit(f"FAIL {dest.name}: sha256 {got} != {entry['sha256']}")
    tmp.replace(dest)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "bundle" / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        dest = target / entry["name"]
        if dest.exists() and sha256_of(dest) == entry["sha256"]:
            print(f"ok   {entry['name']} (already present)")
            continue
        print(f"get  {entry['name']} ({entry['size']:,} bytes)")
        fetch(entry, dest)
        print(f"ok   {entry['name']} sha256 {entry['sha256']}")
    print(f"bundle verified in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
