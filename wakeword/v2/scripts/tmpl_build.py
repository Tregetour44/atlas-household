"""Template building and splits shared by the LibriTTS-R (torch) and ONNX
synthesisers: v1's functions from synth.py, unchanged, plus build_templates_v2.
Needs only numpy and piper-tts's espeak phonemizer."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import templates as T  # noqa: E402  (v1)
import templates_v2 as T2  # noqa: E402

from piper.phonemize_espeak import EspeakPhonemizer  # noqa: E402

SPLITS = ("train", "validation", "test")
NUM_SPEAKERS = 800

def split_ids(ids, seed, fractions=(0.8, 0.1, 0.1)):
    """Deterministic 80/10/10 assignment of ids."""
    rng = np.random.default_rng(seed)
    ids = list(ids)
    order = rng.permutation(len(ids))
    n_train = int(round(fractions[0] * len(ids)))
    n_val = int(round(fractions[1] * len(ids)))
    out = {}
    for rank, idx in enumerate(order):
        out[ids[idx]] = (
            "train" if rank < n_train else "validation" if rank < n_train + n_val else "test"
        )
    return out


def stratified_split(items, seed):
    """items: list of (template_id, group). Split each group 80/10/10, at least
    one template per split when the group has three or more."""
    by_group = {}
    for tid, group in items:
        by_group.setdefault(group, []).append(tid)
    out = {}
    for gi, (group, tids) in enumerate(sorted(by_group.items())):
        rng = np.random.default_rng(seed + 1000 * gi)
        tids = [tids[i] for i in rng.permutation(len(tids))]
        n = len(tids)
        n_val = max(1, int(round(0.1 * n))) if n >= 3 else 0
        n_test = max(1, int(round(0.1 * n))) if n >= 3 else 0
        for i, tid in enumerate(tids):
            out[tid] = "validation" if i < n_val else "test" if i < n_val + n_test else "train"
    return out


def build_templates_v2(kind, phonemizer=None):
    """v1 templates (ids and splits as v1) plus the v2 families.
    Returns (templates, split by template id)."""
    rows = build_templates(kind)
    split_seed = 20261018
    if kind == "positive":
        tsplit = stratified_split([(t["template_id"], t["family"]) for t in rows], split_seed + 1)
    elif kind == "negative":
        texts = sorted({(t["text"], t["group"]) for t in rows})
        text_split = stratified_split(texts, split_seed + 2)
        tsplit = {t["template_id"]: text_split[t["text"]] for t in rows}
    else:
        tsplit = {}
    phonemizer = phonemizer or EspeakPhonemizer()
    new = []
    if kind == "positive":
        for fam, ph, sp in T2.v2_positive_ipa():
            new.append({"group": fam, "family": fam, "text": "Hey Atlas", "phonemes": ph, "split": sp})
        # extra espeak British voices and casual spellings: split by (voice, text) item
        items = [(v, t) for v in T2.POSITIVE_ESPEAK_V2 for t in T2.POSITIVE_TEXTS_V2]
        isplit = T2._split_items([f"{v}|{t}" for v, t in items], T2.NEW_SPLIT_SEED + 20)
        for v, t in items:
            ph = " ".join("".join(x) for x in phonemizer.phonemize(v, t))
            new.append({"group": f"espeak_{v}", "family": "gb2", "text": t, "phonemes": ph,
                        "split": isplit[f"{v}|{t}"]})
    else:
        for group, text, sp in T2.v2_negative_texts():
            for voice in T.HARD_NEGATIVE_VOICES:
                ph = " ".join("".join(x) for x in phonemizer.phonemize(voice, text))
                new.append({"group": group, "family": group, "text": text, "voice": voice,
                            "phonemes": ph, "split": sp})
    seen = {t["phonemes"] for t in rows}
    for i, r in enumerate(new):
        if r["phonemes"] in seen:
            continue
        seen.add(r["phonemes"])
        r["template_id"] = f"{kind[:3]}2_{i:04d}"
        tsplit[r["template_id"]] = r.pop("split")
        rows.append(r)
    return rows, tsplit


def build_templates(kind):
    """Returns list of dicts: template_id, group, phonemes (string)."""
    phonemizer = EspeakPhonemizer()
    rows = []
    if kind == "positive":
        seen = set()
        for voice in T.POSITIVE_ESPEAK_VOICES:
            for text in T.POSITIVE_TEXTS:
                ph = " ".join("".join(s) for s in phonemizer.phonemize(voice, text))
                if ph in seen:
                    continue
                seen.add(ph)
                rows.append({"group": f"espeak_{voice}", "text": text, "phonemes": ph})
        for group, ph in T.POSITIVE_IPA:
            if ph in seen:
                continue
            seen.add(ph)
            rows.append({"group": group, "text": "Hey Atlas", "phonemes": ph})
        # Families for stratification: au, us, gb, other
        for r in rows:
            g = r["group"]
            r["family"] = (
                "au" if g == "au"
                else "us" if g == "espeak_en-us"
                else "gb" if g in ("espeak_en", "espeak_en-gb-x-rp", "espeak_en-gb-scotland")
                else "other"
            )
    else:
        # Probes: every hard-negative text plus the probe-only confusables,
        # spoken by one split's voices, for per-phrase false-accept reports.
        source = T.HARD_NEGATIVES if kind == "negative" else T.HARD_NEGATIVES + T.PROBE_ONLY
        for group, text in source:
            assert kind == "probe" or not T.is_wake_phrase(text)
            for voice in T.HARD_NEGATIVE_VOICES:
                ph = " ".join("".join(s) for s in phonemizer.phonemize(voice, text))
                rows.append({"group": group, "family": group, "text": text,
                             "voice": voice, "phonemes": ph})
    for i, r in enumerate(rows):
        r["template_id"] = f"{kind[:3]}{i:03d}"
    return rows

