"""Offline tests for the energy cards, the arithmetic pieces and the prompt build. python -B -m unittest test_build (from this folder)."""
import asyncio
import json
import math
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'custom_components'))
import calc as C  # noqa: E402
import energy_cards as E  # noqa: E402

SYD = E.SYDNEY


def at(h, m=0, d=20, mo=10):
    return datetime(2026, mo, d, h, m, tzinfo=SYD)


def flat(kwh_per_hour=0.5, n=10, end=at(0)):
    return [{'date': (end.date() - timedelta(days=n - i)).isoformat(), 'hours': [kwh_per_hour] * 24} for i in range(n)]


class Readings(unittest.TestCase):
    def test_missing_is_none_not_zero(self):
        v = E.reading(None, at(21), 'soc')
        self.assertIsNone(v.value)
        self.assertEqual(v.reason, 'not available')

    def test_true_zero_kept(self):
        self.assertEqual(E.reading({'value': 0, 'at': at(21)}, at(21), 'power').value, 0.0)

    def test_bad_inputs_rejected(self):
        for bad in (True, '61', float('nan'), float('inf'), -1):
            self.assertIsNone(E.reading({'value': bad, 'at': at(21)}, at(21), 'soc', hi=100).value, bad)
        self.assertIsNone(E.reading({'value': 101, 'at': at(21)}, at(21), 'soc', hi=100).value)

    def test_stale_and_future(self):
        v = E.reading({'value': 70, 'at': at(16, 55)}, at(21), 'soc', hi=100)
        self.assertIsNone(v.value)
        self.assertEqual(v.last, 70)
        self.assertIn('stale', v.reason)
        self.assertIn('future', E.reading({'value': 70, 'at': at(21, 30)}, at(21), 'soc').reason)
        self.assertIn('time zone', E.reading({'value': 70, 'at': datetime(2026, 10, 20, 21)}, at(21), 'soc').reason)

    def test_daily_total_never_stale(self):
        self.assertEqual(E.reading({'value': 9.4, 'at': at(6)}, at(21), None).value, 9.4)


class Clock(unittest.TestCase):
    def test_windows_half_open(self):
        self.assertTrue(E.clock_card(at(11))['in_free'])
        self.assertFalse(E.clock_card(at(14))['in_free'])
        self.assertEqual(E.clock_card(at(18))['credit'], 'during')
        self.assertEqual(E.clock_card(at(20))['credit'], 'after')
        self.assertEqual(E.clock_card(at(17, 59))['credit'], 'before')

    def test_minutes_to_free(self):
        self.assertEqual(E.clock_card(at(21, 40))['minutes_to_free'], 800)
        self.assertEqual(E.clock_card(at(8, 30))['minutes_to_free'], 150)
        self.assertEqual(E.clock_card(at(12, 10))['free_minutes_left'], 110)

    def test_dst_night(self):
        # 4 Oct 2026, 2 am -> 3 am in Sydney: 21:00 on 3 Oct to 11:00 on 4 Oct is 13 h, not 14 h
        self.assertEqual(E.clock_card(datetime(2026, 10, 3, 21, 0, tzinfo=SYD))['minutes_to_free'], 13 * 60)


class Battery(unittest.TestCase):
    def test_codex_budget(self):
        b = E.battery_card(E.Value(60.0))
        self.assertAlmostEqual(b['above_reserve_kwh'], 10.24)
        self.assertAlmostEqual(b['above_floor_kwh'], 6.4)

    def test_below_reserve_is_zero_margin_not_empty(self):
        b = E.battery_card(E.Value(15.0))
        self.assertEqual(b['above_reserve_kwh'], 0)
        self.assertTrue(b['below_reserve'])
        self.assertAlmostEqual(b['stored_kwh'], 3.84)

    def test_floor_distinct_from_reserve(self):
        b = E.battery_card(E.Value(34.0))
        self.assertGreater(b['above_reserve_kwh'], 0)
        self.assertEqual(b['above_floor_kwh'], 0)

    def test_trend_points_per_hour(self):
        b = E.battery_card(E.Value(61.0, at=at(21)), E.Value(66.0, at=at(20)))
        self.assertAlmostEqual(b['trend_pp_per_h'], -5.0)
        b = E.battery_card(E.Value(61.0, at=at(21)), E.Value(66.0, at=at(20, 55)))
        self.assertIsNone(b['trend_pp_per_h'])

    def test_missing(self):
        self.assertIsNone(E.battery_card(E.Value(None, 'not available'))['soc'])


