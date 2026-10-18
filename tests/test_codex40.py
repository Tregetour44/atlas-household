"""Runs Codex run 40's 52 cases (run_codex40.py) as part of the offline suite."""
import unittest

import run_codex40


class Codex40(unittest.TestCase):
    def test_all_52(self):
        self.assertEqual(run_codex40.main(write=False), 0)

    def test_redteam41_coordinator_side(self):
        import run_redteam41
        self.assertEqual(run_redteam41.main(write=False), 0)


if __name__ == '__main__':
    unittest.main()
