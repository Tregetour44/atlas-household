"""Atlas energy fact cards (energy-advice-build; Codex 49 FACT-CARDS, directive 20261018-2225 + am. 1). Pure Python, no HA import, read-only.

Every energy figure Atlas may say is computed here and handed to the model as finished text: the model quotes, it never adds, subtracts,
multiplies or divides (the owner, 20 Oct: "it couldnt even do basic arithmatic"). The cards are evidence for a tactical answer, not a script:
they compare running a named load tonight / now with the next free window, from the battery, the history of similar nights, the solar outlook
and the tariff and credit rules, and they say which way the estimate leans and why (the owner: "it should consider history, forecast, trends").

Inputs are plain values the HA adapter has already read (states, recorder statistics, the forecast helper). Rules that keep the figures honest:
  - missing, invalid or stale is None with a reason, never 0; a true 0 stays 0 [Codex 49 FACT-CARDS, "Bad input"];
  - booleans, numeric strings, NaN/inf, negative energy and SOC outside 0-100 are invalid;
  - percentage POINTS for the SOC trend; the battery budget is nominal (25.6 kWh recorded, not calibrated delivery) and says so;
  - the reserve (20%) and the export floor (35%) are different limits; neither is "empty";
  - tomorrow's solar never counts as energy tonight; whole-day means are never evening demand;
  - the credit is per hour, gross import strictly below 0.030 kWh in EACH of 18-19 and 19-20; export never offsets; HA indicates, the bill decides;
  - estimates are labelled as estimates, with their basis (days, range); rounding is for display only, after every comparison.
Nothing here reads or changes the battery, the inverter or the controller, and no card ever suggests changing them.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SYDNEY = ZoneInfo('Australia/Sydney')
RULES = {'free_start': 11 * 60, 'free_end': 14 * 60, 'credit_start': 18 * 60, 'credit_end': 20 * 60, 'credit_limit_kwh': 0.030,
         'credit_dollars': 1, 'paid_rate': 0.55, 'capacity_kwh': 25.6, 'reserve_pct': 20, 'export_floor_pct': 35}
# Freshness for advice (Codex 49 FACT-CARDS "Freshness"; the display limits in fact-cards.mjs): minutes since the reading last reported.
FRESH_MINUTES = {'power': 15, 'soc': 120, 'forecast': 120}
# DRAFT policy values for Energy's review (not owner preferences): the buffer that makes a margin "comfortable", and the matched-day minimum.
COMFORT_BUFFER_KWH = 1.0
MIN_MATCHED_DAYS = 5
HOT_DAY_C = 30          # a forecast high at or above this matches history days of the same band (within HOT_BAND_C)
HOT_BAND_C = 4

# Appliance programmes. 'typical' figures are general knowledge for common Australian appliances, NOT measured in this house; a measured
# profile (from HA's history or the person's own words) replaces them and is labelled measured. Each is (low kWh, high kWh, minutes).
PROFILES = {
    'dishwasher': (1.0, 1.5, 120),
    'washing machine': (0.5, 1.0, 90),
    'dryer': (2.0, 3.5, 120),
    'oven': (1.5, 2.5, 60),
    'pool pump': (1.5, 3.0, 240),
}
_LOAD_WORDS = [('dishwasher', r'dish ?washer|dishes'), ('washing machine', r'washing machine|(?<!dish)(?<!dish )washer\b|(the |a |some )?washing\b|a wash\b|load of washing'),
               ('dryer', r'dryer|drier|tumble'), ('oven', r'\boven\b'), ('pool pump', r'pool pump|pool filter')]


class Value:
    """A checked reading: value (or None) and, when None, the reason (missing / invalid / stale)."""
    __slots__ = ('value', 'reason', 'at', 'last')

    def __init__(self, value, reason: str | None = None, at: datetime | None = None, last: float | None = None) -> None:
        self.value, self.reason, self.at, self.last = value, reason, at, last   # last: a stale reading's value, never used as current

    def __bool__(self) -> bool:
        return self.value is not None


def number(v, *, lo: float | None = 0.0, hi: float | None = None) -> float | None:
    """A finite real number within [lo, hi], else None. Booleans and strings are not numbers (upstream normalises units)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        return None
    return float(v)