class Demand(unittest.TestCase):
    def test_now_to_free_spans_midnight(self):
        d = E.demand_card(at(21), flat(0.5))
        self.assertAlmostEqual(d['to_free']['median'], 14 * 0.5)
        self.assertEqual(d['to_free']['n'], 9)           # the newest day has no next morning yet

    def test_partial_hour(self):
        d = E.demand_card(at(20, 30), flat(1.0))
        self.assertAlmostEqual(d['to_free']['median'], 14.5)

    def test_missing_hour_excludes_day_not_zero(self):
        h = flat(0.5)
        h[3]['hours'][22] = None
        d = E.demand_card(at(21), h)
        self.assertEqual(d['to_free']['n'], 8)
        self.assertAlmostEqual(d['to_free']['median'], 7.0)

    def test_few_days_rough(self):
        d = E.demand_card(at(21), flat(0.5, n=3))
        self.assertTrue(d['to_free']['rough'])

    def test_no_history(self):
        d = E.demand_card(at(21), [])
        self.assertEqual(d['n'], 0)
        self.assertIn('no hourly', d['reason'])

    def test_future_or_today_ignored(self):
        h = flat(0.5) + [{'date': '2026-10-20', 'hours': [9.0] * 24}]
        self.assertAlmostEqual(E.demand_card(at(21), h)['to_free']['median'], 7.0)

    def test_hot_match(self):
        h = flat(0.5, n=14)
        for i in range(7, 14):
            h[i]['hours'] = [1.0] * 24
            h[i]['high'] = 35
        d = E.demand_card(at(21), h, forecast_high=36)
        self.assertIn('hot', d['basis'])
        self.assertAlmostEqual(d['to_free']['median'], 14.0)
        d = E.demand_card(at(21), h[:10], forecast_high=36)     # only 3 hot days: recent days, flagged
        self.assertIn('only 3', d['basis'])

    def test_percentiles_nearest_rank(self):
        h = [{'date': (at(0).date() - timedelta(days=11 - i)).isoformat(), 'hours': [0.1 * (i + 1)] * 24} for i in range(11)]
        e = E.demand_card(at(23), h)['to_free']
        self.assertEqual(e['n'], 10)
        v = sorted(0.1 * (i + 1) + 11 * 0.1 * (i + 2) for i in range(10))     # 23:00 on day i, then 00:00-11:00 on day i+1
        self.assertAlmostEqual(e['low'], v[0])
        self.assertAlmostEqual(e['high'], v[8])


class Credit(unittest.TestCase):
    V = E.Value

    def test_strict(self):
        self.assertEqual(E.credit_card(at(20, 1), self.V(0.030), self.V(0.001))['status'], 'missed')
        self.assertEqual(E.credit_card(at(20, 1), self.V(0.029), self.V(0.029))['status'], 'met')
        self.assertEqual(E.credit_card(at(20, 1), self.V(0.02999), self.V(0.02999))['status'], 'met')

    def test_known_failure_with_missing_hour(self):
        self.assertEqual(E.credit_card(at(20, 1), self.V(None), self.V(0.04))['status'], 'missed')

    def test_missing_is_no_data(self):
        self.assertEqual(E.credit_card(at(20, 1), self.V(None), self.V(0.001))['status'], 'no data')

    def test_pending_headroom_per_hour(self):
        c = E.credit_card(at(18, 40), self.V(0.016), self.V(None))
        self.assertEqual(c['status'], 'pending')
        self.assertAlmostEqual(c['headroom'], 0.014)
        c = E.credit_card(at(19, 15), self.V(0.004), self.V(0.002))
        self.assertEqual((c['current_hour'], round(c['headroom'], 6)), (2, 0.028))

    def test_partial_hour_already_over(self):
        self.assertEqual(E.credit_card(at(18, 30), self.V(0.04), self.V(None))['status'], 'missed')

    def test_ahead(self):
        self.assertEqual(E.credit_card(at(17), self.V(None), self.V(None))['status'], 'ahead')


