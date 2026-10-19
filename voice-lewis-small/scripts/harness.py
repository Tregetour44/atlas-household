"""Shared timing/RTF harness: synth(text) -> (float32 mono numpy array, sample_rate)."""
import json, os, resource, time
import numpy as np
import soundfile as sf


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def read_lines(path):
    return [l.strip() for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]


def run(tag, synth, lines, out_dir, stats_path, warmup="Warm up, please.", names=None):
    """Render each line to <out_dir>/<tag>-<n>.wav and append per-clip + summary stats."""
    os.makedirs(out_dir, exist_ok=True)
    if warmup:
        synth(warmup)
    rtfs, tot_s, tot_a = [], 0.0, 0.0
    for i, text in enumerate(lines, 1):
        t = time.perf_counter()
        audio, sr = synth(text)
        dt = time.perf_counter() - t
        audio = np.asarray(audio, dtype=np.float32).squeeze()
        dur = len(audio) / sr
        name = names[i - 1] if names else f"{tag}-{i}"
        sf.write(os.path.join(out_dir, name + ".wav"), audio, sr, subtype="PCM_16")
        rtfs.append(dt / dur); tot_s += dt; tot_a += dur
        print(f"{name}: {dur:.2f}s audio in {dt:.2f}s (RTF {dt/dur:.2f})", flush=True)
    rec = dict(tag=tag, n=len(lines), synth_s=round(tot_s, 2), audio_s=round(tot_a, 2),
               rtf_mean=round(tot_s / tot_a, 3), rtf_p50=round(float(np.percentile(rtfs, 50)), 3),
               rtf_p95=round(float(np.percentile(rtfs, 95)), 3), peak_rss_mb=round(peak_rss_mb()),
               threads=int(os.environ.get("OMP_NUM_THREADS", 0)) or None)
    with open(stats_path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(rec, flush=True)
    return rec
