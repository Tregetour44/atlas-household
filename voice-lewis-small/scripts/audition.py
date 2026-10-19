"""Step 1 audition: render the dev sentences with a candidate engine and time it.
usage: python audition.py <engine> <lines.txt> <out_dir> <stats.jsonl> <reference.wav>
engines: chatterbox (teacher), chatterbox-turbo, pocket, kokoro-bm_lewis
"""
import sys, os
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import run, read_lines

engine, lines_path, out_dir, stats, ref = sys.argv[1:6]
torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
lines = read_lines(lines_path)

if engine == "chatterbox":  # the teacher, exactly as voice-samples/tools/chatterbox_run.py
    from chatterbox.tts import ChatterboxTTS
    m = ChatterboxTTS.from_pretrained(device="cpu")
    def synth(text):
        torch.manual_seed(7)
        return m.generate(text, audio_prompt_path=ref, exaggeration=0.4, cfg_weight=0.4).squeeze().numpy(), m.sr
elif engine == "chatterbox-turbo":  # 350M; ignores exaggeration/cfg_weight
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    m = ChatterboxTurboTTS.from_pretrained(device="cpu")
    m.prepare_conditionals(ref)
    def synth(text):
        torch.manual_seed(7)
        return m.generate(text).squeeze().numpy(), m.sr
elif engine == "pocket":
    from pocket_tts import TTSModel
    m = TTSModel.load_model()
    state = m.get_state_for_audio_prompt(ref)
    def synth(text):
        torch.manual_seed(7)
        return m.generate_audio(state, text).numpy(), m.sample_rate
elif engine == "kokoro-bm_lewis":
    from kokoro import KPipeline
    pipe = KPipeline(lang_code="b")
    def synth(text):
        torch.manual_seed(0)
        chunks = [a.numpy() for _, _, a in pipe(text, voice="bm_lewis", speed=0.92)]
        return np.concatenate(chunks), 24000
else:
    raise SystemExit(f"unknown engine {engine}")

run(engine, synth, lines, out_dir, stats)