class CreditStatus(unittest.TestCase):
    V = E.Value

    def st(self, h, m, a=None, b=None, **kw):
        return E.credit_status(at(h, m), self.V(a), self.V(b), **kw)

    def test_exactly_limit_is_missed(self):
        c = self.st(20, 1, 0.030, 0.001)
        self.assertEqual((c['tonight'], c['hours'][0]['status']), ('MISSED', 'MISSED'))

    def test_both_029_met_not_added(self):
        self.assertEqual(self.st(20, 1, 0.029, 0.029)['tonight'], 'MET')

    def test_partial_hour_over_limit_is_final(self):
        c = self.st(18, 40, 0.041, load={'name': 'dishwasher'})
        self.assertEqual(c['tonight'], 'MISSED')
        self.assertIn('already missed', '\n'.join(E.credit_lines(c)))

    def test_missing_hour(self):
        self.assertEqual(self.st(20, 2, None, 0.004)['tonight'], 'NO DATA')
        self.assertEqual(self.st(20, 2, None, 0.040)['tonight'], 'MISSED')
        self.assertEqual(self.st(23, 30)['tonight'], 'NOT SUPPLIED')

    def test_at_risk_and_safe(self):
        c = self.st(19, 5, 0.010, 0.026, load={'name': 'dishwasher'})
        self.assertEqual((c['tonight'], c['current'], round(c['hours'][1]['headroom'], 6), c['hours'][1]['minutes_left']), ('AT RISK', 2, 0.004, 55))
        self.assertIn('after 8 pm (in 55 min)', '\n'.join(E.credit_lines(c)))
        self.assertEqual(self.st(18, 30, 0.016)['tonight'], 'SAFE')        # above the 0.015 engineering target, still under the limit
        self.assertEqual(self.st(18, 20, 0.024)['tonight'], 'AT RISK')

    def test_stale_meter_or_no_protection_is_at_risk(self):
        self.assertEqual(self.st(18, 30, 0.008, meter_age_min=12)['tonight'], 'AT RISK')
        self.assertEqual(self.st(18, 30, 0.008, protection=False)['tonight'], 'AT RISK')

    def test_not_in_window(self):
        c = self.st(17, 0)
        self.assertEqual((c['tonight'], c['minutes_to_window']), ('NOT IN WINDOW', 60))

    def test_load_overlap_and_start_by(self):
        c = self.st(15, 40, load={'name': 'dishwasher', 'minutes': 120})
        self.assertEqual((c['load']['overlap'], c['load']['latest_start']), (0.0, at(16)))
        self.assertIn('starts by 4 pm', '\n'.join(E.credit_lines(c)))
        c = self.st(16, 45, load={'name': 'dishwasher', 'minutes': 120})
        self.assertEqual(c['load']['overlap'], 45)
        self.assertIn('after 8 pm', '\n'.join(E.credit_lines(c)))

    def test_import_from_battery_limit_or_cant_rule_out(self):
        c = self.st(18, 10, 0.006, load={'name': 'dryer', 'peak_kw': 6.0}, house_kw=0.8, battery_limit_kw=5.0)
        self.assertAlmostEqual(c['load']['import_kw'], 1.8)
        c = self.st(18, 10, 0.006, load={'name': 'dryer', 'peak_kw': 6.0})
        self.assertIn("can't be ruled out", '\n'.join(E.credit_lines(c)))

    def test_unknown_run_time_never_shown_as_one(self):
        t = '\n'.join(E.credit_lines(self.st(18, 20, 0.024, load={'name': 'dryer'})))
        self.assertIn("run time isn't known", t)
        self.assertNotIn('would run 1 h 40 min', t)
        self.assertIn('nothing is secured until 8 pm', '\n'.join(E.credit_lines(self.st(18, 40, 0.010))))

    def test_typical_duration_is_labelled(self):
        c = E.build(at(17, 30), {}, 'Dryer tonight?')
        t = '\n'.join(E.credit_lines(c['credit_status']))
        self.assertIn('a typical 2 h cycle, not measured here', t)

    def test_cooling_card(self):
        def cool(h, m, solar, house, q='Aircon now?', fh=36):
            c = E.build(at(h, m), {'solar_w': {'value': solar, 'at': at(h, m)}, 'house_w': {'value': house, 'at': at(h, m)}, 'forecast_high': fh}, q)
            return c['cooling'], c['text']
        self.assertEqual(cool(15, 0, 4300, 1100)[0]['now'], 'solar')
        self.assertEqual(cool(12, 0, 300, 900)[0]['now'], 'free')
        self.assertEqual(cool(18, 30, 0, 900)[0]['now'], 'credit')
        self.assertEqual(cool(10, 15, 600, 800)[0]['now'], 'before_free')
        self.assertEqual(cool(16, 0, 600, 800)[0]['now'], 'battery_day')
        self.assertEqual(cool(21, 0, 0, 900)[0]['now'], 'night')
        self.assertIsNone(cool(15, 0, 4300, 1100, q='Dishwasher now?', fh=24)[0])
        t = cool(15, 0, 4300, 1100)[1]
        self.assertIn("Opening up the house isn't an option here", t)
        self.assertNotRegex(t.lower(), r'open (the |a )?(windows?|doors?)')

    def test_credit_advice_defers_to_energy_lean(self):
        t = '\n'.join(E.credit_lines(self.st(19, 20, 0.006, 0.002, load={'name': 'dishwasher', 'minutes': 120}), 'free_window'))
        self.assertIn('not before 8 pm', t)
        self.assertIn('next free window', t)

    def test_comfort_not_deferred(self):
        t = '\n'.join(E.credit_lines(self.st(19, 10, 0.005, 0.003, load={'name': 'aircon (cooling)'})))
        self.assertIn('comfort comes first', t)
        self.assertNotIn('start it after 8 pm', t)

    def test_export_noted_never_offsets(self):
        t = '\n'.join(E.credit_lines(self.st(19, 15, 0.035, export_kwh=0.8)))
        self.assertIn('never cancels', t)


