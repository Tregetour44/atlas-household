"""Atlas voice: text -> WAV with the voice-lewis-small Piper model (CPU, ONNX Runtime).
usage: speak.py "text" out.wav [--model model/en_GB-lewis_small-medium.onnx] [--length-scale 1.0]
Needs only `pip install piper-tts` (1.8+). Text goes through atlas_text.normalise first."""
import argparse, os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_text import normalise
from piper import PiperVoice, SynthesisConfig

ap = argparse.ArgumentParser()
ap.add_argument("text"); ap.add_argument("out")
ap.add_argument("--model", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model", "en_GB-lewis_small-medium.onnx"))
ap.add_argument("--length-scale", type=float, default=None, help="> 1 slower; default from the model's .onnx.json")
a = ap.parse_args()
voice = PiperVoice.load(a.model)
with wave.open(a.out, "wb") as w:
    voice.synthesize_wav(normalise(a.text), w, syn_config=SynthesisConfig(length_scale=a.length_scale))
