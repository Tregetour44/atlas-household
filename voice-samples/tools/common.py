import json, os, resource, time, sys
import soundfile as sf
S = os.path.dirname(os.path.abspath(__file__))
LINES = [l.strip() for l in open(os.path.join(S, "lines.txt")) if l.strip()]
OUT = os.path.join(S, "out")

def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

def run(model, voice, synth, sr_hint=None, lines=None, note=""):
    """synth(text) -> (np.ndarray float audio, sample_rate)"""
    tot_s = tot_a = 0.0
    for i, text in enumerate(lines or LINES, 1):
        t = time.time()
        audio, sr = synth(text)
        dt = time.time() - t
        dur = len(audio) / sr
        tot_s += dt; tot_a += dur
        sf.write(os.path.join(OUT, f"{model}-{voice}-{i}.wav"), audio, sr)
        print(f"{model}-{voice}-{i}: {dur:.1f}s audio in {dt:.1f}s", flush=True)
    rec = dict(model=model, voice=voice, synth_s=round(tot_s, 1), audio_s=round(tot_a, 1),
               rtf=round(tot_s / tot_a, 2), peak_rss_mb=round(rss_mb()), note=note)
    with open(os.path.join(S, "stats.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(rec, flush=True)
