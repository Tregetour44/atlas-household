import sys, json, numpy as np
sys.path.insert(0, "/home/user/atlas-household/voice-fablemix")
import kokoro_backend as kb
synth, _ = kb.kokoro_synth("/home/user/atlas-household/voice-fablemix/model", threads=4)
g2p = kb.build_g2p()
def sil(y, thr_db=-40):
    hop = 240; fr = len(y) // hop
    e = np.array([np.sqrt(np.mean(y[i*hop:(i+1)*hop] ** 2)) + 1e-9 for i in range(fr)])
    db = 20 * np.log10(e / e.max()); v = np.flatnonzero(db > thr_db)
    gaps = []; run = 0
    for x in (db > thr_db)[v[0]:v[-1] + 1]:
        if x:
            if run >= 8: gaps.append(run * 10)
            run = 0
        else: run += 1
    return v[0] * 10, (fr - 1 - v[-1]) * 10, gaps
kb.MERGE_BELOW = 0; kb.CLAUSE_SPLIT = 40
texts = ["Done. Kitchen lights off.", "Timer set: Robe Downlight off in ten minutes. Say cancel that to stop it.",
         "Solar did rather well today: you made just over thirty kilowatt hours, used about half of it, and sent the rest to the grid.",
         "Careful. There's a storm warning from six this evening, with gusts up to ninety kilometres an hour.", "Would you like the blinds down as well, or shall I leave them?"]
for t in texts:
    whole = np.frombuffer(b"".join(synth.__wrapped__(t) if hasattr(synth, "__wrapped__") else []), "<i2")
    for ch in kb.plan_chunks(g2p, t):
        pass
    print("TEXT", t[:40])
    kb.MERGE_BELOW = 1000; kb.CLAUSE_SPLIT = 510
    y = np.frombuffer(b"".join(synth(t)), "<i2").astype(np.float32) / 32768
    print("  whole: lead %d ms, tail %d ms, internal pauses %s" % sil(y))
    kb.MERGE_BELOW = 0; kb.CLAUSE_SPLIT = 40
    for c in synth(t):
        y = np.frombuffer(c, "<i2").astype(np.float32) / 32768
        print("  chunk: lead %d ms, tail %d ms, internal %s" % sil(y))