class Load(unittest.TestCase):
    def cards(self, now, soc, q='Should I run the dishwasher tonight?', **kw):
        inp = {'soc': {'value': soc, 'at': now}, 'history': flat(0.45, n=14)}
        inp.update(kw)
        return E.build(now, inp, q)

    def test_high_battery_tonight_fine(self):
        c = self.cards(at(21, 30), 85)
        ld = c['load_card']
        self.assertEqual(ld['lean'], 'tonight_fine')
        self.assertAlmostEqual(ld['margin_heavy'], 25.6 * 0.65 - 13.5 * 0.45 - 1.5)
        self.assertEqual(ld['paid_kwh_heavy'], 0)

    def test_low_battery_free_window_and_cost(self):
        ld = self.cards(at(21), 30)['load_card']
        self.assertEqual(ld['lean'], 'free_window')
        self.assertAlmostEqual(ld['paid_kwh_typical'], 1.25)          # the whole load is paid grid when the battery is already short
        self.assertAlmostEqual(ld['paid_cost_high'], 1.5 * 0.55)

    def test_partial_shortfall_counts_only_the_load_part(self):
        # 25.6 * 0.3 = 7.68 above reserve; 14 h * 0.5 = 7.0 typical night; load 1.25 typical -> 0.68 covered, 0.57 paid
        ld = self.cards(at(21), 50, history=flat(0.5, n=14))['load_card']
        self.assertAlmostEqual(ld['paid_kwh_typical'], 1.25 - (25.6 * 0.30 - 7.0))

    def test_tomorrow_solar_not_counted_tonight(self):
        a = self.cards(at(21), 40)['load_card']
        b = self.cards(at(21), 40, solar_tomorrow='sunny', solar_rest_kwh=[5, 8])['load_card']     # a misfiled forecast at night
        self.assertEqual(a['margin_typical'], b['margin_typical'])

    def test_morning_solar_not_counted_before_11(self):
        a = self.cards(at(8, 30), 38, q='dishwasher now?')['load_card']
        b = self.cards(at(8, 30), 38, q='dishwasher now?', solar_rest_kwh=[14, 19])['load_card']
        self.assertEqual(a['margin_typical'], b['margin_typical'])

    def test_afternoon_solar_low_estimate_counts(self):
        a = self.cards(at(15, 40), 60, q='dishwasher now?')['load_card']
        b = self.cards(at(15, 40), 60, q='dishwasher now?', solar_rest_kwh=[1.5, 2.5])['load_card']
        self.assertAlmostEqual(b['margin_heavy'] - a['margin_heavy'], 1.5)

    def test_credit_hours(self):
        self.assertEqual(self.cards(at(15, 40), 88, q='dishwasher now?')['load_card']['lean'], 'tonight_fine')   # finishes 17:40
        self.assertEqual(self.cards(at(15, 40), 88, q='dishwasher now?')['load_card']['latest_start_before_credit'], at(16))
        self.assertEqual(self.cards(at(16, 45), 88, q='dishwasher now?')['load_card']['lean'], 'after_credit')
        ld = self.cards(at(18, 40), 76, credit_hour1={'value': 0.004, 'at': at(18, 40)})['load_card']
        self.assertEqual((ld['lean'], ld['minutes_to_credit_end']), ('after_credit', 80))
        ld = self.cards(at(19, 30), 76, credit_hour1={'value': 0.045, 'at': at(19)}, credit_hour2={'value': 0.001, 'at': at(19, 30)})['load_card']
        self.assertEqual(ld['lean'], 'tonight_fine')                     # already missed: no reason to wait
        ld = self.cards(at(19, 20), 27, credit_hour1={'value': 0.004, 'at': at(19)})['load_card']
        self.assertEqual(ld['lean'], 'free_window')                      # energy shortfall decides first

    def test_free_window_now(self):
        ld = self.cards(at(12, 10), 92, q='dishwasher now?')['load_card']
        self.assertEqual(ld['lean'], 'now')
        self.assertEqual(ld['free_part_now'], 110)

    def test_person_figure_used(self):
        c = E.build(at(21, 40), {'soc': {'value': 64, 'at': at(21, 40)}}, 'If the dishwasher uses 1.2 kWh, how much is left above the reserve after it?')
        ld = c['load_card']
        self.assertEqual((ld['load']['low'], ld['load']['source']), (1.2, 'your figure'))
        self.assertAlmostEqual(ld['after_load_now'][0], 25.6 * 0.44 - 1.2)
        self.assertIn('about 10.1 kWh', c['text'])

    def test_no_history_still_useful(self):
        c = E.build(at(21), {'soc': {'value': 64, 'at': at(21)}, 'history': []}, 'dishwasher tonight?')
        self.assertEqual(c['load_card']['lean'], 'unknown_need')
        self.assertIn('13%', c['text'])

    def test_stale_soc_is_labelled_estimate(self):
        c = E.build(at(21), {'soc': {'value': 70, 'at': at(16, 55)}, 'history': flat(0.5, n=14)}, 'dishwasher tonight?')
        self.assertIn('no current reading (the last was 70% at 4:55 pm)', c['text'])
        self.assertIn('on the estimated charge', c['text'])
        self.assertAlmostEqual(c['battery']['soc'], 70 - (4 + 5 / 60) * 0.5 / 25.6 * 100)

    def test_unknown_battery_no_lean(self):
        c = E.build(at(21), {'history': flat()}, 'dishwasher tonight?')
        self.assertEqual(c['load_card']['lean'], 'unknown')
        self.assertIn('no battery figures', c['text'])

    def test_two_loads_left_to_calc(self):
        c = E.build(at(21), {'soc': {'value': 64, 'at': at(21)}}, 'dryer at 2.5 kWh and the dishwasher at 1.2 kWh tonight?')
        self.assertNotIn('load_card', c)
        self.assertIn('atlas_calc', c['text'])

    def test_no_controller_advice_in_cards(self):
        for soc in (5, 25, 50, 95):
            for h in (8, 12, 16, 18, 19, 21, 23):
                t = self.cards(at(h, 10), soc)['text'].lower()
                self.assertNotRegex(t, r'(lower|change|raise|adjust|set) (the )?(reserve|controller|inverter|export)')


