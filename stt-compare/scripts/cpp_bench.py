"""whisper.cpp (whisper-server) and parakeet.cpp (parakeet-cli) on the test set: transcripts, time per clip, peak RSS.

These are the engines that can use the RX 9070 XT through Vulkan on Windows. Here they run on the sandbox CPU, to check that
the GGML-quantised models are as accurate as the CTranslate2/ONNX ones; GPU speed comes from the owner's PC (bench_pc.ps1).

  python cpp_bench.py whisper NAME MODEL MANIFEST AUDIO_DIR OUT_DIR [--prompt-file F] [--threads 4] [--server BIN]
  python cpp_bench.py parakeet NAME MODEL MANIFEST AUDIO_DIR OUT_DIR [--threads 4] [--cli BIN]
whisper: one HTTP request per clip to a warm whisper-server (beam 5, language en, as a Wyoming wrapper would call it).
parakeet: parakeet-cli has no server; all clips go to one process and the time per clip is the gap between output lines.
"""
import argparse
import io
import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
import uuid

import numpy as np
import psutil
import soundfile as sf

WCPP = os.environ.get("WHISPER_CPP", "/home/user/whisper.cpp/build/bin")


def peak_sampler(pid, peak, stop):
    p = psutil.Process(pid)
    while not stop.is_set():
        try:
            peak[0] = max(peak[0], p.memory_info().rss)
        except psutil.Error:
            pass
        time.sleep(0.05)


def post_wav(port, path, prompt):
    x, sr = sf.read(path, dtype="int16")
    buf = io.BytesIO()
    sf.write(buf, x, sr, format="WAV", subtype="PCM_16")
    b = uuid.uuid4().hex
    fields = {"response_format": "json", "language": "en", "temperature": "0.0"}
    if prompt:
        fields["prompt"] = prompt
    body = b""
    for k, v in fields.items():
        body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode()
    body += buf.getvalue() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/inference", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        text = json.loads(r.read())["text"]
    return text.strip(), time.perf_counter() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["whisper", "parakeet"])
    ap.add_argument("name")
    ap.add_argument("model")
    ap.add_argument("manifest")
    ap.add_argument("audio_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--prompt-file")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--filter", default="")
    a = ap.parse_args()
    clips = [json.loads(l) for l in open(a.manifest) if a.filter in l]
    prompt = open(a.prompt_file).read().strip() if a.prompt_file else None
    out = open(os.path.join(a.out_dir, a.name + ".jsonl"), "w")
    peak, stop, lat = [0], threading.Event(), []
    if a.kind == "whisper":
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        proc = subprocess.Popen([f"{WCPP}/whisper-server", "-m", a.model, "-t", str(a.threads), "-bs", "5", "-l", "en",
                                 "--port", str(port), "-nfa"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        threading.Thread(target=peak_sampler, args=(proc.pid, peak, stop), daemon=True).start()
        for _ in range(300):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        post_wav(port, os.path.join(a.audio_dir, clips[0]["clip"]), prompt)  # warm-up
        for c in clips:
            text, dt = post_wav(port, os.path.join(a.audio_dir, c["clip"]), prompt)
            lat.append(dt)
            out.write(json.dumps({"clip": c["clip"], "id": c["id"], "hyp": text, "latency_s": round(dt, 4), "dur": c["dur"]}) + "\n")
            out.flush()
        proc.terminate()
    else:
        files = [os.path.join(a.audio_dir, clips[0]["clip"])] + [os.path.join(a.audio_dir, c["clip"]) for c in clips]
        proc = subprocess.Popen([f"{WCPP}/parakeet-cli", "-m", a.model, "-t", str(a.threads), "-np"] + files,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        threading.Thread(target=peak_sampler, args=(proc.pid, peak, stop), daemon=True).start()
        proc.stdout.readline()  # warm-up clip (includes model load)
        t = time.perf_counter()
        for c in clips:
            text = proc.stdout.readline().strip()
            now = time.perf_counter()
            dt, t = now - t, now
            lat.append(dt)
            out.write(json.dumps({"clip": c["clip"], "id": c["id"], "hyp": text, "latency_s": round(dt, 4), "dur": c["dur"]}) + "\n")
            out.flush()
        proc.wait()
    stop.set()
    meta = {"name": a.name, "engine": a.kind + ".cpp (CPU build)", "model": os.path.basename(a.model), "clips": len(clips),
            "threads": a.threads, "prompt": bool(prompt), "peak_rss_mb": round(peak[0] / 2**20), "cpu": os.cpu_count(),
            "latency_p50_s": round(float(np.median(lat)), 3), "latency_p95_s": round(float(np.percentile(lat, 95)), 3)}
    json.dump(meta, open(os.path.join(a.out_dir, a.name + ".meta.json"), "w"), indent=1)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
