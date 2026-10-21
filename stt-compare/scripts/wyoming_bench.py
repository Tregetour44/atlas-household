"""Run one STT configuration through a real Wyoming server and record transcripts, latency and memory.

Starts `python -m wyoming_faster_whisper` (v3.8.1: faster-whisper, sherpa-onnx/Parakeet, onnx-asr, Qwen3-ASR backends) with the
given arguments, then sends each clip the way Home Assistant does: transcribe, audio-start, audio-chunk..., audio-stop, and waits
for the transcript. Latency = audio-stop sent -> transcript received (the part of "after end of speech" that the STT engine owns;
HA's own end-of-speech wait is added on top and is the same for every engine). Peak server RSS is sampled throughout.

Usage: python wyoming_bench.py NAME MANIFEST AUDIO_DIR OUT_DIR [--realtime] [--clips N] -- <server args...>
"""
import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time

import numpy as np
import psutil
import soundfile as sf
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient

RATE, CHUNK = 16000, 1024


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


async def transcribe(port, pcm: bytes, realtime: bool, prompt=None):
    async with AsyncTcpClient("127.0.0.1", port) as c:
        await c.write_event(Transcribe(language="en").event())
        await c.write_event(AudioStart(rate=RATE, width=2, channels=1).event())
        t_audio = time.perf_counter()
        for i in range(0, len(pcm), CHUNK * 2):
            await c.write_event(AudioChunk(rate=RATE, width=2, channels=1, audio=pcm[i:i + CHUNK * 2]).event())
            if realtime:  # pace like a live microphone
                target = t_audio + (i + CHUNK * 2) / 2 / RATE
                await asyncio.sleep(max(0, target - time.perf_counter()))
        await c.write_event(AudioStop().event())
        t0 = time.perf_counter()
        while True:
            ev = await c.read_event()
            if ev is None:
                return None, time.perf_counter() - t0
            if Transcript.is_type(ev.type):
                return Transcript.from_event(ev).text, time.perf_counter() - t0


def main():
    argv = sys.argv[1:]
    sep = argv.index("--")
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("manifest")
    ap.add_argument("audio_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--realtime", action="store_true")
    ap.add_argument("--clips", type=int, default=0)
    ap.add_argument("--filter", default="", help="only clips whose path contains this")
    a = ap.parse_args(argv[:sep])
    server_args = argv[sep + 1:]
    clips = [json.loads(l) for l in open(a.manifest)]
    if a.filter:
        clips = [c for c in clips if a.filter in c["clip"]]
    if a.clips:
        clips = clips[: a.clips]
    port = free_port()
    log = open(os.path.join(a.out_dir, a.name + ".server.log"), "w")
    proc = subprocess.Popen([sys.executable, "-m", "wyoming_faster_whisper", "--uri", f"tcp://127.0.0.1:{port}"] + server_args,
                            stdout=log, stderr=subprocess.STDOUT)
    peak = {"rss": 0}
    stop = threading.Event()

    def sample():
        p = psutil.Process(proc.pid)
        while not stop.is_set():
            try:
                rss = p.memory_info().rss + sum(ch.memory_info().rss for ch in p.children(recursive=True))
                peak["rss"] = max(peak["rss"], rss)
            except psutil.Error:
                pass
            time.sleep(0.05)

    threading.Thread(target=sample, daemon=True).start()
    for _ in range(600):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            break
        except OSError:
            if proc.poll() is not None:
                raise SystemExit(f"server exited: see {log.name}")
            time.sleep(0.5)

    def pcm_of(path):
        x, sr = sf.read(path, dtype="int16")
        assert sr == RATE
        return x.tobytes()

    # warm-up: the first request loads the model (HA pays this once, at start-up)
    t_load = time.perf_counter()
    first, _ = asyncio.run(transcribe(port, pcm_of(os.path.join(a.audio_dir, clips[0]["clip"])), False))
    load_s = time.perf_counter() - t_load
    if not first:
        proc.terminate()
        raise SystemExit(f"{a.name}: no transcript for the warm-up clip; see {log.name}")
    asyncio.run(transcribe(port, pcm_of(os.path.join(a.audio_dir, clips[1]["clip"])), False))
    out = open(os.path.join(a.out_dir, a.name + ".jsonl"), "w")
    lat = []
    for c in clips:
        text, dt = asyncio.run(transcribe(port, pcm_of(os.path.join(a.audio_dir, c["clip"])), a.realtime))
        lat.append(dt)
        out.write(json.dumps({"clip": c["clip"], "id": c["id"], "hyp": text, "latency_s": round(dt, 4), "dur": c["dur"]}) + "\n")
        out.flush()
    stop.set()
    proc.terminate()
    proc.wait(timeout=30)
    meta = {"name": a.name, "server_args": server_args, "clips": len(clips), "realtime": a.realtime,
            "first_request_s": round(load_s, 2), "peak_rss_mb": round(peak["rss"] / 2**20), "cpu": os.cpu_count(),
            "latency_p50_s": round(float(np.median(lat)), 3), "latency_p95_s": round(float(np.percentile(lat, 95)), 3)}
    json.dump(meta, open(os.path.join(a.out_dir, a.name + ".meta.json"), "w"), indent=1)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
