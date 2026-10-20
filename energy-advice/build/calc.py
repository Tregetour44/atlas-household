"""Atlas arithmetic in code (energy-advice-build; the owner, 20 Oct: "it couldnt even do basic arithmatic"). Pure Python, no HA import.

Three pieces, so no figure Atlas says comes from the model's own arithmetic:
  1. fast_arithmetic(text): a whole-utterance sum ("what's 2 + 8?", "17% of 340", "100 divided by 8") is answered here, the model is not
     asked (like fastpath.parse_timer: strict grammar, whole utterance only, anything else returns None).
  2. atlas_calc, a read-only tool: pure arithmetic over numbers ALREADY IN THE TURN (the person's words, the readings and energy cards in the
     prompt, earlier atlas_calc results), or the time from one clock time to the next. No device access, no state reads, no side effects;
     an operand that isn't in the turn is refused, so the tool can't launder a made-up number into a "computed" one.
  3. unsupported_figures(reply, sources): the figure guard. Every quantity in a reply must match one in the turn's sources (same kind of
     unit, within the reply's own rounding). turn_figures() applies it like core.guard_reply: one nudge, then unsupported sentences dropped.
Evaluation is an AST walk over + - * / and brackets only (no eval, no names, no powers), bounded in length and size.
"""
from __future__ import annotations

import ast
import math
import re

TOOL_NAME = 'atlas_calc'
CONSTANTS = {100.0, 60.0, 1000.0, 24.0}          # unit conversions the tool may use without a source: %, minutes, W<->kW, hours
_MAX_LEN, _MAX_NUMBERS, _MAX_ABS = 200, 12, 1e9

TOOL_SPEC = (TOOL_NAME,
             'Arithmetic in code. Use it for ANY sum, difference, product, share, percentage, cost or time span you need: never work a figure '
             'out yourself. Give expression (numbers from the readings, the energy cards or the person\'s words, with + - * / and brackets; '
             'a percentage p of x is x * p / 100), OR from_time and to_time (24-hour HH:MM) for how long from one clock time to the next.',
             {'expression': {'type': 'string', 'description': 'For example (25.6 * (61 - 20) / 100) - 4.0'},
              'from_time': {'type': 'string', 'description': '24-hour HH:MM'},
              'to_time': {'type': 'string', 'description': '24-hour HH:MM'}},
             [])

NUMBER_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
                'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
                'hundred': 100, 'half': 0.5, 'quarter': 0.25, 'double': 2, 'twice': 2, 'triple': 3}


class CalcError(ValueError):
    pass


def _walk(node, seen: list[float]) -> float:
    if isinstance(node, ast.Expression):
        return _walk(node.body, seen)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        seen.append(float(node.value))
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _walk(node.operand, seen)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = _walk(node.left, seen), _walk(node.right, seen)
        if isinstance(node.op, ast.Div):
            if b == 0:
                raise CalcError('division by zero')
            r = a / b
        else:
            r = a + b if isinstance(node.op, ast.Add) else a - b if isinstance(node.op, ast.Sub) else a * b
        if not math.isfinite(r) or abs(r) > _MAX_ABS:
            raise CalcError('result out of range')
        return r
    raise CalcError('only numbers, + - * / and brackets are allowed')


def evaluate(expression: str) -> tuple[float, list[float]]:
    """(value, operands). Raises CalcError for anything but plain arithmetic."""
    if not isinstance(expression, str) or not expression.strip():
        raise CalcError('expression must be text')
    e = expression.replace('×', '*').replace('÷', '/').replace('−', '-').replace('–', '-').replace(',', '')
    e = re.sub(r'(?<=\d)\s*x\s*(?=[\d(])', '*', e)
    if len(e) > _MAX_LEN:
        raise CalcError('expression too long')
    if re.search(r'\*\*|//|[A-Za-z_=;:\[\]{}\'"]', e):
        raise CalcError('only numbers, + - * / and brackets are allowed')
    try:
        tree = ast.parse(e, mode='eval')
    except SyntaxError:
        raise CalcError('not a valid sum') from None
    seen: list[float] = []
    v = _walk(tree, seen)
    if len(seen) > _MAX_NUMBERS:
        raise CalcError('too many numbers')
    return v, seen


def say(v: float) -> str:
    """Display only: whole numbers bare, otherwise up to 2 decimals (4 for small values), trailing zeros dropped."""
    if abs(v - round(v)) < 1e-9:
        return f'{round(v):,}'.replace(',', '')
    d = 4 if abs(v) < 0.1 else 2
    return f'{v:.{d}f}'.rstrip('0').rstrip('.')


