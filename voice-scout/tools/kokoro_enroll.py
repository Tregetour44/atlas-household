"""inno-kokoro: reference clip -> Kokoro voice pack (.pt). Usage: kokoro_enroll.py ref.wav out.pt"""
import sys, torch
from inno_kokoro.enroll import Tuner, enroll, read
pack, weights = enroll(*read(sys.argv[1]), Tuner(device="cpu"))
torch.save(pack, sys.argv[2]); print(sys.argv[2], {k: round(v, 2) for k, v in sorted(weights.items(), key=lambda kv: -kv[1])})
