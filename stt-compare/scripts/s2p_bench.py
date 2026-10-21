"""Speech-to-Phrase v2.2.0 (OHF-Voice/apps, the HA add-on's own recogniser library) on the test set.

Builds the grammar the add-on would build for this house with its default command selection: home-assistant-intents'
speech_to_phrase templates, the add-on's default-enabled combos, and this house's names as HA registry records (lights with
brightness, blinds with position, the two scenes, an air conditioner, a weather entity; rooms as areas, upstairs/downstairs as
floors). Then decodes every clip with the add-on's English model (NeMo Parakeet TDT-CTC 110M) and applies the add-on's score
gate (3.8 for that model): above it, the transcript is empty, as HA would receive it.

Two grammars:
  default  the add-on's first-run selection (24 combos), no custom commands.
  tuned    every light/blind/climate/weather/timer/time combo, plus custom commands for this house: the two scenes, Atlas's
           light timers ("turn off the X in N minutes", "... at H MM pm") and blind percentages. The best case for fronting.
Usage (in a venv with the add-on's lib/ installed + hassil + home-assistant-intents):
  python s2p_bench.py ADDON_SRC_DIR MODEL_DIR MANIFEST AUDIO_DIR OUT_DIR [default|tuned]
Writes OUT_DIR/speech-to-phrase-<grammar>.jsonl (+ .meta.json, .grammar.txt).
"""
import json
import os
import sys
import time

import numpy as np
import psutil

src, model_dir, manifest, audio_dir, out = sys.argv[1:6]
mode = sys.argv[6] if len(sys.argv) > 6 else "default"
NAME = f"speech-to-phrase-{mode}"
sys.path.insert(0, src)
import presets as bi  # noqa: E402
import training  # noqa: E402
from speech_to_phrase import load_recognizer  # noqa: E402
from speech_to_phrase.defaults import MODEL_MAX_SCORE  # noqa: E402

LIGHTS = """atrium spotlight left; atrium spotlight right; dining room lamp; dining room pendant; ensuite downlight; fountain spotlight;
garage ceiling left; garage ceiling right; garden spotlight; guest bedroom ceiling; guest bedroom lamp; hallway downlight;
hallway downlight back; hallway downlight front; kitchen ceiling; kitchen chandelier one; kitchen chandelier two;
kitchen chandelier three; kitchen downlight left; kitchen downlight right; laundry downlight; living room chandelier one;
living room chandelier two; living room chandelier three; living room chandelier four; living room chandelier five;
living room chandelier six; living room downlight back; living room downlight front; living room lamp; loft downlight left;
loft downlight middle; loft downlight right; loft lamp; master bedroom ceiling; master bedroom lamp; mirror ambiance;
pergola floodlight one; pergola floodlight two; pergola floodlight three; pergola spotlight one; pergola spotlight two;
pergola spotlight three; porch downlight one; porch downlight two; porch downlight three; porch downlight four; range hood one;
range hood two; robe downlight; study ceiling; wall floodlight; wall light; living room lights; porch lights; patio lights;
kitchen lights; loft lights; study lights; garage lights; laundry lights; hallway lights; atrium lights; dining room lights;
guest bedroom lights; master bedroom lights; outside lights""".replace("\n", " ")
AREAS = ["atrium", "dining room", "garage", "guest bedroom", "hallway", "kitchen", "laundry", "living room", "loft",
         "master bedroom", "patio", "porch", "study", "pergola", "ensuite", "garden"]
FLOORS = ["upstairs", "downstairs", "ground floor"]


def area_of(name):
    for a in sorted(AREAS, key=len, reverse=True):
        if name.startswith(a):
            return a
    return None


records = [{"name": n.strip(), "domain": "light", "entity_id": "light." + n.strip().replace(" ", "_"), "features": ["brightness"],
            "area": area_of(n.strip()), "floor": None} for n in LIGHTS.split(";")]
records += [{"name": n, "domain": "cover", "entity_id": "cover." + n.replace(" ", "_"), "features": ["set_position"],
             "device_class": "blind", "area": area_of(n), "floor": None}
            for n in ("atrium blind", "living room door blind", "living room window blind", "living room blinds")]
records += [{"name": n, "domain": "scene", "entity_id": "scene." + n.replace(" ", "_"), "features": [], "area": None, "floor": None}
            for n in ("good night", "wind down")]
