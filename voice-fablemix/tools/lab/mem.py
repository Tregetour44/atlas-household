import sys, time, gc, resource
def rss(): return int([l for l in open("/proc/self/status") if l.startswith("VmRSS")][0].split()[1]) // 1024
def peak(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
sys.path.insert(0, "."); r0 = rss()
import numpy, onnxruntime, spacy, misaki.en  # noqa
r1 = rss()
import kokoro_backend as kb
if sys.argv[1] in ("noarena", "noprepack", "basic"):
    import onnxruntime as ort
    _SO = ort.SessionOptions
    class SO(_SO):
        def __init__(self):
            super().__init__()
            if sys.argv[1] == "noarena": self.enable_cpu_mem_arena = False
            if sys.argv[1] == "noprepack": self.add_session_config_entry("session.disable_prepacking", "1")
            if sys.argv[1] == "basic": self.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    ort.SessionOptions = SO
s, _ = kb.kokoro_synth("model", threads=4); gc.collect(); r2 = rss(); p2 = peak()
t = time.perf_counter(); list(s("I've turned the porch lights off, and the living room lamp is at forty percent.")); t1 = time.perf_counter() - t
t = time.perf_counter(); list(s("I've turned the porch lights off, and the living room lamp is at forty percent.")); t2 = time.perf_counter() - t
list(s("Solar did rather well today: you made just over thirty kilowatt hours and used about half of it, and sent the rest to the grid while the battery filled up by early afternoon, which is rather good for October."))
print(sys.argv[1], f"start {r0} MB, after imports {r1} MB, after load {r2} MB (peak {p2}), after synth {rss()} MB (peak {peak()}), medium {t1:.2f}s/{t2:.2f}s")
