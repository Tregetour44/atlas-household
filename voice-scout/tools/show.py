import sys, json
for l in sys.stdin:
    if not l.startswith("{"): continue
    r = json.loads(l); r['f0'] = r['f0'] or 0; r['f0_st'] = r['f0_st'] or 0; print(f"{r['voice']:28s} {r['id']} utmos {r['utmos']:.2f} f0 {r['f0']:6.1f} st {r['f0_st']:.2f} wer {r['wer']:.2f} wps {r['wps']:.2f} {r['accent']:10s} {r['eng_us']:+.2f} sim {r['sim_cbfable']:.2f} | {r['asr'][:70]}")