# ---- quantities in text (shared by the tool's operand check and the figure guard) ----

_MONTHS = r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
_NUM = r'(\d+(?:\.\d+)?)'
_Q = re.compile(
    r'(?P<range>\b(?P<r1>\d{1,2})(?::(?P<r1m>\d{2}))?\s*(?:[–-]|to)\s*(?P<r2>\d{1,2})(?::(?P<r2m>\d{2}))?\s*(?P<rap>am|pm|a\.m\.|p\.m\.))'
    r'|(?P<tod>\b(?P<th>\d{1,2})(?::(?P<tm>\d{2}))?\s*(?P<ap>am|pm|a\.m\.|p\.m\.)(?![a-z]))'
    r'|(?P<tod24>\b(?P<h24>[01]?\d|2[0-3]):(?P<m24>[0-5]\d)\b)'
    r'|(?P<named>\b(?:noon|midday|midnight)\b)'
    r'|(?P<dur>\b(?P<dh>\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)\b(?:\s*(?:and\s*)?(?P<dm>\d+)\s*(?:min|mins|minutes?)\b)?)'
    r'|(?P<durm>\b(?P<mm>\d+)\s*(?:min|mins|minutes?)\b)'
    r'|(?P<date>\b(?P<dd>\d{1,2})(?:st|nd|rd|th)?\s+' + _MONTHS + r'\b)'
    r'|(?P<money>\$\s?(?P<dol>\d+(?:\.\d+)?)|\b(?P<cents>\d+(?:\.\d+)?)\s?(?:c|cents?)\b)'
    r'|(?P<qty>(?<![\w.])(?P<qv>[+-]?\d+(?:\.\d+)?)\s*(?P<qu>kWh|Wh|kW|W\b|%|per ?cent\b|percent\b|points?\b|°\s?C|degrees?\b|days?\b|nights?\b)?)',
    re.I)


def _dec(s: str) -> int:
    return len(s.split('.')[1]) if '.' in s else 0


def _ap(h: int, ap: str | None) -> list[int]:
    if ap is None:
        return [h % 24]
    pm = ap.lower().startswith('p')
    return [(h % 12) + (12 if pm else 0)]


def quantities(text: str) -> list[tuple[str, float, int, str]]:
    """(kind, value, decimals, text) for each quantity: kinds tod (minutes of the day), dur (minutes), date (day of month), money ($),
    kwh, w, pct, temp, count, plain. A year (2020-2039) and list numbering are not quantities."""
    out = []
    text = (text or '').replace('’', "'")
    for m in _Q.finditer(text):
        g = m.group
        if g('range'):
            ap = g('rap')
            for h, mi in ((g('r1'), g('r1m')), (g('r2'), g('r2m'))):
                for hh in _ap(int(h), ap):
                    out.append(('tod', hh * 60 + int(mi or 0), 0, m[0]))
        elif g('tod'):
            for hh in _ap(int(g('th')), g('ap')):
                out.append(('tod', hh * 60 + int(g('tm') or 0), 0, m[0]))
        elif g('tod24'):
            out.append(('tod', int(g('h24')) * 60 + int(g('m24')), 0, m[0]))
        elif g('named'):
            out.append(('tod', 0 if g('named').lower() == 'midnight' else 720, 0, m[0]))
        elif g('dur'):
            mins = float(g('dh')) * 60 + float(g('dm') or 0)
            out.append(('dur', mins, 0 if g('dm') or '.' not in g('dh') else _dec(g('dh')) + 1, m[0]))
        elif g('durm'):
            out.append(('dur', float(g('mm')), 0, m[0]))
        elif g('date'):
            out.append(('date', float(g('dd')), 0, m[0]))
        elif g('money'):
            if g('dol') is not None:
                out.append(('money', float(g('dol')), _dec(g('dol')), m[0]))
            else:
                out.append(('money', float(g('cents')) / 100, _dec(g('cents')) + 2, m[0]))
        else:
            v, u = float(g('qv')), (g('qu') or '').lower().replace(' ', '')
            if not u and 2020 <= v <= 2039 and '.' not in g('qv'):
                continue
            kind = {'kwh': 'kwh', 'wh': 'kwh', 'kw': 'w', 'w': 'w', '%': 'pct', 'percent': 'pct', 'percent': 'pct', 'point': 'pct',
                    'points': 'pct', 'degree': 'temp', 'degrees': 'temp', 'day': 'count', 'days': 'count', 'night': 'count',
                    'nights': 'count'}.get(u, 'temp' if u.startswith('°') else 'plain')
            if u == 'wh':
                v, dec = v / 1000, _dec(g('qv')) + 3
            elif u == 'kw':
                v, dec = v * 1000, _dec(g('qv')) - 3
            else:
                dec = _dec(g('qv'))
            out.append((kind, v, dec, m[0]))
    return out


