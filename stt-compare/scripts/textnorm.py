"""Text canonicalisation for scoring STT output against Atlas test commands.

canon(s): Whisper's English normaliser (numbers to digits, spelling, punctuation), then house-specific folding so that
equivalent written forms score the same: "10:15 p.m." = "ten fifteen p m" = "1015 pm"; "30%" = "thirty percent";
"kWh" = "kilowatt hours"; "Zero Charge" = "ZeroCharge"; "en suite" = "ensuite"; "goodnight" = "good night".
Used for both WER (reference and hypothesis) and the command slots, so the scoring never depends on formatting.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from english_normalizer import EnglishTextNormalizer  # noqa: E402  (OpenAI Whisper normaliser, Apache-2.0)

_N = EnglishTextNormalizer(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper_english_spelling.json"))))
_SMALL = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
          "ten": "10", "eleven": "11", "twelve": "12", "zero": "0"}
_FOLD = [  # applied after Whisper normalisation, in order
    (r"\bkilo ?watt ?hours?\b|\bk ?w ?h\b|\bkilowatt-hours?\b|\bkwhs\b", "kwh"),
    (r"\b(?:0|zero|xero) ?charges?\b|\bzerocharges?\b", "zerocharge"),
    (r"\ben ?suite\b|\bon ?suite\b|\bon sweet\b|\bensuites\b", "ensuite"),
    (r"\bgood ?night\b", "goodnight"),
    (r"\bwind-?down\b", "wind down"),
    (r"\bair ?con(?:ditioner|ditioning)?\b|\ba ?c\b", "ac"),
    (r"\bper ?cent\b|%", " percent"),
    (r"\bp ?m\b", "pm"),
    (r"\ba m\b", "am"),
    (r"\bo'?clock\b", ""),
    (r"\b(?:oh|o) (\d)\b", r"0\1"),          # "nine oh five" -> "9 05"
    (r"\bdown ?lights?\b", lambda m: m.group(0).replace(" ", "")),
    (r"\bspot ?lights?\b", lambda m: m.group(0).replace(" ", "")),
    (r"\bflood ?lights?\b", lambda m: m.group(0).replace(" ", "")),
    (r"\bok\b|\bokay\b", "ok"),
    (r"\bmum\b", "mom"),
    (r"\bt v\b", "tv"),
    (r"\bu v\b", "uv"),
]


def canon(s: str) -> str:
    s = s.replace("+", " plus ").replace("&", " and ")
    s = re.sub(r"(\d)\s*([ap])\.?\s?m\b\.?", r"\1 \2m", s, flags=re.I)        # 1pm -> 1 pm before Whisper's normaliser
    s = re.sub(r"\b(\d{1,2}):(\d\d)\b", r"\1\2", s)                         # 10:15 -> 1015
    s = re.sub(r"\b(\d{1,2})\.(\d\d)(?= ?[ap]m\b)", r"\1\2", s)              # 7.30 pm -> 730 pm
    s = re.sub(r"\b(what|how|where|who|that|it)s\b", r"\1 is", s, flags=re.I)    # typed "whats" = "what's"
    s = _N(s)
    s = re.sub(r"\b(" + "|".join(_SMALL) + r")(?=\.\d)", lambda m: _SMALL[m.group(1)], s)   # Whisper's normaliser: "1.2" -> "one.2"
    for pat, rep in _FOLD:
        s = re.sub(pat, rep, s)
    s = " ".join(_SMALL.get(w, w) for w in s.split())
    s = re.sub(r"\b(\d{1,2}) (0\d|[1-5]\d)\b(?= ?(?:pm|am|tonight|tomorrow|$))", r"\1\2", s)   # "10 15 pm" -> "1015 pm"
    s = re.sub(r"\b(\d{1,2}) (0\d|[1-5]\d)\b", r"\1\2", s) if re.search(r"\bat \d{1,2} \d\d\b", s) else s
    s = re.sub(r"\b(\d+) percent\b", r"\1 percent", s)
    return re.sub(r"\s+", " ", s).strip()


def slot_form(s: str) -> str:
    """Looser form for command slots: singular/plural and filler words don't change the action."""
    s = canon(s)
    s = re.sub(r"\b(light|lamp|blind|downlight|spotlight|floodlight|pendant|chandelier|timer|minute|hour)s\b", r"\1", s)
    s = re.sub(r"\b(the|a|an|please|can|you|could|would)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slot_hit(slot: str, hyp_slot_form: str) -> bool:
    """slot: 'a|b' alternatives; each alternative must appear as whole words in the hypothesis (slot form)."""
    for alt in slot.split("|"):
        a = slot_form(alt)
        if a and re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w])", hyp_slot_form):
            return True
    return False


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(repr(t), "->", repr(canon(t)), "|", repr(slot_form(t)))
