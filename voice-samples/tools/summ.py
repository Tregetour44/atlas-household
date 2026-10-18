import json,collections,sys
d=collections.defaultdict(list)
for f in sys.argv[1:]:
  for l in (x for x in open(f) if x.startswith("{")):
    r=json.loads(l); k=r["file"].rsplit("-",1)[0]; d[k].append(r)
for k,v in sorted(d.items()):
    n=len(v); g=lambda key: sum(r.get(key,0) for r in v)/n
    print(f"{k:42s} n={n} utmos={g('utmos'):.2f} engVsUS={g('eng_minus_us'):+.2f} topEng={sum(r['accent'][0][0]=='england' for r in v)}/{n} wer={g('wer'):.2f} f0={g('f0_hz'):.0f} wps={g('wps'):.2f} top={v[0]['accent'][0]}")