def _words(text: str) -> list[float]:
    return [float(NUMBER_WORDS[w]) for w in re.findall(r'[a-z]+', (text or '').lower()) if w in NUMBER_WORDS]


def source_numbers(sources: list[str]) -> set[float]:
    """Every number literal in the sources (and number words in them), for the tool's operand check; money in cents also as dollars."""
    out: set[float] = set()
    for s in sources:
        for k, v, _, raw in quantities(s):
            out.add(round(v, 6))
            for lit in re.findall(r'\d+(?:\.\d+)?', raw):
                out.add(round(float(lit), 6))
        for lit in re.findall(r'(?<![\w.])\d+(?:\.\d+)?', (s or '').replace(',', '')):
            out.add(round(float(lit), 6))
        out.update(round(w, 6) for w in _words(s))
    return out


def calc_tool(args: dict, sources: list[str], prior_results: list[float] | None = None) -> dict:
    """The atlas_calc tool. args are checked like tools.validate_args (unknown fields rejected). Never touches the house."""
    if not isinstance(args, dict) or any(k not in ('expression', 'from_time', 'to_time') for k in args):
        return {'status': 'denied', 'reason': 'unknown field', 'summary': 'Only expression, or from_time and to_time.'}
    if 'expression' in args and ('from_time' in args or 'to_time' in args):
        return {'status': 'denied', 'reason': 'both modes', 'summary': 'Give an expression, or from_time and to_time, not both.'}
    if 'expression' in args:
        try:
            v, operands = evaluate(args['expression'])
        except CalcError as ex:
            return {'status': 'denied', 'reason': str(ex), 'summary': f"I couldn't work that out: {ex}."}
        allowed = source_numbers(sources) | CONSTANTS | {round(x, 6) for x in (prior_results or [])}
        stray = [x for x in operands if round(x, 6) not in allowed]
        if stray:
            return {'status': 'denied', 'reason': 'number_not_in_turn', 'summary':
                    f"{say(stray[0])} isn't in the readings, the energy cards or the person's words; use only figures you were given."}
        return {'status': 'calculated', 'expression': args['expression'], 'result': v, 'say': say(v),
                'summary': f"{args['expression']} = {say(v)}"}
    if 'from_time' in args and 'to_time' in args:
        a, b = args['from_time'], args['to_time']
        if not all(isinstance(x, str) and re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', x) for x in (a, b)):
            return {'status': 'denied', 'reason': 'bad time', 'summary': 'Times must be 24-hour HH:MM.'}
        m = (int(b[:2]) * 60 + int(b[3:]) - int(a[:2]) * 60 - int(a[3:])) % 1440
        text = f'{m // 60} h' + (f' {m % 60} min' if m % 60 else '') if m >= 60 else f'{m} min'
        return {'status': 'calculated', 'from_time': a, 'to_time': b, 'minutes': m, 'result': m, 'say': text,
                'summary': f'From {a} to the next {b} is {text}.'}
    return {'status': 'denied', 'reason': 'missing', 'summary': 'Give an expression, or from_time and to_time.'}


# ---- 1. whole-utterance arithmetic, answered without the model ----

_OPS = [(r'\bmultiplied by\b|\btimes\b|×|\*|(?<=\d)\s*x\s*(?=\d)', '*'), (r'\bdivided by\b|\bover\b|÷|/', '/'),
        (r'\bplus\b|\+|\band\b', '+'), (r'\bminus\b|\btake away\b|−|–', '-')]
_FAST = re.compile(r"^\s*(?:(?:hey\s+)?atlas,?\s+)?(?:what(?:'s| is)|whats|calculate|work out|how much is)?\s*(?P<e>[\d\s.,()+\-*/×÷x−–]+|"
                   r"[\d.,]+(?:\s*(?:plus|minus|times|multiplied by|divided by|over|take away|and|[+\-*/×÷x−–])\s*[\d.,]+)+)\s*[?.!]?\s*$", re.I)
_PCT = re.compile(r"^\s*(?:(?:hey\s+)?atlas,?\s+)?(?:what(?:'s| is)|whats|calculate|work out)?\s*(?P<p>\d+(?:\.\d+)?)\s*(?:%|percent|per cent)\s+of\s+"
                  r"(?P<x>\d+(?:\.\d+)?)\s*[?.!]?\s*$", re.I)


def fast_arithmetic(text: str) -> str | None:
    """A reply for a whole utterance that is plain arithmetic, else None (the turn goes to the model as before)."""
    t = (text or '').strip()
    m = _PCT.match(t)
    if m:
        v = float(m['x']) * float(m['p']) / 100
        return f"{m['p']}% of {m['x']} is {say(v)}."
    m = _FAST.match(t)
    if not m or not re.search(r'\d.*(?:[+\-*/×÷x−–]|plus|minus|times|multiplied|divided|over|take away|and).*\d', m['e'], re.I):
        return None
    e = m['e']
    for pat, op in _OPS:
        e = re.sub(pat, f' {op} ', e, flags=re.I)
    try:
        v, _ = evaluate(e)
    except CalcError:
        return None
    shown = re.sub(r'\s+', ' ', e).strip().replace('*', '×').replace('/', '÷')
    return f'{shown} is {say(v)}.'


# ---- 3. the figure guard ----

_COMPATIBLE = {'plain': None}


def _match(kind: str, v: float, dec: int, src: list[tuple[str, float, int, str]]) -> bool:
    tol = 0.5 * 10 ** (-dec) + 1e-9
    if kind == 'tod':
        return any(k == 'tod' and (abs(s - v) < 1e-9 or abs((s - v) % 720) < 1e-9) for k, s, _, _ in src)   # 9 pm said as 9:00 or 21:00
    if kind == 'dur':
        tol = max(tol, 0.5)
        return any(k == 'dur' and (abs(s - v) <= tol or (dec == 0 and v % 60 == 0 and abs(s - v) < 60)) for k, s, _, _ in src)
    if kind == 'plain' and dec == 0 and any(k == 'tod' and s % 60 == 0 and (s // 60) % 12 == v % 12 for k, s, _, _ in src):
        return True                                   # "between 6 and 8 pm": the 6 is a clock hour given in the sources
    for k, s, _, _ in src:
        if kind != 'plain' and k != 'plain' and k != kind:
            continue
        if kind == 'money' and k == 'plain':
            continue
        if abs(s - v) <= tol:
            return True
    return False


def unsupported_figures(reply: str, sources: list[str]) -> list[str]:
    """The quantities in reply that no source supports (same kind of unit, within the reply's own rounding: 10.24 may be said as 10.2 or 10,
    never as 10.3). A bare number may match any kind. Number words are not checked here (the judge reads them)."""
    src = [q for s in sources for q in quantities(s)]
    src += [('plain', float(w), 0, '') for s in sources for w in _words(s)]
    bad = []
    for kind, v, dec, raw in quantities(reply):
        if kind == 'date':
            if not any(k == 'date' and s == v for k, s, _, _ in src):
                bad.append(raw)
            continue
        if not _match(kind, v, dec, src):
            bad.append(raw.strip())
    return bad


FIGURE_NUDGE = ("Your reply has figures that aren't in the readings, the energy cards, the person's words or an atlas_calc result: {figs}. "
                "Answer again, briefly: quote only figures you were given, and use atlas_calc for any sum you need.")


def _drop(reply: str, bad: list[str]) -> str:
    parts = re.split(r'(?<=[.!?])\s+', reply.strip())
    keep = [p for p in parts if not any(b and b in p for b in bad)]
    return ' '.join(keep).strip()


async def turn_figures(reply: str, sources: list[str], ask_model, tool_summaries=lambda: []) -> tuple[str, dict]:
    """Applied after core.guard_reply: (final reply, record). Unsupported figures -> one nudge -> re-check -> unsupported sentences dropped;
    if nothing is left, a plain line instead of a guess. tool_summaries() returns this turn's atlas_calc summaries (they are sources)."""
    rec = {'first_unsupported': unsupported_figures(reply, sources + tool_summaries()), 'nudged': False, 'dropped': []}
    if not rec['first_unsupported']:
        return reply, rec
    rec['nudged'] = True
    second = await ask_model(FIGURE_NUDGE.format(figs=', '.join(rec['first_unsupported'])))
    bad = unsupported_figures(second, sources + tool_summaries())
    rec['second_unsupported'] = bad
    if not bad:
        return second, rec
    kept = _drop(second, bad)
    rec['dropped'] = bad
    return (kept or "I can't give that figure reliably from what I have."), rec
