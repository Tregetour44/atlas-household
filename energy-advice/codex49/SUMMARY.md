# DRAFT: House AI and Energy review

Atlas should recommend a time because the particular load fits the available solar, battery and expected household demand—not just because the clock is in a tariff window. This draft separates battery energy from short import spikes, treats comfort and deadlines as real needs, and allows “little difference” only when both choices are supported. It supplies proposed read-only fact cards, brief prompt guidance, 40 synthetic scenarios compatible with run42’s scorer and eight sample answers. Everything is for House AI and Energy review; no live system, Git state or controller was changed, and no household service or model was contacted. Actual advice improvement, live card availability, forecast calibration and owner preference are NO DATA.

## Design in brief

- HA supplies the maths: whole-cycle timing, SOC trend, separate reserve/export margins, remaining solar, representative evening/overnight demand, programme profiles, each credit hour and uncertainty ranges.
- Compare now, a feasible later interval and the next free window. Paid tariff is not proof of paid import. Tomorrow’s solar cannot cover tonight. Free grid does not mean unlimited simultaneous power.
- Keep credit status separate from risk: each hour must stay strictly below 0.030 kWh; no netting or averaging. A completed miss cannot be repaired. HA indicates; the bill decides.
- Confidence belongs to each claim. Give a supported recommendation, a specific missing-data answer or an evidence-backed “little difference”; never a battery-runtime or credit promise.
- Atlas gives the advice and one short reason, with at most one apt question. No controller changes, lectures or routine offers.
- Validation: 55 offline formula, fixture and scorer checks passed. These are not model or production HA tests. 32 development cases and 8 visible holdouts; 27 original run42 cases retained as separate regressions.

## Eight sample answers

These are authored answers to synthetic situations, not live readings or measured Atlas responses. Full fact snapshots are in SAMPLES.md and SCENARIOS.md.

**EN002 — Should I wait until 11 for the washing?**

Run it now. The solar surplus covers this cycle on the current estimate, and waiting would miss your deadline.

**EN001 — Dryer now or tomorrow?**

I'd leave it for tomorrow's free window. This cycle runs past today's free power, and the battery is already low.

**EN003 — Is the dishwasher expensive to run now?**

It looks fine to run now: the solar estimate covers this cycle. Being outside the free window doesn't mean you'll need paid grid power.

**EN008 — Dryer this afternoon?**

I'd leave the dryer until tomorrow. The battery is low and falling, with little solar left to help tonight.

**EN004 — Leave the AC off until 8 to save the credit?**

Use the cooling if you need it. The battery budget looks comfortable, though a load spike could still affect the credit.

**EN013 — Dishwasher now or tomorrow—is there much difference?**

Not much on these estimates. The battery has room for the dishwasher and the overnight demand, so either timing looks reasonable.

**EN012 — Will tonight be fine for the battery?**

I can't judge tonight from the charge alone. I'm missing the remaining solar outlook and a useful evening-demand estimate.

**EN017 — Did we get the credit with exactly 0.030 in the first hour?**

The meter says it missed: each hour has to be strictly below the limit. The bill decides the actual credit.

## Files and SHA-256

Start with this summary; DESIGN.md and FACT-CARDS.md explain the design, PROMPT.md supplies the short guidance, and EVALUATION.md explains the scorer contract and limits. All output files are listed below. Ordinary hashes cover exact whole-file bytes except SUMMARY.md’s explicitly canonical self-hash. Source provenance hashes are in source-index.json.