class Calc(unittest.TestCase):
    SRC = ["Battery: 64%; that's about 16.4 kWh stored, 11.3 kWh above the 20% reserve (nominal, from the 25.6 kWh capacity). about 55c/kWh"]

    def test_eval(self):
        self.assertEqual(C.evaluate('(2 + 8) * 3 / 4')[0], 7.5)
        self.assertEqual(C.evaluate('25.6 × (64 − 20) ÷ 100')[0], 25.6 * 44 / 100)

    def test_refuses_non_arithmetic(self):
        for e in ('__import__("os")', '2 ** 100', 'a + 1', '1; 2', '9' * 300, '1/0', '1e400'):
            with self.assertRaises(C.CalcError, msg=e):
                C.evaluate(e)

    def test_tool_numbers_must_be_in_turn(self):
        ok = C.calc_tool({'expression': '11.3 - 1.2'}, self.SRC + ['the dishwasher uses 1.2 kWh'])
        self.assertEqual((ok['status'], ok['say']), ('calculated', '10.1'))
        bad = C.calc_tool({'expression': '11.3 - 7.7'}, self.SRC)
        self.assertEqual((bad['status'], bad['reason']), ('denied', 'number_not_in_turn'))
        ok = C.calc_tool({'expression': '25.6 * (64 - 20) / 100'}, self.SRC)
        self.assertEqual(ok['status'], 'calculated')
        ok = C.calc_tool({'expression': '0.42 * 0.55 / 3'}, ['paid 0.42', 'about 55c/kWh', 'split it three ways'])
        self.assertEqual(ok['say'], '0.077')
        prior = C.calc_tool({'expression': '9.75 * 2'}, ['7.5 plus 2.25, then double it'], prior_results=[9.75])
        self.assertEqual(prior['status'], 'calculated')

    def test_tool_schema_strict(self):
        self.assertEqual(C.calc_tool({'expression': '1+1', 'entity_id': 'x'}, ['1'])['status'], 'denied')
        self.assertEqual(C.calc_tool({'expression': '1+1', 'to_time': '11:00'}, ['1'])['status'], 'denied')
        self.assertEqual(C.calc_tool({}, [])['status'], 'denied')
        self.assertEqual(C.calc_tool({'from_time': '9:40', 'to_time': '11:00'}, [])['status'], 'denied')

    def test_time_span(self):
        self.assertEqual(C.calc_tool({'from_time': '21:40', 'to_time': '11:00'}, [])['say'], '13 h 20 min')
        self.assertEqual(C.calc_tool({'from_time': '18:40', 'to_time': '20:00'}, [])['minutes'], 80)

    def test_status_is_not_an_action(self):
        from atlas_household.core import STATUSES  # noqa: PLC0415
        self.assertNotIn('calculated', STATUSES)

    def test_fast_path(self):
        self.assertEqual(C.fast_arithmetic("What's 2 + 8?"), '2 + 8 is 10.')
        self.assertEqual(C.fast_arithmetic('what is 17% of 340?'), '17% of 340 is 57.8.')
        self.assertEqual(C.fast_arithmetic("What's 45 minus 17?"), '45 - 17 is 28.')
        self.assertEqual(C.fast_arithmetic('100 divided by 8'), '100 ÷ 8 is 12.5.')
        for q in ('Can you do basic arithmetic?', 'turn the lights off in 10 minutes', 'what is the battery at?', 'lights to 50%', '2 lights on'):
            self.assertIsNone(C.fast_arithmetic(q), q)


