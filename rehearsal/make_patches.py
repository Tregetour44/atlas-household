"""Builds patches/*.patch against the input branch, as three cumulative steps, and runs the offline suite on each intermediate tree:
  0001-gap-fixes            the safety fixes for the rehearsal's MAJOR and MINOR gaps (G01-G13, G18) + tests/test_rehearsal_gaps.py
  0002-fast-paths           Part B: scene, blind and read-only fast paths + tests/test_fast_paths.py
  0003-optional-over-refusals  narrow fixes for MINOR over-refusals (G14-G17) + tests/test_over_refusals.py; the owner decides
Each step's tree is the final tree with the later steps' edits peeled off (exact reverse replacements, each asserted).
Usage: python -I rehearsal/make_patches.py   (from the repository root, on branch atlas-robustness)
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = 'custom_components/atlas_household/core.py'
TURN = 'custom_components/atlas_household/turn.py'
FAST = 'custom_components/atlas_household/fastpath.py'

# step 3 -> step 2: the optional over-refusal fixes, peeled off (new text, old text)
OPTIONAL = {CORE: [
    ('''_ONE = r"(?<!\\bin )(?<!\\bat )\\bone\\b(?!\\s*(?:hours?|minutes?|mins?|seconds?|hrs?|o'?clock|am|pm|thirty|fifteen|forty))"   # not "in one hour", "at one" [G15]
_AFTER_PLACE_LIGHT = re.compile(r"\\b(?:it|its|that|this|her)\\b|" + _ONE + r"|(?<!of )\\bthem\\b|"''',
     '''_AFTER_PLACE_LIGHT = re.compile(r"\\b(?:it|its|that|this|her|one)\\b|(?<!of )\\bthem\\b|"'''),
    ('''(?!\\s*$)|\\bher\\b|" + _ONE + r"|(?<!of )\\bthem\\b|"''', '''(?!\\s*$)|\\b(?:her|one)\\b|(?<!of )\\bthem\\b|"'''),
    ('''        t = _BLIND_ON_DOOR.sub(' door blind ', t)                            # "the blind on the family room door" is the door blind [G14]
''', ''),
    ('''_BLIND_ON_DOOR = re.compile(r"\\bblinds?\\s+(?:on|by|at|near|of)\\s+(?:the\\s+)?(?:(?:family|living|lounge|dining|sun)\\s+room\\s+|sunroom\\s+)?door\\b"
                            r"(?![\\s-]*(?:lock|opener|strike|release|bell))", re.I)
''', ''),
    ('ll re ve m drop everywhere', 'll re ve m'),
    ('''
        words = re.sub(r"\\bat\\s+(\\d{1,3}\\s*(?:%|per\\s*cent|percent))", r"to \\1", words, flags=re.I)     # "at 40 per cent" is a level, never a time [G16]''', ''),
    ('''|what|is|are|pause|mute|unmute|resume)\\b")     # [G16] media verbs''', '''|what|is|are)\\b")'''),
    ('''                if toks - vocab and not verbs.search(c) and seen and not toks & {'light', 'lights', 'lamp', 'lamps'}:    # "...and the sunroom lights on" is about lights [G16]''',
     '''                if toks - vocab and not verbs.search(c) and seen:'''),
    ('''r"\\b(?:all|every|everywhere)\\b", c)''', '''r"\\b(?:all|every)\\b", c)'''),
    ('''        scene_words = {w for o in self.handles.values() if o.get('kind') == 'scene' and o.get('enabled', True) for w in re.findall(r"[a-z]+", o['label'].lower())}
        if used_all and {self._BLIND_SYNONYMS.get(w, w) for w in re.findall(r"[a-z]+", self._BLIND_NOT_ALL.sub(' ', words.lower()))} - vocab - scene_words - {'and', 'then', 'also'}:   # a scene's
            # name is not a place: "good night and close all the blinds" [G16]''',
     '''        if used_all and {self._BLIND_SYNONYMS.get(w, w) for w in re.findall(r"[a-z]+", self._BLIND_NOT_ALL.sub(' ', words.lower()))} - vocab:'''),
    ('''            if scope is None:
                scope = self._yes_scope(ctx, a)          # a plain yes to Atlas's own one-blind question [G17]
''', ''),
    (None, ('    _ASKED = re.compile(', '    def _blind_words(self, handle: str) -> set[str]:')),     # cut the whole _ASKED/_yes_scope block
    ('''(?!\\s+(in|on|at)\\s+the\\b(?!\\s+(?:house|home|place)\\b))", re.I)   # "every light in the house" [G20]''', '''(?!\\s+(in|on|at)\\s+the\\b)", re.I)'''),
]}

# step 2 -> step 1: the fast paths, peeled off
FASTPATHS = {
    CORE: [
        ('''        from .readings import check_readings      # read-only fast answers: their own section, never a handle, never a tool [cloud robustness job]
        self.readings = check_readings(targets.get('readings'))
        fp = targets.get('fast_paths')             # which deterministic paths run_turn may use (absent: all of them)
        self.fast_paths = set(FAST_PATHS if fp is None else fp)
        if self.fast_paths - set(FAST_PATHS):
            raise ValueError(f'unknown fast_paths {sorted(self.fast_paths - set(FAST_PATHS))}')
''', ''),
        ("FAST_PATHS = ('timer', 'level', 'scene', 'blind', 'read')\n", ''),
    ],
    FAST: [(None, ('\n\n# ---------- the SCENE and BLIND paths', None))],          # cut to the end of the file
    TURN: [
        ('''from .fastpath import parse_blind, parse_level, parse_scene, parse_timer
from .readings import answer, parse_question
''', '''from .fastpath import parse_level, parse_timer
'''),
        (None, ('''    paths = getattr(coord, 'fast_paths', {'timer', 'level'})''', '''    def evidence():''')),
    ],
}
TURN_FAST_OLD = '''    fast = parse_timer(text, coord.handles, now_local or coord.now().astimezone(coord.tz), getattr(coord, 'timer_scenes', True))
    tool, label, sorry = 'atlas_schedule', 'fast_timer', "I didn't set that timer."
    if fast is None:
        fast = parse_level(text, coord.handles)
        tool, label, sorry = 'atlas_lights', 'fast_level', "I didn't change anything."
    if fast is not None:
        try:
            if call_tool is None:
                res = await coord.call_tool(tool, fast, conversation_id=conversation_id, user_text=text)
            else:
                res = await call_tool(tool, fast)
        except Exception as ex:      # noqa: BLE001  [B16-06] said honestly, never HA's generic error
            coord._log(label, 'error', conversation=conversation_id, args=fast, error=f'{type(ex).__name__}: {ex}')
            res = {'status': 'tool_error', 'summary': f"Something went wrong, so {sorry}"}
        reply = res.get('summary') or f"Sorry, {sorry}"
        coord._log(label, res.get('status'), conversation=conversation_id, args=fast)
        return {'reply': reply, 'path': 'fast', 'claims': [], 'statuses': [res.get('status')], 'first': None, 'args': fast, 'tool': tool,
                'tool_results': coord.results_since(t0, conversation_id) or [(tool, fast, res)]}

'''


def peel(tree: pathlib.Path, edits: dict) -> None:
    for rel, pairs in edits.items():
        p = tree / rel
        s = p.read_text(encoding='utf-8')
        for new, old in pairs:
            if new is None:                          # cut a block from a start marker up to an end marker (kept); None = to the end
                start, end = old
                i = s.index(start)
                j = len(s) if end is None else s.index(end, i)
                s = s[:i] + (TURN_FAST_OLD if rel == TURN else '') + s[j:]
                continue
            assert s.count(new) == 1, (rel, new[:80], s.count(new))
            s = s.replace(new, old)
        p.write_text(s, encoding='utf-8')


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='atlas-patches-'))
    trees = {}
    for k in ('t0', 't1', 't2', 't3'):
        trees[k] = tmp / k
    subprocess.run(f'git archive atlas-current-input custom_components tests | tar -x -C {tmp}', shell=True, cwd=ROOT, check=True)
    (tmp / 'custom_components').rename(tmp / 'cc0')
    (tmp / 'tests').rename(tmp / 'tests0')
    for k in trees:
        trees[k].mkdir()
    shutil.copytree(tmp / 'cc0', trees['t0'] / 'custom_components')
    shutil.copytree(tmp / 'tests0', trees['t0'] / 'tests')
    for k in ('t1', 't2', 't3'):
        shutil.copytree(ROOT / 'custom_components', trees[k] / 'custom_components', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'tests', trees[k] / 'tests', ignore=shutil.ignore_patterns('__pycache__', 'results*'))
    for k in trees:
        shutil.copytree(ROOT / 'packs', trees[k] / 'packs')          # unchanged; the suite reads the Codex packs
    peel(trees['t2'], OPTIONAL)
    (trees['t2'] / 'tests' / 'test_over_refusals.py').unlink()
    peel(trees['t1'], OPTIONAL)
    (trees['t1'] / 'tests' / 'test_over_refusals.py').unlink()
    peel(trees['t1'], FASTPATHS)
    (trees['t1'] / 'tests' / 'test_fast_paths.py').unlink()
    (trees['t1'] / 'custom_components' / 'atlas_household' / 'readings.py').unlink()
    out = ROOT / 'patches'
    out.mkdir(exist_ok=True)
    ok = True
    for k in ('t1', 't2', 't3'):
        r = run([sys.executable, '-I', '-B', '-W', 'ignore', '-m', 'unittest', 'discover', '-s', 'tests'], trees[k])
        last = (r.stderr.strip().splitlines() or ['?'])[-1]
        print(k, last)
        ok = ok and last.startswith('OK')
    names = [('t0', 't1', '0001-gap-fixes.patch'), ('t1', 't2', '0002-fast-paths.patch'), ('t2', 't3', '0003-optional-over-refusals.patch')]
    repo = tmp / 'repo'
    for a, b, name in names:                       # each step's diff from a scratch git repo: tree a committed, then tree b over it
        if repo.exists():
            shutil.rmtree(repo)
        repo.mkdir()
        g = lambda *c: subprocess.run(['git', '-c', 'user.email=x@x', '-c', 'user.name=x', *c], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
        g('init', '-q')
        for d in ('custom_components', 'tests'):
            shutil.copytree(trees[a] / d, repo / d, ignore=shutil.ignore_patterns('__pycache__'))
        g('add', '-A')
        g('commit', '-qm', a)
        for d in ('custom_components', 'tests'):
            shutil.rmtree(repo / d)
            shutil.copytree(trees[b] / d, repo / d, ignore=shutil.ignore_patterns('__pycache__'))
        g('add', '-A')
        d = g('diff', '--cached', '--stat', '-p').stdout
        (out / name).write_text(d, encoding='utf-8')
        print(name, len(d.splitlines()), 'lines')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
