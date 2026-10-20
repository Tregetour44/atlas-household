"""Build cases/all.json: Codex 49's 40 scenarios, the owner's three 20 Oct turns, the dishwasher-tonight case in 14 states, and 20 arithmetic
cases. Every reading is SYNTHETIC (made up for tests); hourly history is generated deterministically from a typical profile.
Expected figures for the arithmetic cases are written out by hand here (independent of calc.py and energy_cards.py) and checked in tests.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEX = HERE.parent / 'codex49'

# typical hourly house kWh (a synthetic Sydney house with a 25.6 kWh battery): quiet night, morning bump, evening peak
BASE = [0.35] * 7 + [0.6, 0.55, 0.45, 0.45] + [0.5] * 6 + [0.8, 1.0, 1.0, 0.85, 0.7, 0.5, 0.4]
HOT_EXTRA = [0.25] * 7 + [0.0] * 6 + [0.2, 0.3, 0.5, 0.6, 0.7, 0.7, 0.7, 0.7, 0.6, 0.5, 0.4]  # aircon on hot evenings and nights


def _jitter(key: str) -> float:
    return 0.85 + (int(hashlib.sha256(key.encode()).hexdigest()[:6], 16) % 400) / 1000      # 0.85-1.25, deterministic


def history(end: date, n: int = 14, scale: float = 1.0, hot: set[int] | None = None, highs: dict | None = None, missing_hours=()):
    """n complete days before `end`. hot: indexes of days (0 = oldest) with aircon use. highs: index -> forecast-matching high °C."""
    out = []
    for i in range(n):
        d = end - timedelta(days=n - i)
        f = _jitter(d.isoformat() + str(scale)) * scale
        hrs = [round(v * f + (HOT_EXTRA[h] if hot and i in hot else 0), 3) for h, v in enumerate(BASE)]
        for (di, hh) in missing_hours:
            if di == i:
                hrs[hh] = None
        out.append({'date': d.isoformat(), 'hours': hrs, 'high': (highs or {}).get(i, 24)})
    return out


def iso(d: str, hm: str) -> str:
    return f'{d}T{hm}:00+11:00'


def days_ledger(today: date, rows):
    return [{'date': (today - timedelta(days=k)).isoformat(), 'house': h, 'solar': s, 'export': e, 'paid': p, 'free': f} for k, h, s, e, p, f in rows]


FC_SUNNY = 'Wed 21 Oct: sunny, 27 / 15 °C, 0 mm; Thu 22 Oct: partly cloudy, 25 / 16 °C, 0 mm; Fri 23 Oct: showers, 21 / 15 °C, 6 mm'
FC_CLOUDY = 'Wed 21 Oct: cloudy, 19 / 14 °C, 4 mm; Thu 22 Oct: rain, 18 / 13 °C, 12 mm; Fri 23 Oct: partly cloudy, 22 / 14 °C, 1 mm'
FC_HOT = 'Wed 21 Oct: sunny, 36 / 24 °C, 0 mm; Thu 22 Oct: hot, 34 / 23 °C, 0 mm; Fri 23 Oct: storms, 27 / 19 °C, 8 mm'
FC24_NIGHT = '21:00 clear 19 °C; 00:00 clear 17 °C; 03:00 clear 16 °C; 06:00 sunny 16 °C; 09:00 sunny 21 °C; 12:00 sunny 25 °C; 15:00 sunny 26 °C; 18:00 sunny 23 °C'
FC24_HOT = '21:00 clear 29 °C; 00:00 clear 27 °C; 03:00 clear 25 °C; 06:00 sunny 25 °C; 09:00 sunny 30 °C; 12:00 sunny 34 °C; 15:00 sunny 36 °C; 18:00 sunny 33 °C'


def dishwasher_cases():
    D = '2026-10-20'
    today = date(2026, 10, 20)
    ledger = days_ledger(today, [(1, 18.6, 12.4, 2.0, 0.35, 4.4), (2, 17.9, 13.1, 2.6, 0.2, 4.1), (3, 19.4, 11.0, 1.5, 0.6, 4.8)])
    H = history(today)

    def case(cid, hm, q, soc, *, fc=FC_SUNNY, fc24=FC24_NIGHT, solar_w=0, house_w=650, solar_today=10.2, energy=None, house=None, state='',
             expect=''):
        e = {'soc': {'value': soc, 'at': iso(D, hm)}, 'history': H, 'solar_tomorrow': 'sunny' if fc == FC_SUNNY else 'cloudy' if fc == FC_CLOUDY else 'hot and sunny'}
        if int(hm[:2]) >= 20:
            e.update(credit_hour1={'value': 0.004, 'at': iso(D, '19:00')}, credit_hour2={'value': 0.007, 'at': iso(D, '20:00')})
        e.update(energy or {})
        h = {'soc': soc, 'solar_w': solar_w, 'house_w': house_w, 'import_w': 0, 'export_w': 0, 'solar_today': solar_today, 'house_today': 13.1,
             'paid_today': 0.3, 'free_today': 3.4, 'export_today': 1.4, 'forecast_days': fc, 'forecast_24h': fc24, 'weather': 'clear-night' if int(hm[:2]) >= 19 else 'sunny',
             'outside_c': 19, 'loft': 23.5, 'bedroom': 22.0, 'days': ledger, 'nights': [{'date': '2026-10-19', 'result': 'met'}, {'date': '2026-10-18', 'result': 'met'}]}
        h.update(house or {})
        return {'id': cid, 'group': 'dishwasher', 'state': state, 'now': iso(D, hm), 'question': q, 'house': h, 'energy': e, 'expect': expect}

    hot_hist = history(today, hot=set(range(6, 14)), highs={i: 34 + (i % 3) for i in range(6, 14)})
    return [
        case('DW-01', '21:30', 'Should I run the dishwasher tonight or wait till tomorrow?', 85, state='battery high, night, sunny tomorrow',
             expect='tonight is fine: large margin above reserve after the night and the load; little cost difference'),
        case('DW-02', '21:00', 'Can I put the dishwasher on tonight?', 31, fc=FC_CLOUDY, solar_today=4.1, state='battery low, night, cloudy tomorrow',
             expect="tomorrow's free window: tonight would run to the reserve and need paid grid (estimate, cents not dollars); cloudy tomorrow doesn't change the free grid"),
        case('DW-03', '22:15', 'Dishwasher tonight, or leave it for the morning?', 46, state='battery mid, late night, sunny tomorrow',
             expect='either; tight on a heavy night, free window the safer bet, small cost either way'),
        case('DW-04', '20:30', "Is it worth running the dishwasher tonight, or is tomorrow better?", 52, fc=FC_CLOUDY, solar_today=5.2,
             state='battery mid, evening, cloudy tomorrow', expect='either/tight; free window recharges whatever the weather; no credit risk now'),
        case('DW-05', '15:40', 'Should I run the dishwasher now or tonight?', 88, solar_w=2600, house_w=900, solar_today=14.8,
             energy={'solar_rest_kwh': [1.5, 2.5]}, house={'weather': 'sunny', 'outside_c': 24}, state='battery high, afternoon before the credit hours',
             expect='now, so it finishes before 6 pm (start by 4 pm)'),
        case('DW-06', '16:45', 'Dishwasher now, or later tonight?', 80, solar_w=900, house_w=800, solar_today=14.1, energy={'solar_rest_kwh': [0.3, 0.8]},
             house={'weather': 'partlycloudy', 'outside_c': 22}, state='battery high, too late to finish before 6 pm',
             expect='start after 8 pm (energy fine; the cycle would run into the credit hours)'),
        case('DW-07', '18:40', 'Can I run the dishwasher now?', 76, house_w=700, energy={'credit_hour1': {'value': 0.004, 'at': iso(D, '18:40')}},
             state='battery mid-high, during the credit hours', expect='wait until after 8 pm (in 1 h 20 min); then tonight is fine'),
        case('DW-08', '19:20', 'Should I start the dishwasher tonight?', 27, fc=FC_CLOUDY, solar_today=3.8,
             energy={'credit_hour1': {'value': 0.006, 'at': iso(D, '19:00')}, 'credit_hour2': {'value': 0.002, 'at': iso(D, '19:20')}},
             state='battery low, during the credit hours, cloudy tomorrow', expect="tomorrow's free window: low battery; not during the credit hours"),
        case('DW-09', '08:30', 'Dishwasher now or wait for the free power at 11?', 38, solar_w=1200, house_w=700, solar_today=1.1,
             energy={'solar_rest_kwh': [14.0, 19.0]}, house={'weather': 'sunny', 'outside_c': 18}, state='battery low-mid, morning before the free window, sunny',
             expect='either; now is fine (battery covers it and tops up free from 11) or wait 2.5 h if no hurry'),
        case('DW-10', '21:00', 'Should I run the dishwasher tonight?', 55, fc=FC_HOT, fc24=FC24_HOT,
             energy={'history': hot_hist, 'forecast_high': 36, 'solar_tomorrow': 'hot and sunny'},
             house={'outside_c': 29, 'loft': 28.5, 'bedroom': 27.0, 'ac_mode': 'cool', 'ac_action': 'cooling'}, state='battery mid, hot night with aircon',
             expect='tight on hot nights; tomorrow free window is the safer bet; keep the house cool (comfort pointer)'),
        case('DW-11', '21:00', 'Will the battery cope with the dishwasher tonight?', 64, energy={'history': []}, state='battery mid, no night-use history',
             expect='no dead end: 11.3 kWh above reserve vs a 1-1.5 kWh load (about a tenth); probably fine; night-use history would firm it up'),
        case('DW-12', '21:00', 'Dishwasher tonight?', 70, energy={'soc': {'value': 70, 'at': iso(D, '16:55')}},
             house={'soc': {'value': 70, 'at': iso(D, '16:55')}}, state='battery reading stale (4 h old)',
             expect='says the battery reading is old (70% at 4:55 pm), still gives a labelled lean from history; no firm figures from the stale value'),
        case('DW-13', '12:10', 'Should I run the dishwasher now?', 92, solar_w=4200, house_w=1100, solar_today=9.0, energy={'solar_rest_kwh': [8.0, 11.0]},
             house={'weather': 'sunny', 'outside_c': 25}, state='battery high, inside the free window', expect='now: free grid power until 2 pm; cycle runs 10 min past 2 pm, negligible'),
        case('DW-14', '19:30', 'We already missed the credit tonight, so can I run the dishwasher now?', 70,
             energy={'credit_hour1': {'value': 0.045, 'at': iso(D, '19:00')}, 'credit_hour2': {'value': 0.001, 'at': iso(D, '19:30')}},
             state='battery mid-high, credit already missed', expect='yes: credit already gone on the meter, energy fine; no reason to wait'),
    ]


def owner_cases():
    D = '2026-10-20'
    today = date(2026, 10, 20)
    oc = json.loads((HERE.parent / 'owner-cases.json').read_text())['cases']
    r = oc[0]['readings_made_up']
    H = history(today, scale=0.66)          # typical use for the rest of the night about 4 kWh, as in the owner case's made-up readings
    ledger = days_ledger(today, [(1, 16.2, r['solar_today_kwh'] + 1.3, 1.1, 0.25, 3.9)])
    house = {'soc': r['battery_percent'], 'solar_w': r['solar_now_w'], 'house_w': r['house_power_now_w'], 'import_w': 0, 'export_w': 0,
             'solar_today': r['solar_today_kwh'], 'house_today': 12.6, 'paid_today': 0.2, 'free_today': 3.0, 'export_today': 0.9,
             'forecast_days': FC_SUNNY, 'forecast_24h': FC24_NIGHT, 'weather': 'clear-night', 'outside_c': 18, 'loft': 23.0, 'bedroom': 21.5,
             'days': ledger, 'nights': [{'date': '2026-10-19', 'result': 'met'}]}
    energy = {'soc': {'value': r['battery_percent'], 'at': iso(D, '20:47')}, 'history': H, 'solar_tomorrow': 'sunny',
              'load': {'name': 'dishwasher', 'kwh': r['small_dishwasher_load_kwh'], 'minutes': 90, 'source': 'a small load: your estimate'},
              'credit_hour1': {'value': 0.004, 'at': iso(D, '19:00')}, 'credit_hour2': {'value': 0.006, 'at': iso(D, '20:00')}}
    out = [{'id': 'OWN-01', 'group': 'owner', 'now': iso(D, r['time']), 'question': oc[0]['q'], 'house': house, 'energy': energy,
            'expect': oc[0]['good_answer_shape'], 'live_reply': oc[0]['atlas_reply']}]
    for c in oc[1:]:
        out.append({'id': c['id'], 'group': 'owner', 'now': iso(D, '20:50'), 'question': c['q'], 'house': house, 'energy': {**energy, 'load': None},
                    'expect': c['good_answer_shape'], 'live_reply': c['atlas_reply'], 'answers': [[10, 10]] if c['id'] == 'OWN-03' else []})
    return out


def arithmetic_cases():
    D = '2026-10-20'
    today = date(2026, 10, 20)
    ledger = days_ledger(today, [(1, 18.6, 12.4, 2.0, 0.35, 4.4), (2, 17.9, 13.1, 2.6, 0.2, 4.1)])
    house = {'soc': 64, 'solar_w': 0, 'house_w': 640, 'import_w': 0, 'export_w': 0, 'solar_today': 9.6, 'house_today': 14.2, 'paid_today': 0.42,
             'free_today': 3.1, 'export_today': 1.2, 'forecast_days': FC_SUNNY, 'forecast_24h': FC24_NIGHT, 'weather': 'clear-night', 'outside_c': 18,
             'loft': 24.6, 'bedroom': 22.1, 'garage': 20.3, 'days': ledger, 'nights': [{'date': '2026-10-19', 'result': 'met'}]}
    energy = {'soc': {'value': 64, 'at': iso(D, '21:40')}, 'history': history(today), 'solar_tomorrow': 'sunny',
              'credit_hour1': {'value': 0.003, 'at': iso(D, '19:00')}, 'credit_hour2': {'value': 0.008, 'at': iso(D, '20:00')}}
    # (id, question, acceptable answers as [low, high] (any one must appear), kind)
    rows = [
        ('AR-01', "What's 45 minus 17?", [[28, 28]], 'difference'),
        ('AR-02', "What's 7.5 plus 2.25?", [[9.75, 9.75]], 'sum'),
        ('AR-03', "What's 17% of 340?", [[57.8, 57.8]], 'percentage'),
        ('AR-04', 'How much would 3.6 kWh cost at 55 cents a kWh?', [[1.98, 1.98]], 'kWh to cost'),
        ('AR-05', 'If the dishwasher uses 1.2 kWh, how much is left in the battery above the reserve after it?', [[10.0, 10.1]], 'left after X'),
        ('AR-06', 'How much solar did we make today and yesterday together?', [[22.0, 22.0]], 'sum of readings'),
        ('AR-07', 'How much more did the house use yesterday than today so far?', [[4.4, 4.4]], 'difference of readings'),
        ('AR-08', "What's today's solar as a percentage of today's house use?", [[67.6, 67.7], [68, 68]], 'percentage of readings'),
        ('AR-09', 'How long until the free window starts?', [[800, 800]], 'how long until'),
        ('AR-10', 'How many kWh is the battery holding right now?', [[16.4, 16.4]], 'stored energy'),
        ('AR-11', "If we run the dryer at 2.5 kWh and the dishwasher at 1.2 kWh tonight, what's left above the reserve?", [[7.5, 7.6]], 'left after X+Y'),
        ('AR-12', "What's 25.6 times 0.64?", [[16.384, 16.384], [16.38, 16.38]], 'product'),
        ('AR-13', 'How much would 4 kWh of paid grid power cost?', [[2.2, 2.2]], 'kWh to cost'),
        ('AR-14', 'How far is the battery above the 35% export floor, in kWh?', [[7.4, 7.4]], 'difference to a limit'),
        ('AR-15', 'How many hours and minutes from 9:40 pm to 11 am?', [[800, 800]], 'how long between'),
        ('AR-16', "What's 1250 W in kW?", [[1.25, 1.25]], 'unit conversion'),
        ('AR-17', "If we split the cost of today's paid grid import three ways, what's each share?", [[0.08, 0.08], [0.077, 0.077]], 'two-step cost'),
        ('AR-18', 'How much warmer is the loft than the master bedroom right now?', [[2.5, 2.5]], 'difference of readings'),
        ('AR-19', "What's the total grid import today, paid and free together?", [[3.52, 3.52], [3.5, 3.5]], 'sum of readings'),
        ('AR-20', "What's $240 with 15% off?", [[204, 204]], 'percentage off'),
    ]
    return [{'id': i, 'group': 'arithmetic', 'kind': k, 'now': iso(D, '21:40'), 'question': q, 'house': house, 'energy': energy, 'answers': a}
            for i, q, a, k in rows]


def codex_cases():
    sc = json.loads((CODEX / 'scenarios.json').read_text())['cases']
    out = []
    for c in sc:
        house = {}
        m = re.match(r'Battery (\d+)%', c['facts'].get('battery', ''))
        if m and 'last reported' not in c['facts']['battery']:
            house['soc'] = int(m.group(1))
        out.append({'id': c['id'], 'group': 'codex49-' + c['group'], 'split': c['split'], 'now': c['snapshot']['as_of'], 'question': c['question'],
                    'house': house, 'codex_facts': c['facts'], 'expect': c['expected_advice'], 'reasoning': c['reasoning'], 'forbidden': c['forbidden'],
                    'gap': c['gap'], 'input_sha256': c['input_sha256']})
    return out


def main():
    cases = codex_cases() + owner_cases() + dishwasher_cases() + arithmetic_cases()
    (HERE / 'cases').mkdir(exist_ok=True)
    (HERE / 'cases' / 'all.json').write_text(json.dumps({'notice': 'SYNTHETIC readings only; see make_cases.py', 'cases': cases}, indent=1, ensure_ascii=False) + '\n')
    print(len(cases), 'cases')


if __name__ == '__main__':
    main()