class FigureGuard(unittest.TestCase):
    SRC = ["Battery: 61%; about 10.5 kWh above the 20% reserve. Free grid power: next from 11 am tomorrow, in 14 h 13 min. "
           "Grid import at other times is paid, about 55c/kWh. 6–7 pm and 7–8 pm. Readings as of Tuesday 20 October 2026, 8:47 PM. "
           "From paid grid it would cost $0.50. House power use right now: 620 W"]

    def u(self, r):
        return C.unsupported_figures(r, self.SRC)

    def test_supported(self):
        for r in ("Tonight's fine: about 10.5 kWh above the reserve.", 'about 10 kWh', 'At 61% it is fine.', 'Wait 14 hours for 11 am.',
                  'in 14 h 13 min', 'It would cost about 50c, or $0.50.', 'after 8 pm', 'between 6 and 8 pm', 'Tuesday 20 October',
                  'the house is using 0.62 kW', 'about 0.6 kW'):
            self.assertEqual(self.u(r), [], r)

    def test_unsupported(self):
        self.assertEqual(self.u('You would have 9.3 kWh left.'), ['9.3 kWh'])
        self.assertEqual(self.u('It costs $1.98.'), ['$1.98'])
        self.assertEqual(C.unsupported_figures('It costs $1.98.', self.SRC + ['3.6 * 0.55 = 1.98']), [])   # an atlas_calc result backs money
        self.assertEqual(self.u('Battery is at 64%.'), ['64%'])
        self.assertEqual(self.u('It runs until 10:30 pm.'), ['10:30 pm'])
        self.assertEqual(self.u('since 15 October'), ['15 October'])
        self.assertEqual(self.u('about 12 kWh'), ['12 kWh'])
        self.assertEqual(self.u('about 11 kWh'), [])                  # 10.5 said as a whole number: either neighbour is honest rounding

    def test_turn_figures_nudge_then_drop(self):
        asked = []

        async def ask(t):
            asked.append(t)
            return 'Tonight is fine. You would have 9.3 kWh left.'
        reply, rec = asyncio.run(C.turn_figures('You would have 9.3 kWh left.', self.SRC, ask))
        self.assertEqual(len(asked), 1)
        self.assertEqual(reply, 'Tonight is fine.')
        self.assertEqual(rec['dropped'], ['9.3 kWh'])

        async def fixed(t):
            return 'Tonight is fine: about 10.5 kWh above the reserve.'
        reply, rec = asyncio.run(C.turn_figures('About 9.3 kWh.', self.SRC, fixed))
        self.assertEqual((reply, rec['nudged']), ('Tonight is fine: about 10.5 kWh above the reserve.', True))

    def test_instruction_figures_are_not_evidence(self):
        prompt = 'Rules: for example "a typical night here uses about 6 kWh".\nHouse readings:\n- Battery: 27%; 1.8 kWh above the 20% reserve.'
        self.assertEqual(C.unsupported_figures('A typical night uses about 6 kWh.', [C.readings_part(prompt)]), ['6 kWh'])
        self.assertEqual(C.unsupported_figures('About 1.8 kWh above the reserve.', [C.readings_part(prompt)]), [])

    def test_calc_result_is_a_source(self):
        async def never(t):
            raise AssertionError('no nudge expected')
        reply, rec = asyncio.run(C.turn_figures('After it, about 9.3 kWh.', self.SRC, never, lambda: ['10.5 - 1.2 = 9.3']))
        self.assertFalse(rec['nudged'])


