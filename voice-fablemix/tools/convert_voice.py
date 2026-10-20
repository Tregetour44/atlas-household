"""Rebuild the voice files in bundle/ from their sources and check them (development tool; needs torch).

    python convert_voice.py kokoro-fablemix.pt bm_fable.pt OUT_DIR    (bm_fable.pt from hexgrad/Kokoro-82M voices/)

* en_GB-fablemix.npy: the voice-scout pack, values unchanged, as float32 [510, 1, 256] without pickle.
* en_GB-fablemix-short.npy: the pack used for short replies. The decoder half (timbre, columns 0-127) is the
  Fable-mix pack's own; the predictor half (prosody, columns 128-255) is 50 % bm_fable + 50 % the inno-kokoro
  fitted pack (flatter and deeper than bm_fable), set by SHORT_PRED below.
  The fitted pack is recovered exactly from the blend the scout made (decoder 50/50 and predictor 70/30 with
  bm_fable): fitted = 2 * mix - fable (decoder), (mix - 0.7 * fable) / 0.3 (predictor).
"""

import hashlib
import sys

import numpy as np
import torch

SHORT_PRED = {"fable": 0.5, "inno": 0.5}


def load(path: str) -> np.ndarray:
    return torch.load(path, weights_only=True).float().numpy()


def main() -> None:
    mix, fable = (load(p) for p in sys.argv[1:3])
    out = sys.argv[3]
    inno = np.concatenate([2 * mix[..., :128] - fable[..., :128], (mix[..., 128:] - 0.7 * fable[..., 128:]) / 0.3], -1)
    rebuilt = np.concatenate([0.5 * fable[..., :128] + 0.5 * inno[..., :128],
                              0.7 * fable[..., 128:] + 0.3 * inno[..., 128:]], -1)
    assert np.abs(rebuilt - mix).max() < 1e-6, "the scout's blend recipe does not reproduce the pack"
    packs = {"fable": fable, "inno": inno}
    pred = sum(w * packs[k] for k, w in SHORT_PRED.items())
    short = np.concatenate([mix[..., :128], pred[..., 128:]], -1).astype(np.float32)
    for name, arr in (("en_GB-fablemix.npy", mix.astype(np.float32)), ("en_GB-fablemix-short.npy", short)):
        assert arr.shape == (510, 1, 256)
        np.save(f"{out}/{name}", arr, allow_pickle=False)
        with open(f"{out}/{name}", "rb") as f:
            print(name, hashlib.sha256(f.read()).hexdigest())


if __name__ == "__main__":
    main()
