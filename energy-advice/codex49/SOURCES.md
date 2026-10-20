# DRAFT: House AI and Energy review

`source-index.json` gives full paths, bytes and whole-file SHA-256 for the explicit source records used. These are local-file provenance checks, not live configuration or source/loaded parity checks. No secret, .storage, backup or Handover/Credentials file was opened. No household service, model or network endpoint was called. No Git operations or installs were made.

| Evidence | Design consequence |
|---|---|
| PCSteward directive 20261018-2225 | Four fixed conclusions rejected; reason from history, forecast and trends; House AI leads, Energy reviews; owner sees 6–8 samples; timers first. |
| prompt-template.jinja and energy-history.jinja.txt | Richer history/weather context exists in source, but blanket load and night advice remains; revise conflicting prose together. Source files do not prove current loaded prompt. |
| fact-cards.mjs | Four conclusion lines explicitly removed; battery AC contribution sign/source documented; display freshness policy exists but is not enough to prove sub-hour credit risk. |
| energy-input-20261017-1645.md | Gross hourly credit semantics, no netting, strict threshold, bill caveat; daily end states, not utility meters on resetting daily sensors; read-only HA-owned facts. |
| FACT-CARDS-SPEC and RESULTS-T2-CARDS | Recorded failures: house draw attributed to import/appliance, time-window reversal, invented free allowance, missing cycle duration and bill caveats. Historical modest improvements do not prove run49 accuracy. |
| HouseAI/TestSuite README, helper-contracts, ADOPTED, scenarios | Preserve frozen baselines, necessary unknowns, coverage/freshness, zero fabricated figures/actions, no live Assist evaluation and semantic review. Earlier timing defaults are superseded by owner's new directive. |
| Run42 kit/contracts/judge | Canonical input/transcript binding, separate semantic judgement and latency cohorts; no runtime inference from nominal SOC; 120-case original generator is not extensible just by changing case count. |
| Energy CURRENT-STATE, README, all eight Rules files | Distinguish 20% reserve/35% export floor, energy/power limits and 15/30 Wh thresholds. Normal house use precedes credit. No controller changes, no recovery/re-arm instruction, no implicit revival of shelved work. Current-state record wins over dated README status. |
| PCSteward economics review | Historical paid import generally small, free-window charging important; paid/free split estimated; VPP/HA regime break and micro-draw caveats. Avoid invented marginal savings from aggregate history. |

**NO DATA:** current household readings, current loaded prompt, live presence of proposed cards, appliance programme profiles, solar-kWh forecast provider/calibration, delivered battery energy calibration, representative evening/hot-day comparison values, contemporary tariffs beyond owner-confirmed rules, export value, actual model improvement/latency, independent Energy/House AI review and owner preference. Scenario figures are explicitly synthetic, so they do not fill these gaps.

No new history extraction was performed. Energy's older hourly/SOC archive is recorded in its README; its data files were not opened. The model design explains how a later approved HA adapter could use complete same-regime intervals rather than inventing evening demand from the young Atlas daily ledger.