def reading(r, now: datetime, kind: str, *, lo: float | None = 0.0, hi: float | None = None) -> Value:
    """r is {'value': x, 'at': aware datetime or ISO text} (or None). Freshness by FRESH_MINUTES[kind]; kind None = no freshness limit
    (a daily total changes only when energy flows, so an unchanged total is not stale)."""
    if r is None or r.get('value') is None:
        return Value(None, 'not available')
    v = number(r['value'], lo=lo, hi=hi)
    if v is None:
        return Value(None, 'invalid reading')
    at = r.get('at')
    if isinstance(at, str):
        at = datetime.fromisoformat(at)
    if at is not None:
        if at.tzinfo is None:
            return Value(None, 'invalid reading (no time zone)')
        age = _mins(at, now)
        if age < -1:
            return Value(None, 'invalid reading (time in the future)')
        if kind and age > FRESH_MINUTES[kind]:
            return Value(None, f'stale (last reported {clock(at.astimezone(SYDNEY))})', at, v)
    return Value(v, None, at)


# ---- display (rounding happens here only, after every comparison) ----

def clock(t: datetime) -> str:
    """'9:40 pm', '11 am'."""
    h, m = t.hour, t.minute
    return f"{h % 12 or 12}{'' if m == 0 else f':{m:02d}'} {'am' if h < 12 else 'pm'}"


def hm(minutes: float) -> str:
    """A duration: '13 h 20 min', '45 min', '2 h'."""
    m = int(round(minutes))
    if m < 60:
        return f'{m} min'
    return f'{m // 60} h' + (f' {m % 60} min' if m % 60 else '')


def kwh(x: float) -> str:
    return f'{x:.2f} kWh' if 0 < abs(x) < 0.1 else f'{x:.1f} kWh'


def money(x: float) -> str:
    return f'${x:.2f}'


# ---- cards ----

def _mins(a: datetime, b: datetime) -> float:
    """Minutes from a to b, through UTC: Python subtracts same-zone datetimes as wall clock, which is wrong across a DST change."""
    return (b.astimezone(timezone.utc) - a.astimezone(timezone.utc)).total_seconds() / 60


def _minute(t: datetime) -> int:
    return t.hour * 60 + t.minute


