"""Every summary the coordinator writes must pass the claim guard unchanged with its own status (R13-02: the guard rewrote the
coordinator's honest not_verified summary into a false "I haven't changed anything."). Records every result the core builds (core._r)
while the core tests and both Codex runners run on the fake, then relays each summary through guard_reply."""
import contextlib
import io
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'custom_components'))
sys.path.insert(0, str(HERE))
from atlas_household import core  # noqa: E402


class OwnSummaries(unittest.TestCase):
    def test_every_summary_passes(self):
        seen, orig = {}, core._r

        def rec(status, summary, **kw):
            seen.setdefault((status, summary), kw.get('reason'))
            return orig(status, summary, **kw)

        core._r = rec
        oc, ot = core.Coordinator.call_tool, core.Coordinator.tick

        async def call_tool(self, *a, **kw):
            res = await oc(self, *a, **kw)
            seen.setdefault((res['status'], res['summary']), 'final')
            return res

        async def tick(self):
            out = await ot(self)
            for res in out:
                seen.setdefault((res['status'], res['summary']), 'tick')
            return out

        core.Coordinator.call_tool, core.Coordinator.tick = call_tool, tick
        try:
            from atlas_household.fake import FakeHouse
            for faulty in (True, False):          # dim/brighten "Done:" and partial undo, with and without a device that ignores the call
                h = FakeHouse()
                for e in ('light.attic_lamp', 'light.attic_downlight_left'):
                    h.set(e, 'on', brightness_percent=50)
                for op in ('dim', 'brighten'):
                    h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': op})
                h.call('atlas_lights', {'target_handle': 'attic_lights', 'operation': 'off'})
                if faulty:
                    h.backend.no_readback.add('light.attic_lamp')
                h.set('light.attic_downlight_left', 'on')
                h.call('atlas_undo', {})
            import run_codex40
            import run_redteam41
            import test_core
            with contextlib.redirect_stdout(io.StringIO()):
                run_codex40.main(write=False)
                run_redteam41.main(write=False)
            unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(unittest.defaultTestLoader.loadTestsFromModule(test_core))
        finally:
            core._r = orig
            core.Coordinator.call_tool, core.Coordinator.tick = oc, ot
        self.assertGreater(len(seen), 80)
        bad = [(st, s, guard_reply_out) for (st, s) in seen for guard_reply_out in [core.guard_reply(s, [st])] if guard_reply_out[1]]
        self.assertEqual(bad, [], f'{len(bad)} of {len(seen)} summaries rewritten')


if __name__ == '__main__':
    unittest.main()
