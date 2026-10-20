# DRAFT: House AI and Energy review

Atlas should compare the consequences of running a particular load now, later today and in the next free window. The clock supplies constraints; it does not supply the answer. HA computes the evidence and comparisons. Atlas explains the useful choice, the main reason and any uncertainty that could change it.

## What the records establish

The owner confirms free grid import in [11:00,14:00) Sydney time and a $1 daily credit only when gross grid import is strictly below 0.030 kWh in **each** of [18:00,19:00) and [19:00,20:00). Export never cancels import. A completed failing hour cannot be repaired by waiting or exporting later. HA's meter indicates eligibility; the retailer's bill decides payment.

Energy records describe an SH10RT/SBR256, about 25.6 kWh, a planned 20% reserve and a separate 35% intentional-export floor. These are different constraints. A battery below 35% is not necessarily empty or unable to supply the house. The native midday charge schedule aims for 100% around 11:01–13:59; HA does not send charge commands in that window. A target is not evidence that charging succeeded. The evening controller normally maintains approximately 500 W export bias. Its 15 Wh engineering target is not the retailer's 30 Wh threshold. Neither the 5 kW uplift cap nor the captured 10.6 kW inverter setting proves spare household power capacity.

The current-state record dated 19 October says the controller was healthy after the 14:25 restart and credits met on 10–17 October. Those are dated records, not today's live readings or a future guarantee. The economics review finds very little paid import historically: this supports considering “little difference”, but cannot prove today's marginal cost. Its paid/free split is estimated, its savings definition is owner-specific, and the August VPP-to-HA change breaks comparisons across regimes. Do not turn those savings into appliance savings or a current bill forecast.

The daily Atlas ledger started 17 October; credit history started 18 October. Daily totals cannot supply evening demand or SOC trajectories. Energy's README records older hourly and SOC exports, but this draft does not ingest that archive. Appliance energy/duration profiles, calibrated delivered battery capacity, solar-energy forecasts, matched-day demand cards and today's actual readings: **NO DATA**. The README explicitly records no AC energy measurement. A weather forecast is not a solar-kWh forecast. The existing prompt/history file still contains blanket timing advice even though fact-cards.mjs has removed the four conclusions: all conflicting prose needs review together, not another sentence appended to it.

## A small reasoning sequence

1. Establish the question: appliance/programme, proposed start, duration, deadline, and whether comfort or urgency matters. Use current conversation facts; ask at most one useful question if it changes the choice. An unknown programme does not justify a generic dryer kWh figure.
2. Establish evidence quality. Check timestamps, coverage, units, rule version, forecast dates and controller-status observation. Return the supported fragment if a dependency is missing. A bigger model cannot retrieve absent house facts.
3. Compare feasible choices: now, an available pre-credit interval, after 20:00, and next 11:00. Do not offer a choice after the user's deadline. Consider the whole cycle and concurrent loads, not just its start. Free grid energy does not guarantee that every load can run simultaneously or that the battery will finish charging.
4. Compute two separate constraints for each option: **energy** available through the required horizon, and **power/transient import** risk during each credit hour. Include house baseline, confirmed loads, heat-related demand, charging opportunity and the controller's observed export overhead. Never count tomorrow's solar as energy available tonight. Include overnight and tomorrow-before-11 demand when assessing a night-time load.
5. Prefer a choice only when its advantage survives plausible low/high demand and solar cases. Otherwise say either “little difference” (both choices supported and differences small) or “can't distinguish” (missing evidence). Those are not interchangeable. Normal household use and comfort precede the credit; offer optional-load deferral, never deprivation for $1.
6. Give a short recommendation, one or two decisive facts and the relevant limit. Recompute on a later question; this design adds no watcher, schedule, control or promised follow-up.

## Confidence is about the claim

| Level | Proposed evidence test | Natural wording |
|---|---|---|
| High for a rule/observation | Valid clock/rule, or complete valid meter evidence; no forecast required | “The free window ends at …”; “The meter shows the limit was exceeded.” |
| Medium for advice | Fresh relevant readings, representative load profile, adequate matched history, explicit conservative ranges; same preference across tested ranges | “I'd run it now”; “It looks comfortable on the current estimate.” |
| Low | Sparse/mismatched history, uncertain weather/load, or options reverse across ranges | “I'd lean towards …, but … could change that.” |
| NO DATA for the requested claim | A critical dependency is absent/invalid/stale | “I can give the timing, but I don't have … to judge tonight.” |

Forecast-dependent advice is capped at medium until local backtesting demonstrates calibrated uncertainty. No percentage probability is available. Confidence in a tariff fact can be high while confidence in battery coverage is NO DATA. A strong recommendation to defer an optional load can rest on a clear shortage; confidence in the exact credit outcome remains low. Even a robust budget is not a battery-runtime promise.

“It doesn't matter much” requires both options to meet the deadline and comfort need, neither to introduce material credit or reserve risk, and their estimated extra paid-import/cost ranges to overlap within an explicitly reviewed materiality tolerance. A proposed test tolerance is 0.1 kWh and about 5c; these are **DRAFT evaluation choices**, not owner preferences or production settings. Losses/export opportunity value must be included or identified as unquantified. With plenty of headroom but no full marginal-cost model, say “little practical difference on these estimates”, not “exactly the same cost” or “free”.

## Proportionate implementation path

First expose trustworthy current flows, SOC trend, time/cycle overlap and both credit-hour meter states. Remove contradictory blanket prompt advice. That already supports better bounded answers without a prediction engine. Next add measured programme profiles and a small matched-history summary; only then add calibrated energy envelopes. All are HA-owned read-only calculations using authorised sources. Entity names for new cards, live mappings, installed freshness checks and forecast availability are **NO DATA** until HA verifies them.

House AI owns prompt and blind scoring; HA owns deterministic cards and source quality; Energy reviews definitions, sign conventions, floors and advice. Timers remain ahead of this work. No Energy controller edits, reloads, helper writes, installations, household connections or deployment are part of run49. Existing never-by-implication controls, shelved features and accepted micro-draw remain untouched. the owner sees the samples and decides before any later go-live.
