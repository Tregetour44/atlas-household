#!/usr/bin/env python3
"""Puts a new Hey Atlas model and manifest into the build, and nothing else:
  * models/hey_atlas/hey_atlas.tflite and hey_atlas.json (copied byte for byte);
  * their SHA-256, size and source in lock/dependency-lock.json, tools/make_lock.py
    and tools/check_merged.py (the lock and the 84 checks must know the new files);
  * the release version in hey-atlas-voice-pe.yaml, tools/build.sh (image names)
    and tools/check_merged.py (expected project version).
Every other input (base YAML, stock models, framework, components, Python
environments) is untouched, so the build stays on the same enforced lock.

  python -I tools/set_model.py MODEL.tflite MANIFEST.json VERSION "SOURCE TEXT"
"""
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tfl, man, version, source = sys.argv[1:5]
m = json.load(open(man))
assert m["model"] == "hey_atlas.tflite" and m["wake_word"] == "Hey Atlas", m
dst = os.path.join(HERE, "models", "hey_atlas")
shutil.copyfile(tfl, os.path.join(dst, "hey_atlas.tflite"))
shutil.copyfile(man, os.path.join(dst, "hey_atlas.json"))


def info(p):
    b = open(p, "rb").read()
    return hashlib.sha256(b).hexdigest(), len(b)


def sub(path, pattern, repl, count=1):
    p = os.path.join(HERE, path)
    s = open(p, encoding="utf-8").read()
    s2, n = re.subn(pattern, repl, s, count=count)
    assert n == count, (path, pattern, n)
    open(p, "w", encoding="utf-8").write(s2)


new = {}
for name in ("hey_atlas.json", "hey_atlas.tflite"):
    new[name] = info(os.path.join(dst, name))
lock_p = os.path.join(HERE, "lock", "dependency-lock.json")
lock_s = open(lock_p, encoding="utf-8").read()
lock = json.loads(lock_s)
for e in lock["wake_word_models"]:
    base = os.path.basename(e["path"])
    if e["path"].startswith("voicepe/models/hey_atlas/"):
        old = e["sha256"]
        e["sha256"], e["size"] = new[base]
        e["source"] = f"{source}, {base}"
        sub("tools/check_merged.py", re.escape(old), e["sha256"])
open(lock_p, "w", encoding="utf-8").write(json.dumps(lock, indent=1, ensure_ascii=False) + "\n")
for base in new:
    sub("tools/make_lock.py",
        r'MODEL_SOURCES\["models/hey_atlas/' + re.escape(base) + r'"\] = "[^"]*"',
        f'MODEL_SOURCES["models/hey_atlas/{base}"] = "{source}, {base}"')
sub("hey-atlas-voice-pe.yaml", r"version: 26\.9\.0-atlas\.\d+", f"version: {version}")
sub("tools/build.sh", r"NAME=atlas-voicepe-hey-atlas-26\.9\.0-atlas\.\d+", f"NAME=atlas-voicepe-hey-atlas-{version}")
sub("tools/check_merged.py", r'"26\.9\.0-atlas\.\d+"\)', f'"{version}")')
print(json.dumps({k: {"sha256": v[0], "size": v[1]} for k, v in new.items()}, indent=1))
