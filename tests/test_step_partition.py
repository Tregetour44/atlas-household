"""Exhaustive property test of dim/brighten (reviews R9-01, R10-01): every combination of 7 light states over a 4-light group, for both
operations (7^4 x 2 = 4,802 cases). Each case must satisfy the honesty invariants, so no "twin" of an earlier bug can hide in an untested mix.
States: gone (unavailable), fixed_on / fixed_off (on/off-only), dim1 / dim50 / dim100 (dimmable, on at that level), dimoff (dimmable, off).
"""
import itertools
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'custom_components'))
from atlas_household.fake import FakeHouse  # noqa: E402

LIGHTS = ['light.attic_lamp', 'light.attic_downlight_left', 'light.attic_downlight_middle', 'light.attic_downlight_right']   # the attic_lights handle
STATES = ['gone', 'fixed_on', 'fixed_off', 'dim1', 'dim50', 'dim100', 'dimoff']


def setup(h, combo):
    for e, s in zip(LIGHTS, combo):
        a = h.backend.states[e]['attributes']
        if s == 'gone':
            h.set(e, 'unavailable')
        elif s.startswith('fixed'):
            h.set(e, 'on' if s == 'fixed_on' else 'off')
            a.update(brightness=None, supported_color_modes=['onoff'])
        elif s == 'dimoff':
            h.set(e, 'off')
            a['supported_color_modes'] = ['brightness']
        else:
            h.set(e, 'on', brightness_percent=int(s[3:]))
            a['supported_color_modes'] = ['brightness']
    h.calls.clear()


def lit(s):
    return s in ('fixed_on', 'dim1', 'dim50', 'dim100')


class StepPartition(unittest.TestCase):
    def test_every_combination(self):
        bad = []
        h = FakeHouse()
        for op in ('dim', 'brighten'):
            for combo in itertools.product(STATES, repeat=4):
                h.coord.data['receipts'].clear()
                setup(h, combo)
                r = h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': op})
                st, summ = r['status'], r['summary']
                sent = {e: c['data'].get('brightness_pct') for c in h.calls for e in c['entity_ids']}
                kind = dict(zip(LIGHTS, combo))
                limit = 'dim1' if op == 'dim' else 'dim100'
                any_lit = any(lit(s) for s in combo)
                problems = []
                if st == 'skipped_already':
                    lit_ones = [s for s in combo if lit(s)]
                    true_already = (lit_ones and all(s == limit for s in lit_ones)) or (op == 'dim' and not lit_ones)
                    if not true_already:
                        problems.append('false already')
                if any_lit and ('is off' in summ or 'Everything' in summ):
                    problems.append('says off while a light is on')
                for e, lvl in sent.items():
                    if kind[e].startswith('fixed') or kind[e] == 'gone':
                        problems.append(f'sent to {kind[e]}')
                    if op == 'dim' and kind[e] == 'dimoff':
                        problems.append('dim turned a light on')
                    if op == 'brighten' and kind[e] == 'dimoff' and any_lit:
                        problems.append('brighten turned on an off light while others were lit')
                if st == 'denied' and r.get('reason') == 'not_supported':
                    steppable = [s for s in combo if s in ('dim50',) or (s == 'dim1' and op == 'brighten') or (s == 'dim100' and op == 'dim')
                                 or (s == 'dimoff' and op == 'brighten' and not any_lit)]
                    if steppable:
                        problems.append('refused although a light could be stepped')
                if st == 'done' and not sent:
                    problems.append('done with nothing sent')
                if problems:
                    bad.append((op, combo, st, summ, problems))
        self.assertEqual(bad[:5], [], f'{len(bad)} bad cases')


if __name__ == '__main__':
    unittest.main()
