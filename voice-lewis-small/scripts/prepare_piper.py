"""Make Piper training copies of accepted clips: trim edge silence (keep 0.15 s lead / 0.25 s tail), mono 22,050 Hz 16-bit WAV.
Masters stay untouched (24 kHz FLAC). usage: prepare_piper.py <accepted.tsv> <masters_dir> <dataset_dir>"""
import csv, os, sys
import librosa, numpy as np, soundfile as sf
acc, masters, ds = sys.argv[1:4]
os.makedirs(os.path.join(ds, "wav"), exist_ok=True)
lines, tot = [], 0.0
for r in csv.DictReader(open(acc, encoding="utf-8"), delimiter="\t"):
    y, sr = sf.read(os.path.join(masters, r["file"]), dtype="float32")
    _, (a, b) = librosa.effects.trim(y, top_db=40, frame_length=1024, hop_length=256)
    y = y[max(a - int(0.15 * sr), 0): min(b + int(0.25 * sr), len(y))]
    y = librosa.resample(y, orig_sr=sr, target_sr=22050, res_type="soxr_hq")
    y = np.clip(y, -1, 1)
    sf.write(os.path.join(ds, "wav", r["id"] + ".wav"), y, 22050, subtype="PCM_16")
    tot += len(y) / 22050
    text = r["text"].replace("|", " ")
    lines.append(f"{r['id']}.wav|{text}")
open(os.path.join(ds, "metadata.csv"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"{len(lines)} clips, {tot/60:.1f} min at 22050 Hz -> {ds}")
