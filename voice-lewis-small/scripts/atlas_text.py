"""Spoken-form text normaliser for Atlas -> Piper. espeak-ng reads most digits well ("80%" -> "eighty percent") but
not clock times with minutes under ten, money or units, and the voice was trained on spoken-form text, so we
expand those first. Pure Python, no dependencies."""
import re

_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num(n: int) -> str:
    if n < 0:
        return "minus " + num(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    if n < 1000:
        r = n % 100
        return _ONES[n // 100] + " hundred" + ("" if r == 0 else " and " + num(r))
    if n < 1_000_000:
        t, r = divmod(n, 1000)
        return num(t) + " thousand" + ("" if r == 0 else (" and " if r < 100 else " ") + num(r))
    return str(n)


def _time(m):
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower().replace(".", "")
    hw = num(h % 12 or 12) if ap or h > 12 else num(h)
    s = hw + (" o'clock" if mi == 0 and not ap else "" if mi == 0 else (" oh " + num(mi) if mi < 10 else " " + num(mi)))
    raw = m.group(3) or ""
    return s + {"am": " a m", "pm": " p m"}.get(ap, "") + ("." if raw.endswith(".") else "")  # keep a sentence-final full stop


def _money(m):
    d, c = int(m.group(1).replace(",", "")), m.group(2)
    s = num(d) + (" dollar" if d == 1 else " dollars")
    if c and int(c):
        s += " and " + num(int(c)) + (" cent" if int(c) == 1 else " cents")
    return s


def _dec(m):
    return num(int(m.group(1))) + " point " + " ".join(_ONES[int(d)] for d in m.group(2))


RULES = [
    (re.compile(r"\b(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?(?![\w:])", re.I), _time),
    (re.compile(r"\$(\d[\d,]*)(?:\.(\d{2}))?\b"), _money),
    (re.compile(r"(-?\d+(?:\.\d+)?)\s*°\s*C\b"), lambda m: m.group(1) + " degrees"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*kWh\b"), lambda m: m.group(1) + " kilowatt hours"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*kW\b"), lambda m: m.group(1) + " kilowatts"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*km/h\b"), lambda m: m.group(1) + " kilometres an hour"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*km\b"), lambda m: m.group(1) + " kilometres"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*mm\b"), lambda m: m.group(1) + " millimetres"),
    (re.compile(r"(\d+)\s*%"), lambda m: m.group(1) + " percent"),
    (re.compile(r"(?<![\d.])-(\d+)"), lambda m: "minus " + m.group(1)),
    (re.compile(r"\b(\d+)\.(\d+)\b"), _dec),
    (re.compile(r"\b\d+\b"), lambda m: num(int(m.group(0)))),
]


def normalise(text: str) -> str:
    for rx, fn in RULES:
        text = rx.sub(fn, text)
    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    for t in ["Battery at 80%, solar's done.", "It's 6:05 pm.", "Dryer at 20:30.", "That's $12.50, or $1.", "It's 21.5°C, low of -3°C.",
              "Used 18.5 kWh; car has 340 km.", "Gusts to 45 km/h, 14 mm of rain.", "Study lights off in 10 minutes.", "It's 7:00."]:
        print(f"{t!r:45} -> {normalise(t)}")
