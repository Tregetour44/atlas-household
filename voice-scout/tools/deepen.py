"""Make a deeper, 'older' variant of a synthetic reference with the WORLD vocoder:
F0 scaled by 2^(-st/12), spectral envelope warped by alpha (<1 lowers formants: a larger vocal tract).
Usage: deepen.py in.wav out.wav semitones alpha"""
import sys, numpy as np, soundfile as sf, librosa, pyworld as pw
y, sr = librosa.load(sys.argv[1], sr=24000); y = y.astype(np.float64)
st, alpha = float(sys.argv[3]), float(sys.argv[4])
f0, t = pw.harvest(y, sr, f0_floor=55, f0_ceil=400); sp = pw.cheaptrick(y, f0, t, sr); ap = pw.d4c(y, f0, t, sr)
n = sp.shape[1]; src = np.minimum(np.arange(n) / alpha, n - 1)  # out[k] = in[k/alpha]: alpha<1 moves formants down
sp2 = np.stack([np.interp(src, np.arange(n), r) for r in sp]); ap2 = np.stack([np.interp(src, np.arange(n), r) for r in ap])
out = pw.synthesize(f0 * 2 ** (-st / 12), sp2, ap2, sr)
sf.write(sys.argv[2], (out / max(1e-6, np.abs(out).max()) * 0.9).astype(np.float32), sr)
