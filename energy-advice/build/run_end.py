"""Position check: the candidate arm with the energy cards where the integration actually puts them. The guarded agent passes the cards as
extra_system_prompt, which HA's Ollama agent appends after the API prompt (the main candidate run has them inside the template, before the
energy history). Same arguments as run_eval.py; use --arm candidate and its own --out file.
"""
import sys

import render as R
import run_eval

_orig = R.system_prompt


def _at_end(arm, now, house, cards_text=''):
    return _orig(arm, now, house, '') + ('\n' + cards_text if cards_text else '')


R.system_prompt = _at_end

if __name__ == '__main__':
    sys.exit(run_eval.main())