records += [{"name": "air conditioner", "domain": "climate", "entity_id": "climate.air_conditioner", "features": ["target_temperature"],
             "area": "living room", "floor": None},
            {"name": "home", "domain": "weather", "entity_id": "weather.home", "features": [], "area": None, "floor": None}]

meta = bi.load_intents_meta()
combos = bi.available_combos("en", meta)
enabled = bi.default_enabled(combos)
custom = []
if mode == "tuned":
    keep = ("HassTurnOn", "HassTurnOff", "HassLightSet", "HassSetPosition", "HassClimateGetTemperature", "HassGetWeather",
            "HassStartTimer", "HassCancelTimer", "HassTimerStatus", "HassNevermind", "HassGetCurrentTime", "HassGetState")
    enabled = [[c["intent"], c["combo"]] for c in combos if c["intent"] in keep]
    clock = "{1..12:hour} [{0..59:minute}] (a m|p m)"
    custom = [
        {"mode": "stt", "sentences": ["[(run|start|activate)] [the] (good night|wind down) [scene] [please]",
                                      "put the (good night|wind down) scene on", "set the house to (good night|wind down)",
                                      "(run|start) (good night|wind down) (in {1..60:minutes} minutes|at " + clock + ")",
                                      "cancel that", "undo that", "cancel the {name} timer"], "name_domains": ["light"]},
        {"mode": "stt", "name_domains": ["light"], "sentences": [
            "turn (on|off) [the] {name} (in {1..60:minutes} minutes|in half an hour|in an hour|at " + clock + "|at midnight)",
            "turn [the] {name} (on|off) (in {1..60:minutes} minutes|in half an hour|in an hour|at " + clock + "|at midnight)",
            "(dim|set|brighten) [the] {name} to {0..100:brightness} percent"]},
        {"mode": "stt", "name_domains": ["cover"], "sentences": [
            "(open|close|raise|lower) [the] {name} [(halfway|all the way)]", "(set|put) [the] {name} (to|at) {0..100:position} percent",
            "(open|close) [the] {name} at " + clock]},
    ]
slot_lists = {"area": AREAS, "floor": FLOORS}
templates, list_values = training.assemble("en", enabled, custom, records, slot_lists)
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, NAME + ".grammar.txt"), "w") as f:
    f.write(f"# {len(templates)} templates from {len(enabled)} default-enabled combos\n")
    for t in templates:
        f.write(t + "\n")
    for k, v in sorted(list_values.items()):
        f.write(f"# list {k}: {len(v)} values: {', '.join(v[:12])}{' ...' if len(v) > 12 else ''}\n")

t0 = time.perf_counter()
rec = load_recognizer("nemo", model_dir, language="en")
rec.train(templates, list_values=list_values)
train_s = time.perf_counter() - t0
gate = MODEL_MAX_SCORE.get("stt_en_parakeet_tdt_ctc_110m", 3.8)
clips = [json.loads(l) for l in open(manifest)]
proc = psutil.Process()
rec.transcribe(os.path.join(audio_dir, clips[0]["clip"]))  # warm-up
lat, peak = [], 0
with open(os.path.join(out, NAME + ".jsonl"), "w") as f:
    for c in clips:
        t = time.perf_counter()
        r = rec.transcribe(os.path.join(audio_dir, c["clip"]))
        dt = time.perf_counter() - t
        lat.append(dt)
        peak = max(peak, proc.memory_info().rss)
        score = r.score if np.isfinite(r.score) else None
        accepted = score is not None and score <= gate
        f.write(json.dumps({"clip": c["clip"], "id": c["id"], "hyp": r.text if accepted else "", "raw": r.text, "score": score,
                            "margin": r.margin if np.isfinite(r.margin) else None, "latency_s": round(dt, 4), "dur": c["dur"]}) + "\n")
m = {"name": NAME, "templates": len(templates), "combos": len(enabled), "train_s": round(train_s, 1), "gate": gate,
     "peak_rss_mb": round(peak / 2**20), "latency_p50_s": round(float(np.median(lat)), 3),
     "latency_p95_s": round(float(np.percentile(lat, 95)), 3), "cpu": os.cpu_count()}
json.dump(m, open(os.path.join(out, NAME + ".meta.json"), "w"), indent=1)
print(json.dumps(m))