def _at_minute(now: datetime, minute_of_day: int, days_ahead: int = 0) -> datetime:
    d = (now + timedelta(days=days_ahead)).date()
    return datetime(d.year, d.month, d.day, minute_of_day // 60, minute_of_day % 60, tzinfo=SYDNEY)


def clock_card(now: datetime, rules: dict = RULES) -> dict:
    """Where now sits against the free window [11:00,14:00) and the credit hours [18:00,20:00), Sydney civil time (DST-safe: wall-clock
    datetimes in Australia/Sydney, differences taken on aware datetimes)."""
    now = now.astimezone(SYDNEY)
    m = _minute(now)
    fs, fe, cs, ce = rules['free_start'], rules['free_end'], rules['credit_start'], rules['credit_end']
    in_free = fs <= m < fe
    next_free = _at_minute(now, fs, 0 if m < fs else 1)
    out = {'now': now, 'in_free': in_free, 'next_free_start': next_free if not in_free else _at_minute(now, fs, 1),
           'minutes_to_free': 0 if in_free else _mins(now, next_free),
           'free_minutes_left': _mins(now, _at_minute(now, fe)) if in_free else 0,
           'credit': 'before' if m < cs else 'during' if m < ce else 'after'}
    out['minutes_to_credit'] = _mins(now, _at_minute(now, cs)) if m < cs else None
    out['credit_minutes_left'] = _mins(now, _at_minute(now, ce)) if cs <= m < ce else None
    return out


def battery_card(soc: Value, soc_earlier: Value | None = None, rules: dict = RULES) -> dict:
    """Nominal budget from the recorded capacity: stored, above the 20% reserve, above the 35% export floor; trend in percentage points per
    hour from an earlier valid sample (at least 20 minutes back, at most 3 hours). Nominal is not calibrated delivered energy."""
    if not soc:
        return {'soc': None, 'reason': soc.reason}
    c, s = rules['capacity_kwh'], soc.value
    out = {'soc': s, 'stored_kwh': c * s / 100, 'above_reserve_kwh': c * max(0.0, s - rules['reserve_pct']) / 100,
           'above_floor_kwh': c * max(0.0, s - rules['export_floor_pct']) / 100, 'below_reserve': s < rules['reserve_pct'],
           'trend_pp_per_h': None, 'trend_reason': 'no earlier reading'}
    if soc_earlier is not None and soc_earlier and soc.at and soc_earlier.at:
        hours = _mins(soc_earlier.at, soc.at) / 60
        if 1 / 3 <= hours <= 3:
            out['trend_pp_per_h'], out['trend_reason'] = (s - soc_earlier.value) / hours, None
        else:
            out['trend_reason'] = 'earlier reading too close or too old for a trend'
    return out


def _nearest_rank(sorted_vals: list[float], p: float) -> float:
    return sorted_vals[max(0, math.ceil(p / 100 * len(sorted_vals)) - 1)]


def _span(day: dict, nxt: dict | None, start_h: float, end_h: float) -> float | None:
    """House kWh on a history day from fractional hour start_h to end_h (end_h > 24 runs into the next day). Any missing hour -> None."""
    total, h = 0.0, start_h
    while h < end_h - 1e-9:
        src, idx = (day, int(h)) if h < 24 else (nxt, int(h) - 24)
        if src is None:
            return None
        hours = src.get('hours') or []
        v = number(hours[idx]) if idx < len(hours) else None
        if v is None:
            return None
        step = min(math.floor(h) + 1, end_h) - h
        total += v * step
        h += step
    return total


def demand_card(now: datetime, history: list[dict] | None, forecast_high: float | None = None, rules: dict = RULES) -> dict:
    """Expected house use from history of complete same-regime days: now -> next 11:00 (when grid power is free again), now -> 18:00 and the
    credit hours 18-20 (only while still ahead). history: [{'date': 'YYYY-MM-DD', 'hours': [24 kWh], 'high': °C or None}], hourly house energy
    from HA's recorder statistics. A hot forecast matches hot days when at least MIN_MATCHED_DAYS exist. Fewer than MIN_MATCHED_DAYS: a rough
    min-max with the count, never percentiles."""
    now = now.astimezone(SYDNEY)
    days = {}
    for d in history or []:
        try:
            date = datetime.fromisoformat(d['date']).date()
        except (KeyError, TypeError, ValueError):
            continue
        if date < now.date() and date not in days:
            days[date] = d
    if not days:
        return {'n': 0, 'reason': 'no hourly house history'}
    chosen, basis = sorted(days), 'recent days'
    if forecast_high is not None and forecast_high >= HOT_DAY_C:
        hot = [k for k in chosen if number(days[k].get('high'), lo=None) is not None and abs(days[k]['high'] - forecast_high) <= HOT_BAND_C]
        if len(hot) >= MIN_MATCHED_DAYS:
            chosen, basis = hot, f'similar hot days (highs within {HOT_BAND_C}°C of tomorrow\'s {forecast_high:g}°C)'
        else:
            basis = f'recent days (only {len(hot)} similar hot days recorded, so this may be low for a hot night)'
    chosen = chosen[-14:]
    m = now.hour + now.minute / 60
    hfree = rules['free_start'] / 60 + (24 if m >= rules['free_start'] / 60 else 0)
    spans = {'to_free': (m, hfree)}
    if m < rules['credit_start'] / 60:
        spans['to_credit'] = (m, rules['credit_start'] / 60)
    if m < rules['credit_end'] / 60:
        spans['credit_hours'] = (max(m, rules['credit_start'] / 60), rules['credit_end'] / 60)
    out = {'basis': basis, 'reason': None}
    for name, (a, b) in spans.items():
        vals = []
        for k in chosen:
            v = _span(days[k], days.get(k + timedelta(days=1)), a, b)
            if v is not None:
                vals.append(v)
        vals.sort()
        if not vals:
            out[name] = None
            continue
        e = {'n': len(vals), 'median': _nearest_rank(vals, 50) if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2,
             'low': vals[0], 'high': vals[-1], 'rough': len(vals) < MIN_MATCHED_DAYS}
        if not e['rough']:
            e['low'], e['high'] = _nearest_rank(vals, 10), _nearest_rank(vals, 90)
        out[name] = e
    out['n'] = max((out[k]['n'] for k in spans if out.get(k)), default=0)
    if not out['n']:
        out['reason'] = 'history days incomplete for this part of the day'
    return out


def credit_card(now: datetime, hour1: Value, hour2: Value, rules: dict = RULES) -> dict:
    """Tonight's credit from gross grid import per hour. A valid hour at or above the limit is conclusive (missed); both complete and below:
    met; otherwise pending (hours still to run) or NO DATA. Headroom only within an hour, never carried across hours."""
    lim, m = rules['credit_limit_kwh'], _minute(now.astimezone(SYDNEY))
    done1, done2 = m >= rules['credit_start'] + 60, m >= rules['credit_end']
    started1, started2 = m >= rules['credit_start'], m >= rules['credit_start'] + 60
    out = {'limit': lim, 'hour1': hour1.value, 'hour2': hour2.value}
    if (hour1 and hour1.value >= lim) or (hour2 and hour2.value >= lim):
        out['status'] = 'missed'
    elif done2 and hour1 and hour2:
        out['status'] = 'met'
    elif not started1:
        out['status'] = 'ahead'
    elif (started1 and not hour1) or (started2 and not hour2):
        out['status'] = 'no data'
    else:
        out['status'] = 'pending'
    if out['status'] == 'pending':
        cur = hour2 if started2 else hour1
        out['current_hour'] = 2 if started2 else 1
        out['headroom'] = lim - cur.value
        out['first_hour_done'] = done1
    return out


def loads_in(question: str) -> list[str]:
    q = (question or '').lower()
    return [name for name, pat in _LOAD_WORDS if re.search(pat, q)]


def load_from_question(question: str) -> str | None:
    n = loads_in(question)
    return n[0] if n else None


def _typical_use(history, a: datetime, b: datetime) -> float | None:
    """Median house kWh between two times on the same evening (a < b, within 24 h), from the history days; None if no usable days."""
    ha = a.hour + a.minute / 60
    hb = ha + _mins(a, b) / 60
    days = sorted((datetime.fromisoformat(d['date']).date(), d) for d in history or [] if d.get('date'))
    idx = {k: d for k, d in days}
    vals = sorted(v for k, d in days if (v := _span(d, idx.get(k + timedelta(days=1)), ha, hb)) is not None)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def load_profile(name: str, measured: dict | None = None) -> dict | None:
    """measured: {'kwh': x or [lo, hi], 'minutes': m} from HA's measured history or the person's own words; else the typical figure."""
    if measured and measured.get('kwh') is not None:
        k = measured['kwh']
        lo, hi = (k, k) if not isinstance(k, (list, tuple)) else (k[0], k[1])
        lo, hi = number(lo), number(hi)
        if lo is not None and hi is not None and lo <= hi:
            mins = number(measured.get('minutes')) or (PROFILES.get(name, (0, 0, None))[2])
            return {'name': name, 'low': lo, 'high': hi, 'minutes': mins, 'source': measured.get('source', 'measured')}
    if name in PROFILES:
        lo, hi, mins = PROFILES[name]
        return {'name': name, 'low': lo, 'high': hi, 'minutes': mins, 'source': 'typical'}
    return None


def _overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    return max(0.0, _mins(max(a0, b0), min(a1, b1)))


def load_card(now: datetime, load: dict, batt: dict, demand: dict, clk: dict, credit: dict | None, solar_rest_kwh: tuple | None,
              rules: dict = RULES) -> dict:
    """Compare running the load now (or tonight) with the next free window. Energy: battery above reserve + the low solar estimate for the
    rest of today (never tomorrow's) - the expected use until the next 11:00 - the load, on a heavy night (P90 / max) and a typical one.
    Any shortfall below the reserve is grid import at the paid rate. Power: a cycle overlapping 18-20 risks a short grid draw even when the
    energy is there. Returns the figures and a code-chosen lean with its reason; the lean is an estimate, never a promise."""
    now = now.astimezone(SYDNEY)
    rate = rules['paid_rate']
    out = {'load': load, 'paid_cost_low': load['low'] * rate, 'paid_cost_high': load['high'] * rate}
    end = now + timedelta(minutes=load['minutes'] or 0)
    cs, ce = _at_minute(now, rules['credit_start']), _at_minute(now, rules['credit_end'])
    out['credit_overlap_now'] = _overlap(now, end, cs, ce) if load['minutes'] else None
    if clk['credit'] == 'before' and load['minutes'] and _minute(now) >= rules['free_end']:
        latest = cs - timedelta(minutes=load['minutes'])
        out['latest_start_before_credit'] = latest if latest > now else None
    fs, fe = _at_minute(now, rules['free_start']), _at_minute(now, rules['free_end'])
    if clk['in_free'] and load['minutes']:
        out['free_part_now'] = _overlap(now, end, fs, fe)
    out['next_free'] = clk['next_free_start']
    out['minutes_to_free'] = clk['minutes_to_free']
    need = demand.get('to_free') if demand else None
    if batt.get('soc') is None:
        out['lean'], out['why'] = 'unknown', f"battery charge {batt.get('reason', 'not available')}"
        return out
    avail = batt['above_reserve_kwh']
    sol_lo = sol_mid = 0.0
    if solar_rest_kwh and rules['free_end'] <= _minute(now) < 19 * 60:
        # the morning's solar mostly comes after 11 am, so it isn't counted before then; after 7 pm there is none to count (and a forecast
        # handed over then could only be tomorrow's, which never counts tonight)
        sol_lo, sol_mid = solar_rest_kwh[0], (solar_rest_kwh[0] + solar_rest_kwh[1]) / 2
    out['available_kwh'] = avail
    out['after_load_now'] = (avail - load['high'], avail - load['low'])      # "how much is left after X", before any other use
    out['solar_rest_low'] = sol_lo if solar_rest_kwh else None
    if clk['in_free']:
        out['lean'] = 'now'
        out['why'] = 'grid power is free now' + ('' if (out.get('free_part_now') or 0) >= load['minutes'] else
                                                  f", though the cycle runs {hm(load['minutes'] - out['free_part_now'])} past 2 pm")
        return out
    if need is None:
        share = load['high'] / avail if avail > 0 else None
        out['share_of_available'] = share
        out['lean'] = 'unknown_need'
        out['why'] = 'no usable history of night-time use'
        return out
    out['need_typical'], out['need_heavy'], out['need_low'] = need['median'], need['high'], need['low']
    out['need_n'], out['need_rough'] = need['n'], need['rough']
    out['margin_typical'] = avail + sol_mid - need['median'] - (load['low'] + load['high']) / 2
    out['margin_heavy'] = avail + sol_lo - need['high'] - load['high']
    out['margin_before_load_typical'] = avail + sol_mid - need['median']
    # paid grid caused by the load itself (the part of it the battery can't cover above the reserve), typical and heavy night
    def caused(margin_before, load_kwh):
        return min(load_kwh, max(0.0, load_kwh - max(0.0, margin_before)))
    out['paid_kwh_typical'] = caused(avail + sol_mid - need['median'], (load['low'] + load['high']) / 2)
    out['paid_kwh_heavy'] = caused(avail + sol_lo - need['high'], load['high'])
    if out['margin_heavy'] >= COMFORT_BUFFER_KWH:
        lean, why = 'tonight_fine', 'the battery covers the load and the heavy end of use until 11 am with room to spare'
    elif out['margin_typical'] >= 0:
        lean, why = 'either_tight', 'it fits with typical use, but the heavy end could dip into paid grid before 11 am'
    else:
        lean, why = 'free_window', 'even typical use would run the battery down to the reserve before 11 am and need paid grid'
    overlap = out.get('credit_overlap_now') or 0
    out['minutes_to_credit_end'] = _mins(now, ce) if now < ce else None
    if lean != 'free_window' and overlap and credit and credit.get('status') in ('pending', 'ahead'):
        if clk['credit'] == 'during':
            lean, why = 'after_credit', 'the cycle would run in the credit hours, when a load spike can pull from the grid; after 8 pm the energy is fine'
        elif out.get('latest_start_before_credit'):
            lean, why = 'before_credit', 'the energy is fine, and finishing before 6 pm keeps it clear of the credit hours'
        else:
            lean, why = 'after_credit', 'started now it would run into the credit hours; after 8 pm the energy is fine'
    out['lean'], out['why'] = lean, why
    return out


# ---- the prompt text ----

def _range(a: float, b: float) -> str:
    return kwh(a) if kwh(a) == kwh(b) else f'{kwh(a)} to {kwh(b)}'


def _need_text(e: dict, what: str) -> str:
    if e['rough']:
        return f"{what}: {kwh(e['median'])} typical, {_range(e['low'], e['high'])} across only {e['n']} recorded days (rough)"
    return f"{what}: {kwh(e['median'])} typical, {_range(e['low'], e['high'])} on most days ({e['n']} days)"


def render(c: dict) -> str:
    """The cards as prompt lines (figures already rounded for speech; the model uses them as given)."""
    L = ['Energy cards (worked out by Home Assistant from the readings; use these figures as given and never work out new ones):']
    k, b, d, cr = c['clock'], c['battery'], c['demand'], c['credit']
    if k['in_free']:
        L.append(f"- Free grid power: on now, for another {hm(k['free_minutes_left'])} (until 2 pm).")
    else:
        L.append(f"- Free grid power: next from 11 am {'today' if k['next_free_start'].date() == k['now'].date() else 'tomorrow'}, in {hm(k['minutes_to_free'])}.")
    if k['credit'] == 'before':
        L.append(f"- Evening credit hours (6-8 pm): start in {hm(k['minutes_to_credit'])}.")
    elif k['credit'] == 'during':
        L.append(f"- Evening credit hours (6-8 pm): on now, {hm(k['credit_minutes_left'])} to go.")
    else:
        L.append('- Evening credit hours (6-8 pm): over for today.')
    st = cr['status']
    if st == 'missed':
        L.append("- Tonight's credit: missed on Home Assistant's meter (an hour reached 0.03 kWh of grid import; that can't be undone). The bill decides.")
    elif st == 'met':
        L.append(f"- Tonight's credit: met on Home Assistant's meter (both hours under 0.03 kWh: {cr['hour1']:.3f} and {cr['hour2']:.3f}). The bill decides.")
    elif st == 'pending':
        hrs = f"first hour {cr['hour1']:.3f} kWh" + (f", second hour {cr['hour2']:.3f} kWh so far" if cr['current_hour'] == 2 else ' so far')
        L.append(f"- Tonight's credit: on track so far ({hrs}; each hour must stay under 0.03 kWh). Not settled until 8 pm.")
    elif st == 'no data':
        L.append("- Tonight's credit: no meter reading for the credit hours, so it can't be told.")
    if b.get('estimated_from'):
        last, at, used = b['estimated_from']
        L.append(f"- Battery: no current reading (the last was {last:.0f}% at {clock(at)}). Estimate from typical use since then: about {b['soc']:.0f}% now,"
                 f" about {kwh(b['above_reserve_kwh'])} above the 20% reserve (estimate; a fresh battery reading would firm it up).")
    elif b['soc'] is None:
        L.append(f"- Battery: charge {b['reason']}, so no battery figures.")
    else:
        t = b['trend_pp_per_h']
        trend = '' if t is None else (' and steady' if abs(t) < 1 else f", {'up' if t > 0 else 'down'} {abs(t):.0f} points in the last hour")
        L.append(f"- Battery: {b['soc']:.0f}%{trend}; that's about {kwh(b['stored_kwh'])} stored, {kwh(b['above_reserve_kwh'])} above the 20% reserve"
                 f" (nominal, from the 25.6 kWh capacity).")
    if c.get('solar_rest'):
        lo, hi = c['solar_rest']
        L.append(f"- Solar still to come today (forecast): {kwh(lo)} to {kwh(hi)}.")
    if c.get('solar_tomorrow'):
        L.append(f"- Tomorrow: {c['solar_tomorrow']}. Tomorrow's solar doesn't help tonight; the battery's normal top-up is in the free window.")
    if d.get('n'):
        if d.get('to_free') and not k['in_free']:
            L.append('- ' + _need_text(d['to_free'], f"Expected house use from now until 11 am ({d['basis']})"))
        if d.get('credit_hours') and k['credit'] != 'after':
            e = d['credit_hours']
            L.append(f"- Expected house use in the credit hours: {kwh(e['median'])} typical ({_range(e['low'], e['high'])}).")
    else:
        L.append(f"- Expected house use tonight: no estimate ({d.get('reason', 'no history')}).")
    ld = c.get('load_card')
    if ld:
        p = ld['load']
        src = ('typical for a ' + p['name'] + ', not measured here') if p['source'] == 'typical' else p['source']
        rng = kwh(p['low']) if p['low'] == p['high'] else f"{p['low']:.1f} to {kwh(p['high'])}"
        L.append(f"- {p['name'].capitalize()}: {rng} a cycle, about {hm(p['minutes'])} ({src}). From paid grid it would cost "
                 + (f"{money(ld['paid_cost_low'])}" if p['low'] == p['high'] else f"{money(ld['paid_cost_low'])} to {money(ld['paid_cost_high'])}")
                 + '; in the free window, nothing.')
        if ld.get('latest_start_before_credit'):
            L.append(f"- To finish before 6 pm it needs to start by {clock(ld['latest_start_before_credit'])}.")
        elif ld.get('credit_overlap_now'):
            L.append(f"- Started now it would run {hm(ld['credit_overlap_now'])} in the credit hours; started after 8 pm (in "
                     f"{hm(ld['minutes_to_credit_end'])}) it wouldn't.")
        when = 'tonight' if k['now'].hour >= 17 or k['now'].hour < 4 else 'now'
        if ld.get('after_load_now') and ld['after_load_now'][0] >= 0:
            a0, a1 = ld['after_load_now']
            L.append(f"- Above the reserve after the {p['name']} alone (before any other use): about {_range(a0, a1)}.")
        if 'margin_heavy' in ld:
            def left(x):
                return f"about {kwh(x)} left above the reserve" if x >= 0 else f"about {kwh(-x)} short (paid grid)"
            L.append(f"- If it runs {when}: {left(ld['margin_typical'])} by 11 am typically, {left(ld['margin_heavy'])} at the heavy end (estimate).")
            pt, ph = ld['paid_kwh_typical'], ld['paid_kwh_heavy']
            r = RULES['paid_rate']
            if ph > 0 and pt > 0:
                L.append(f"- Paid grid the {p['name']} itself would cause {when}: {kwh(pt)} to {kwh(ph)}, about {money(pt * r)} to {money(ph * r)} (estimate).")
            elif ph > 0:
                L.append(f"- Paid grid the {p['name']} itself would cause {when}: none typically, up to {kwh(ph)} (about {money(ph * r)}) at the heavy end (estimate).")
            else:
                L.append(f"- Paid grid the {p['name']} itself would cause {when}: none expected; what it takes from the battery is normally topped up in the free window (estimate).")
        elif ld.get('share_of_available') is not None:
            L.append(f"- The {p['name']} is about {ld['share_of_available'] * 100:.0f}% of the {kwh(ld['available_kwh'])} above the reserve (no night-use history to compare).")
        lean = {'tonight_fine': f'{when} is fine', 'either_tight': 'either works; the free window is the safer bet',
                'free_window': "the next free window", 'after_credit': 'start it after 8 pm',
                'before_credit': 'start it now, so it finishes before 6 pm', 'now': 'run it now',
                'unknown_need': 'probably fine tonight, but not firm', 'unknown': 'no firm lean'}[ld['lean']]
        L.append(f"- Lean (estimate{', on the estimated charge' if b.get('estimated_from') else ''}): {lean}, because {ld['why']}.")
    for g in c.get('gaps', []):
        L.append(f'- Not known: {g}.')
    return '\n'.join(L)


def build(now: datetime, inp: dict, question: str = '', rules: dict = RULES) -> dict:
    """All cards for one turn. inp keys (each optional): soc, soc_earlier ({'value','at'}), history (demand_card), forecast_high (tomorrow, °C),
    solar_rest_kwh ([lo, hi] forecast for the rest of today), solar_tomorrow (text, e.g. 'sunny, 18 to 24 kWh forecast'), credit_hour1/2
    ({'value','at'} gross import kWh), load ({'name', 'kwh', 'minutes', 'source'} measured or said by the person)."""
    now = now.astimezone(SYDNEY)
    gaps = []
    soc = reading(inp.get('soc'), now, 'soc', hi=100)
    earlier = reading(inp.get('soc_earlier'), now, None, hi=100) if inp.get('soc_earlier') else None
    clk = clock_card(now, rules)
    batt = battery_card(soc, earlier, rules)
    fh = number(inp.get('forecast_high'), lo=None)
    dem = demand_card(now, inp.get('history'), fh, rules)
    if not soc and soc.last is not None and soc.at is not None and (now - soc.at) <= timedelta(hours=12):
        # stale: an ESTIMATE from typical use since the last reading (no solar counted, so on the low side), labelled as such
        a = soc.at.astimezone(SYDNEY)
        used = _typical_use(inp.get('history'), a, now)
        if used is not None:
            est = max(0.0, soc.last - used / rules['capacity_kwh'] * 100)
            batt = battery_card(Value(est, None, now), None, rules)
            batt['estimated_from'] = (soc.last, a, used)
    h1 = reading(inp.get('credit_hour1'), now, None)
    h2 = reading(inp.get('credit_hour2'), now, None)
    cr = credit_card(now, h1, h2, rules)
    sr = inp.get('solar_rest_kwh')
    solar_rest = None
    if sr is not None:
        lo, hi = (number(sr[0]), number(sr[1])) if isinstance(sr, (list, tuple)) and len(sr) == 2 else (None, None)
        if lo is not None and hi is not None and lo <= hi:
            solar_rest = (lo, hi)
        else:
            gaps.append('solar forecast for the rest of today (invalid)')
    elif _minute(now) < 17 * 60 and not clk['in_free']:
        gaps.append('solar forecast for the rest of today')
    cards = {'clock': clk, 'battery': batt, 'demand': dem, 'credit': cr, 'solar_rest': solar_rest,
             'solar_tomorrow': inp.get('solar_tomorrow'), 'gaps': gaps}
    named = loads_in(question)
    name = (inp.get('load') or {}).get('name') or (named[0] if len(named) == 1 else None)
    measured = inp.get('load')
    figs = re.findall(r'(\d+(?:\.\d+)?)\s*kwh', (question or '').lower())
    if name and not measured and len(figs) == 1:
        measured = {'name': name, 'kwh': float(figs[0]), 'source': 'your figure'}
    if len(named) > 1 and not inp.get('load'):
        gaps.append(f"a combined figure for {' and '.join(named)} (use atlas_calc with the figures above)")
    if name:
        prof = load_profile(name, measured)
        if prof:
            cards['load_card'] = load_card(now, prof, batt, dem, clk, cr, solar_rest, rules)
    cards['text'] = render(cards)
    return cards