class AdviceNudge(unittest.TestCase):
    def test_question_refused_is_nudged(self):
        self.assertTrue(C.advice_nudge_needed('Leave the AC off until 8 to save the credit?', "I can't control the aircon yet."))
        self.assertTrue(C.advice_nudge_needed('Put the washing on now?', "I'm afraid I can't control the washing machine yet."))

    def test_requests_and_commands_left_alone(self):
        self.assertFalse(C.advice_nudge_needed('Can you turn the aircon on?', "I can't control the aircon yet."))
        self.assertFalse(C.advice_nudge_needed('Lower the reserve and start the dryer.', "I can't change the reserve."))
        self.assertFalse(C.advice_nudge_needed('Dishwasher tonight?', "Tonight's fine: about 10.5 kWh above the reserve."))


class Cases(unittest.TestCase):
    def test_arithmetic_oracles(self):
        """The hand-written expected answers, recomputed independently of calc.py and energy_cards.py."""
        cases = {c['id']: c for c in json.loads((HERE / 'cases' / 'all.json').read_text())['cases']}
        cap, soc = 25.6, 64
        want = {'AR-01': 45 - 17, 'AR-02': 7.5 + 2.25, 'AR-03': 340 * 0.17, 'AR-04': 3.6 * 0.55, 'AR-05': round(cap * (soc - 20) / 100, 1) - 1.2,
                'AR-06': 9.6 + 12.4, 'AR-07': 18.6 - 14.2, 'AR-08': 9.6 / 14.2 * 100, 'AR-09': 13 * 60 + 20, 'AR-10': cap * soc / 100,
                'AR-11': cap * (soc - 20) / 100 - 3.7, 'AR-12': 25.6 * 0.64, 'AR-13': 4 * 0.55, 'AR-14': cap * (soc - 35) / 100,
                'AR-15': 13 * 60 + 20, 'AR-16': 1.25, 'AR-17': 0.42 * 0.55 / 3, 'AR-18': 24.6 - 22.1, 'AR-19': 0.42 + 3.1, 'AR-20': 240 * 0.85}
        for cid, v in want.items():
            ok = any(lo - 0.051 <= v <= hi + 0.051 or (lo == hi and abs(round(v, 2) - lo) < 1e-9) for lo, hi in cases[cid]['answers'])
            self.assertTrue(ok, (cid, v, cases[cid]['answers']))

    def test_counts(self):
        cases = json.loads((HERE / 'cases' / 'all.json').read_text())['cases']
        groups = {}
        for c in cases:
            groups[c['group'].split('-')[0]] = groups.get(c['group'].split('-')[0], 0) + 1
        self.assertEqual(groups, {'codex49': 40, 'owner': 3, 'dishwasher': 14, 'arithmetic': 20, 'cooling': 3})