| File | Bytes | SHA-256 |
|---|---:|---|
| [build.py](build.py) | 30816 | `15c64c969a80183a43c86b3bf75e544ea719757547be9479c30e671666804a83` |
| [compatibility.json](compatibility.json) | 432 | `5a65a1e1c75061146c56b1755fd1aa32d5b77c6b1d942ea0f6b80c84a6898734` |
| [DESIGN.md](DESIGN.md) | 7542 | `ad4a5281e05ea3e0c82e1a3303e338c9197a1f5f609903220f29efa6aa9d4525` |
| [EVALUATION.md](EVALUATION.md) | 6586 | `18de9243b0f55ef7d08b0c92ed51e914e37e7247754a6ed48a9f638163b61ab1` |
| [expected.json](expected.json) | 203397 | `bb67b61fae21ce96e997c2c3888fd2294c78148767ad95df6a21dd38362cece8` |
| [FACT-CARDS.md](FACT-CARDS.md) | 11395 | `bdec5321eaff0dbedec05b63253a9d3a1275d272c4f3c49a20fbb79fd532bad2` |
| [judge-template.json](judge-template.json) | 16828 | `94b3159aa390f04a090506e7efbc7c7e8e41fdcfb13af09199a522b1d7ad3797` |
| [kit.py](kit.py) | 31602 | `67a9726b8ec3ac9b0913ded01aedb2f6da71b94e8221d138418af70220f0825c` |
| [prepare_sources.py](prepare_sources.py) | 3793 | `75a12a6a7aecbf9ea1c0bad5d80566dcdec22229e16e745e5e6f1879fc65d9fe` |
| [PROMPT.md](PROMPT.md) | 1763 | `39ebce16d845b2218c685abbde6943fa220d6020a0cbccf42e4a04292e2d7c87` |
| [reference.py](reference.py) | 2364 | `c4f55438ddc59a6b44d5e1d189fe5713ad292983f5013f33bea75eeee731ce63` |
| [run42-energy-regressions.json](run42-energy-regressions.json) | 31657 | `22b9029f1a8fd7e20d4efcdb9dca4ecd38a9acf3705bb494ad613484084f66d6` |
| [SAMPLES.md](SAMPLES.md) | 3861 | `b9c06f6974c78d3de0fdeceb63429e1664f09466e35c3fe824dc8914c0053e70` |
| [scenarios.json](scenarios.json) | 110411 | `541da7bff9b43e8767f20c32133a93b520cb138715a52d0631ce0208cad400d7` |
| [SCENARIOS.md](SCENARIOS.md) | 31470 | `bd6080d8240bdeb865bffbac25b441cd76a413cda7536969073e84b212053a09` |
| [seal.py](seal.py) | 4606 | `86e44df2a3cdbc83851d792c23aa8698e8bc8b7b4a09a225f98b9cfa69182943` |
| [self-test-results.txt](self-test-results.txt) | 4262 | `aa7a330d200ad144ceab223bf261308c2ec22175bc9ff047ef2c629cacc4c1af` |
| [source-index.json](source-index.json) | 8325 | `b477eabb52392cebb0ea926a0bbc766318d7f10e535bb7b5a432c007e140b80c` |
| [SOURCES.md](SOURCES.md) | 3379 | `2611eea8e8ffaaf32350ab14a643f4cac8f0c60b08e87a85debc87aa0369669d` |
| [test_offline.py](test_offline.py) | 8133 | `c0b9c2fe778d7587f224b86ef0f4834879b723d5128c6774fa88ff5ecf427f80` |
| [transcript-template.json](transcript-template.json) | 10155 | `764218d5b06c79a2d93a3b3ffd3c1e0d6d2f2e34dbff65b57ad11b9b2f90360e` |
| [validation.json](validation.json) | 423 | `20e7430ce4a50abaa09a2f08a4bf35b8092f9066656db8147593a1d1268fb7d4` |
| [SUMMARY.md](SUMMARY.md) | canonical self-hash | `bc489bdec50e4e12ad9fb2084d52b26876629055989d04683cd77314629df20b` |

SUMMARY.md self-hash convention: UTF-8, LF newlines and final newline retained; replace only the 64 hexadecimal characters in its own table row with 64 zeros before hashing. An ordinary whole-file self-hash cannot practically be embedded in the same file; the final chat supplies that whole-file hash separately. Re-run seal.py after changing any output.
