"""WAV -> loudness-matched MP3s (-18 LUFS, mono, 96 kbps, like voice-samples), per line and one joined file per voice
(L01..L10 with 0.5 s between lines). Input names <tag>-<S1..L10>.wav or <tag>-<1..14>.wav (fable_render.py).
usage: make_mp3s.py <wav_dir> <mp3_dir> [tag_rename=new ...]"""
import glob, os, re, subprocess, sys, tempfile, collections
import numpy as np, soundfile as sf, librosa
src, dst = sys.argv[1:3]
ren = dict(a.split("=", 1) for a in sys.argv[3:])
NAMES = [f"S{i}" for i in range(1, 5)] + [f"L{i:02d}" for i in range(1, 11)]
os.makedirs(dst, exist_ok=True)
groups = collections.defaultdict(dict)
for f in glob.glob(os.path.join(src, "*.wav")):
    m = re.match(r"(.+)-(S\d|L\d\d|\d+)\.wav$", os.path.basename(f))
    key = NAMES[int(m.group(2)) - 1] if m.group(2).isdigit() else m.group(2)
    groups[ren.get(m.group(1), m.group(1))][key] = f
enc = lambda i, o: subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", i, "-af", "loudnorm=I=-18:TP=-1.5:LRA=11",
                                   "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", o], check=True)
for tag, files in sorted(groups.items()):
    for key, f in files.items():
        enc(f, os.path.join(dst, f"{tag}-{key}.mp3"))
    seq = [librosa.load(files[k], sr=24000)[0] for k in NAMES[4:] if k in files]
    if seq:
        gap = np.zeros(12000, dtype=np.float32)
        joined = np.concatenate([np.concatenate([s, gap]) for s in seq])
        with tempfile.NamedTemporaryFile(suffix=".wav") as t:
            sf.write(t.name, joined, 24000); enc(t.name, os.path.join(dst, f"{tag}-joined-L01-L10.mp3"))
    print(tag, len(files), flush=True)
