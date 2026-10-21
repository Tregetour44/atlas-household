"""Owner's-PC bench driver (called by bench_pc.ps1; also runs on Linux). About 5 minutes after downloads.

Runs the shortlisted engines on 60 test clips (2-5 s of speech; clean, noise and far-field; AU and GB voices) with the PC's
real CPU/GPU, through the same Wyoming server Home Assistant would use, and writes pc-results/<stamp>/ with transcripts,
latency per clip, peak RAM, VRAM (Windows GPU counters) and a summary.md to send back.

  python pc_bench.py STAGE OUT_DIR [--threads 8] [--whisper-cpp DIR] [--llm-load]
  STAGE: cpu      via the Wyoming server: faster-whisper small.en int8 + house prompt + --vad-filter (the recommendation), the same
                  with 8 vs 4 threads, Parakeet TDT 0.6B v2 int8 (the fast fallback), faster-whisper large-v3-turbo int8 (reference)
         directml onnx-asr Parakeet v2 on the GPU through DirectML (separate venv: onnxruntime-directml)
         vulkan   whisper.cpp large-v3-turbo q5_0 via whisper-server (needs --whisper-cpp: a Vulkan build's bin folder)
         score    score everything in OUT_DIR and write summary.md
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SCRIPTS = os.path.join(ROOT, "scripts")
AUDIO = os.path.join(ROOT, "testset", "audio")
SUBSET = os.path.join(HERE, "manifest_pc.jsonl")
PROMPT = open(os.path.join(ROOT, "testset", "house_prompt.txt")).read().strip()


class VramSampler:
    """Peak dedicated GPU memory on Windows (all processes), from the 'GPU Adapter Memory' performance counter."""

    def __init__(self):
        self.peak, self.base, self._stop = None, None, threading.Event()

    def read(self):
        if platform.system() != "Windows":
            return None
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples | "
                                  "Measure-Object -Property CookedValue -Maximum | Select -Expand Maximum"],
                                 capture_output=True, text=True, timeout=20).stdout.strip()
            return float(out) / 2**20
        except Exception:  # noqa: BLE001
            return None

    def __enter__(self):
        self.base = self.read()

        def loop():
            while not self._stop.is_set():
                v = self.read()
                if v is not None:
                    self.peak = max(self.peak or 0, v)
                time.sleep(1)

        self._t = threading.Thread(target=loop, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()


def llm_load(stop):
    """Optional: keep Ollama generating while STT runs, to see GPU contention (needs `ollama` on PATH, a model loaded)."""
    model = os.environ.get("OLLAMA_MODEL", "")
    while not stop.is_set() and model:
        subprocess.run(["ollama", "run", model, "Write two sentences about the weather."], capture_output=True, timeout=120)


def wyoming(name, out, threads, *server_args):
    data = os.path.join(out, "..", "models")
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "wyoming_bench.py"), name, SUBSET, AUDIO, out, "--",
                    "--data-dir", data, "--language", "en", "--cpu-threads", str(threads), *server_args], check=False)


def stage_cpu(out, threads):
    small = ("--stt-library", "faster-whisper", "--model", "small.en", "--compute-type", "int8", "--beam-size", "5",
             "--initial-prompt", PROMPT, "--vad-filter")
    wyoming(f"pc-fw-small.en-int8+prompt-vadfilter-{threads}t", out, threads, *small)
    wyoming("pc-fw-small.en-int8+prompt-vadfilter-4t", out, 4, *small)
    wyoming("pc-parakeet-v2-int8-cpu", out, threads, "--stt-library", "sherpa", "--model", "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8")
    wyoming("pc-fw-large-v3-turbo-int8-cpu", out, threads, "--stt-library", "faster-whisper", "--model", "large-v3-turbo",
            "--compute-type", "int8", "--beam-size", "5")


def stage_directml(out):
    import numpy as np
    import onnx_asr
    import soundfile as sf
    clips = [json.loads(l) for l in open(SUBSET)]
    t = time.perf_counter()
    model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", providers=["DmlExecutionProvider", "CPUExecutionProvider"])
    load_s = time.perf_counter() - t
    with VramSampler() as v:
        model.recognize(sf.read(os.path.join(AUDIO, clips[0]["clip"]), dtype="float32")[0])  # warm-up
        lat = []
        with open(os.path.join(out, "pc-parakeet-v2-directml.jsonl"), "w") as f:
            for c in clips:
                x = sf.read(os.path.join(AUDIO, c["clip"]), dtype="float32")[0]
                t = time.perf_counter()
                text = model.recognize(x)
                dt = time.perf_counter() - t
                lat.append(dt)
                f.write(json.dumps({"clip": c["clip"], "id": c["id"], "hyp": text, "latency_s": round(dt, 4), "dur": c["dur"]}) + "\n")
    json.dump({"name": "pc-parakeet-v2-directml", "load_s": round(load_s, 1), "latency_p50_s": round(float(np.median(lat)), 3),
               "latency_p95_s": round(float(np.percentile(lat, 95)), 3), "vram_before_mb": v.base, "vram_peak_mb": v.peak},
              open(os.path.join(out, "pc-parakeet-v2-directml.meta.json"), "w"), indent=1)


def stage_vulkan(out, wcpp, threads):
    from huggingface_hub import hf_hub_download
    model = hf_hub_download("ggerganov/whisper.cpp", "ggml-large-v3-turbo-q5_0.bin", local_dir=os.path.join(out, "..", "models"))
    env = dict(os.environ, WHISPER_CPP=wcpp)
    with VramSampler() as v:
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "cpp_bench.py"), "whisper", "pc-whispercpp-turbo-q5_0-vulkan", model, SUBSET,
                        AUDIO, out, "--threads", str(threads)], env=env, check=False)
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "cpp_bench.py"), "whisper", "pc-whispercpp-turbo-q5_0-vulkan+prompt", model,
                        SUBSET, AUDIO, out, "--threads", str(threads), "--prompt-file",
                        os.path.join(ROOT, "testset", "house_prompt.txt")], env=env, check=False)
    m = os.path.join(out, "pc-whispercpp-turbo-q5_0-vulkan.meta.json")
    if os.path.exists(m):
        d = json.load(open(m))
        d.update(vram_before_mb=v.base, vram_peak_mb=v.peak)
        json.dump(d, open(m, "w"), indent=1)


def stage_score(out):
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "score.py"), out, out, "--min-rows", "1"], check=False)
    info = {"machine": platform.processor() or platform.machine(), "system": platform.platform(), "python": platform.python_version()}
    table = os.path.join(out, "accuracy_speed.md")
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write("# PC bench (60 clips, 2-5 s)\n\n" + (open(table).read() if os.path.exists(table) else "(no scored runs)\n"))
        f.write("\nMachine: " + json.dumps(info) + "\n")
        for fn in sorted(os.listdir(out)):
            if fn.endswith(".meta.json"):
                f.write(f"\n`{fn}`: {open(os.path.join(out, fn)).read().strip()}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["cpu", "directml", "vulkan", "score"])
    ap.add_argument("out")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--whisper-cpp")
    ap.add_argument("--llm-load", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stop = threading.Event()
    if a.llm_load:
        threading.Thread(target=llm_load, args=(stop,), daemon=True).start()
    if a.stage == "cpu":
        stage_cpu(a.out, a.threads)
    elif a.stage == "directml":
        stage_directml(a.out)
    elif a.stage == "vulkan":
        stage_vulkan(a.out, a.whisper_cpp, a.threads)
    else:
        stage_score(a.out)
    stop.set()


if __name__ == "__main__":
    main()
