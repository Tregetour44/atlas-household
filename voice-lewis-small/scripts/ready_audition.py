"""Ready-made voice audition (no training): render the 4 sample lines (S1..S4) and the 10 audition lines (L01..L10).
usage: ready_audition.py <engine> <all14.txt> <out_dir> <timing.jsonl> <voice spec>...
  kokoro  specs: "bm_fable", "bm_fable:0.7+bm_george:0.3@0.95" (weighted style-vector blend, optional @speed)
  piper   specs: "<model.onnx>" or "<model.onnx>#<speaker_id>"
  pocket  specs: catalog voice names
"""
import json, os, sys, time
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
engine, lines_path, out, timing = sys.argv[1:5]
specs = sys.argv[5:]
lines = [l.strip() for l in open(lines_path, encoding="utf-8") if l.strip()]
names = [f"S{i}" for i in range(1, 5)] + [f"L{i:02d}" for i in range(1, 11)]
os.makedirs(out, exist_ok=True)

def tagof(spec):
    t = os.path.basename(spec).replace(".onnx", "").replace(":", "").replace("+", "_").replace("@", "-s").replace("#", "-spk")
    return f"{engine}-{t}"

if engine == "kokoro":
    import torch
    from kokoro import KPipeline
    torch.set_num_threads(4)
    pipe = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")
    def make(spec):
        spec, _, sp = spec.partition("@"); speed = float(sp or 1.0)
        parts = [p.split(":") for p in spec.split("+")]
        if len(parts) == 1:
            voice = parts[0][0]
        else:
            voice = sum(float(w) * pipe.load_voice(v) for v, w in parts)
        def synth(text):
            torch.manual_seed(0)
            return np.concatenate([a.numpy() for _, _, a in pipe(text, voice=voice, speed=speed)]), 24000
        return synth
elif engine == "piper":
    from piper import PiperVoice, SynthesisConfig
    def make(spec):
        path, _, spk = spec.partition("#")
        v = PiperVoice.load(path)
        cfg = SynthesisConfig(speaker_id=int(spk) if spk else None)
        def synth(text):
            return np.concatenate([c.audio_float_array for c in v.synthesize(text, syn_config=cfg)]), v.config.sample_rate
        return synth
elif engine == "pocket":
    import torch
    from pocket_tts import TTSModel
    m = TTSModel.load_model()
    def make(spec):
        st = m.get_state_for_audio_prompt(spec)
        def synth(text):
            torch.manual_seed(7)
            return m.generate_audio(st, text).numpy(), m.sample_rate
        return synth

for spec in specs:
    tag = tagof(spec); synth = make(spec); synth("Warm up, please.")
    tot_s = tot_a = 0.0; rtfs = []
    for n, text in zip(names, lines):
        t = time.perf_counter(); a, sr = synth(text); dt = time.perf_counter() - t
        sf.write(os.path.join(out, f"{tag}-{n}.wav"), np.asarray(a, dtype=np.float32), sr, subtype="PCM_16")
        rtfs.append(dt / (len(a) / sr)); tot_s += dt; tot_a += len(a) / sr
    rec = dict(tag=tag, spec=spec, rtf_mean=round(tot_s / tot_a, 3), rtf_p95=round(float(np.percentile(rtfs, 95)), 3))
    open(timing, "a").write(json.dumps(rec) + "\n"); print(rec, flush=True)
