"""Speed and memory of kokoro_backend on this machine. Run on an idle CPU.

    python -I bench.py MODEL_DIR [threads,...]          -> one JSON line per measurement on stdout

Each thread count runs in a fresh child process, so load time, peak RAM and the cold first call are real:
* load_s: kokoro_synth() wall time (hash check + G2P + ONNX session), and the process's peak RSS after it;
* cold: the first synth() of a fresh process (time to first chunk, total), then warm: the median of 5 later calls;
* for the 3-, 15- and 40-word replies below: time to first audio (first chunk) and real-time factor (render time
  / audio length), plus peak RSS at the end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPLIES = {
    "short": "Kitchen lights off.",  # 3 words
    "medium": "I've turned the porch lights off, and the living room lamp is at forty percent.",  # 15 words
    "long": ("Solar did rather well today: you made just over thirty kilowatt hours and used about half of it. "
             "The battery filled up by early afternoon, so the rest went to the grid, and the evening should be "
             "nicely covered too."),  # 40 words
}

CHILD = r"""
import json, os, statistics, sys, time
t0 = time.perf_counter()
sys.path.insert(0, sys.argv[1])
import kokoro_backend as kb
synth, rate = kb.kokoro_synth(sys.argv[2], threads=int(sys.argv[3]))
load_s = time.perf_counter() - t0

def peak_mb():
    if sys.platform == "win32":
        import ctypes, ctypes.wintypes as w
        class PMC(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                        ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / 2**20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

def run(text):
    t = time.perf_counter(); first = None; n = 0
    for c in synth(text):
        first = first if first is not None else time.perf_counter() - t
        n += len(c)
    total = time.perf_counter() - t
    return first, total, n / 2 / rate

out = {"threads": int(sys.argv[3]), "load_s": round(load_s, 2), "rss_after_load_mb": round(peak_mb())}
replies = json.loads(sys.argv[4])
f, tot, dur = run(replies["medium"])
out["cold_medium"] = {"first_s": round(f, 3), "total_s": round(tot, 3), "audio_s": round(dur, 2)}
for name, text in replies.items():
    rs = [run(text) for _ in range(5)]
    out[name] = {"first_s": round(statistics.median(r[0] for r in rs), 3),
                 "total_s": round(statistics.median(r[1] for r in rs), 3), "audio_s": round(rs[0][2], 2),
                 "rtf": round(statistics.median(r[1] / r[2] for r in rs), 3)}
out["peak_rss_mb"] = round(peak_mb())
print(json.dumps(out))
"""


def main() -> None:
    model_dir = sys.argv[1]
    threads = [int(t) for t in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1, 2, 4]
    backend = os.path.dirname(HERE)
    for t in threads:
        proc = subprocess.run([sys.executable, "-I", "-c", CHILD, backend, model_dir, str(t), json.dumps(REPLIES)],
                              capture_output=True, text=True, check=True)
        print(proc.stdout.strip(), flush=True)


if __name__ == "__main__":
    main()
