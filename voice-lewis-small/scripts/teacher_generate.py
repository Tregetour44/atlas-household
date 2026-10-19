"""Generate teacher clips: Chatterbox 0.1.7, fixed synthetic reference, exaggeration 0.4, cfg_weight 0.4,
default sampling, torch.manual_seed(<per-clip seed> + attempt) before each clip, Perth watermark kept (library default).
Resumable: skips clips whose master already exists. Writes 24 kHz FLAC (24-bit) masters and appends to a jsonl log.
usage: teacher_generate.py <manifest.tsv> <out_dir> <ref.wav> --splits train,heldout [--worker 0/2] [--attempt 0] [--ids a,b]
"""
import argparse, csv, json, os, time
import numpy as np, soundfile as sf, torch

ap = argparse.ArgumentParser()
ap.add_argument("manifest"); ap.add_argument("out"); ap.add_argument("ref")
ap.add_argument("--splits", default="train"); ap.add_argument("--worker", default="0/1")
ap.add_argument("--attempt", type=int, default=0); ap.add_argument("--ids", default="")
ap.add_argument("--limit", type=int, default=0)
a = ap.parse_args()
torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
wid, nw = map(int, a.worker.split("/"))
rows = [r for r in csv.DictReader(open(a.manifest, encoding="utf-8"), delimiter="\t") if r["split"] in a.splits.split(",")]
if a.ids:
    want = set(a.ids.split(",")); rows = [r for r in rows if r["id"] in want]
rows = rows[wid::nw]
if a.limit:
    rows = rows[: a.limit]
masters = os.path.join(a.out, "masters"); os.makedirs(masters, exist_ok=True)
log = os.path.join(a.out, "teacher_log.jsonl")

from chatterbox.tts import ChatterboxTTS
m = ChatterboxTTS.from_pretrained(device="cpu")
m.prepare_conditionals(a.ref, exaggeration=0.4)  # same as passing audio_prompt_path each call
for r in rows:
    name = r["id"] if a.attempt == 0 else f"{r['id']}.a{a.attempt}"
    path = os.path.join(masters, name + ".flac")
    if os.path.exists(path):
        continue
    seed = int(r["seed"]) + a.attempt
    torch.manual_seed(seed)
    t = time.perf_counter()
    wav = m.generate(r["text"], exaggeration=0.4, cfg_weight=0.4).squeeze().numpy()
    dt = time.perf_counter() - t
    sf.write(path + ".tmp", np.clip(wav, -1, 1), m.sr, format="FLAC", subtype="PCM_24")
    os.replace(path + ".tmp", path)
    rec = dict(id=r["id"], file=name + ".flac", attempt=a.attempt, seed=seed, synth_s=round(dt, 2),
               audio_s=round(len(wav) / m.sr, 2), rtf=round(dt / (len(wav) / m.sr), 3), worker=a.worker,
               threads=torch.get_num_threads())
    with open(log, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(rec, flush=True)
