"""Daylight-saving cases (Codex 41 RT068 and the spring-forward twin). Needs the real Australia/Sydney zone, which this PC's Windows Python lacks,
so it is skipped there and run inside the test copy's container:
  MSYS_NO_PATHCONV=1 docker exec atlas-ha-test python3 -m unittest /config/atlas-tests/test_dst.py   (run_dst_in_container.sh copies it in)
"""
import pathlib
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'custom_components'))
try:
    from zoneinfo import ZoneInfo
    REAL_SYDNEY = ZoneInfo('Australia/Sydney')
except Exception:          # noqa: BLE001
    REAL_SYDNEY = None


@unittest.skipIf(REAL_SYDNEY is None, 'no tz database here (run in the test copy container)')
class Dst(unittest.TestCase):
    def house(self, start):
        from atlas_household import fake
        fake.SYDNEY = REAL_SYDNEY
        h = fake.FakeHouse(start=start)
        h.coord.tz = REAL_SYDNEY
        h.set('light.office_ceiling', 'on')
        return h

    def test_RT068_doubled_time_is_asked(self):
        h = self.house(datetime(2026, 4, 5, 1, 50, tzinfo=REAL_SYDNEY))       # 02:00-03:00 happens twice (AEDT, then AEST)
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '02:05'})
        self.assertEqual((r['status'], r['reason']), ('needs_choice', 'ambiguous_time'))      # a question, not a refusal (RT068 "ask")
        self.assertEqual(h.coord.data['tasks'], [])

    def test_R4_02_second_occurrence_still_ahead_is_asked(self):
        h = self.house(datetime(2026, 4, 5, 2, 50, tzinfo=REAL_SYDNEY, fold=0))   # 02:50 AEDT; 02:20 AEST is still 30 min ahead
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '02:20'})
        self.assertEqual((r['status'], r['reason']), ('needs_choice', 'ambiguous_time'))

    def test_skipped_time_is_asked(self):
        h = self.house(datetime(2026, 10, 4, 1, 50, tzinfo=REAL_SYDNEY))      # 02:00-03:00 doesn't exist (spring forward)
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '02:15'})
        self.assertEqual((r['status'], r['reason']), ('needs_choice', 'ambiguous_time'))

    def test_R5_03_skipped_hour_already_behind_is_too_far(self):
        h = self.house(datetime(2026, 10, 4, 3, 20, tzinfo=REAL_SYDNEY))      # 03:20 AEDT, after the spring gap
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '02:30'})
        self.assertEqual(r['status'], 'scheduled')                               # tomorrow's 02:30 (24 h cap, directive 1151): not a question
        due = datetime.fromisoformat(h.coord.data['tasks'][0]['due_at']).astimezone(REAL_SYDNEY)
        self.assertEqual((due.day, due.hour, due.minute), (5, 2, 30))

    def test_in_minutes_across_the_change_is_elapsed_time(self):
        h = self.house(datetime(2026, 4, 5, 2, 50, tzinfo=REAL_SYDNEY, fold=0))
        r = h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'in_minutes': 20})
        self.assertEqual(r['status'], 'scheduled')
        due = datetime.fromisoformat(h.coord.data['tasks'][0]['due_at'])
        self.assertEqual(due - h.clock, timedelta(minutes=20))

    def test_ordinary_at_time_on_a_normal_day(self):
        h = self.house(datetime(2026, 10, 18, 19, 30, tzinfo=REAL_SYDNEY))
        self.assertEqual(h.call('atlas_schedule', {'target_handle': 'office_lights', 'operation': 'off', 'at_time': '19:50'})['status'], 'scheduled')


if __name__ == '__main__':
    unittest.main()