class Prompt(unittest.TestCase):
    def test_current_arm_is_the_golive_template(self):
        import render as R  # noqa: PLC0415
        self.assertEqual(R.current_template().replace('\n' + R.CARDS_SLOT + '\n', '', 1), R.TEMPLATE)

    def test_candidate_edits_exactly(self):
        import render as R  # noqa: PLC0415
        t = R.candidate_template()
        self.assertNotIn('Good advice: run big loads', t)
        self.assertNotIn('cheapest choice is usually to wait', t)
        self.assertNotIn('Never invent or estimate a figure', t)
        self.assertIn('call atlas_calc', t)
        self.assertIn("you can't change the battery, the inverter, exports or any energy setting", t)   # the no-control rule stays
        self.assertIn('Never: energy, solar, battery, inverter or controller settings', t)

    def test_renders(self):
        import render as R  # noqa: PLC0415
        p = R.system_prompt('candidate', at(20, 47), {'soc': 61}, '- card')
        self.assertIn('- Home battery charge: 61 %', p)
        self.assertIn('Readings as of Tuesday 20 October 2026, 8:47 PM', p)
        self.assertIn('Handles you can use:', p)
        self.assertEqual([t['function']['name'] for t in R.tool_specs('candidate')][-1], 'atlas_calc')
        self.assertNotIn('atlas_calc', [t['function']['name'] for t in R.tool_specs('current')])


if __name__ == '__main__':
    unittest.main()
