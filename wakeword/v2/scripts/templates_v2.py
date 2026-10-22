"""v2 templates: v1's templates and splits unchanged, plus new families.

v1's positive templates, hard-negative texts and their splits are rebuilt
exactly as v1 made them (templates.py, same seeds), so v1's validation and
test templates stay out of v2 training. New templates are split separately
(their own seed), 80/10/10 by template (positives) or by text frame
(hard negatives), so a frame such as "ask Atlas about {x}" sits in one split.
"""
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import templates as T  # noqa: E402  (v1)

NEW_SPLIT_SEED = 20261022

# ---------------------------------------------------------------- positives
# Hand-written IPA (espeak-ng has no en-AU or en-NZ voice). Australian: [æɪ]/[ɐɪ]/[æe] in
# "hey", [ɐ]/[ə]/[ɪ] in "-las", glottal or unreleased t. New Zealand: raised [ɛ] in
# "At-", centralised [ɘ] in "-las". Casual: unstressed or fast "hey", [hɛ].
POSITIVE_IPA_V2 = [
    ("au2", "hˈæɪ ˈætlɐs"), ("au2", "hæɪ ˈætləs"), ("au2", "hˈæɪ ˈæʔlɐs"),
    ("au2", "hˈɐɪ ˈætləs"), ("au2", "hˈæɪ, ˈætlɐs"), ("au2", "hˈæe ˈætlɐs"),
    ("au2", "hɐɪ ˈæʔləs"), ("au2", "hˈæɪ ˈɛtlɐs!"), ("au2", "hˈæːɪ ˈætləs"),
    ("au2", "hæe, ˈætlɐs"), ("au2", "hˈɐɪ ˈætlɪs."), ("au2", "hˈæɪ ˈætˌlɐs"),
    ("au2", "hæɪ ˈætlɐs?"), ("au2", "hˈɐe ˈætləs"), ("au2", "hˈæɪ, ˈæʔlɐs!"),
    ("nz", "hˈæe ˈɛtləs"), ("nz", "hˈæɪ ˈɛtlɘs"), ("nz", "hˈɐe ˈɛtlɘs"),
    ("nz", "hæe, ˈɛtləs"), ("nz", "hˈæɪ ˈɛʔlɘs"), ("nz", "hˈæe ˈɛtlɘs?"),
    ("casual", "hɛ ˈætləs"), ("casual", "heɪ ˈætləs"), ("casual", "hˌeɪ ˈætlɪs"),
    ("casual", "hɛɪ ˈatləs"), ("casual", "heɪ, ˈætləs"), ("casual", "hɛ, ˈætlɐs"),
]
# espeak-ng British voices v1 did not use (Lancashire, West Midlands, northern)
POSITIVE_ESPEAK_V2 = ["en-gb-x-gbclan", "en-gb-x-gbcwmd", "en-gb-x-rp"]
POSITIVE_TEXTS_V2 = ["hey atlas", "hey, atlas", "Hey Atlas...", "Hey... Atlas"]

# ---------------------------------------------------------------- hard negatives
# "Atlas" in the middle of a sentence: frames x fillers, about 2,000 sentences.
_TOPICS = ["the weather", "the footy", "dinner", "the bins", "tomorrow", "the time",
           "the traffic", "the forecast", "the cricket score", "the shopping list",
           "the news", "our flights", "the bus times", "the recipe", "the power bill",
           "the train", "school pick-up", "the dentist", "the movie", "the tides",
           "the barbecue", "the long weekend", "the rugby", "the electricity", "the garden",
           "the surf report", "the speed limit", "the solar panels", "the meeting", "the camping trip"]
_REQS = ["to turn off the lights", "to play some music", "to set a timer", "to call Mum",
         "what time it is", "if it's going to rain", "to dim the lounge lights",
         "to add milk to the list", "to turn the heater on", "to lock the front door",
         "for the weather", "to remind me later", "to open the blinds", "how hot it is",
         "to turn the telly down", "to start the vacuum", "what's on tonight",
         "to set an alarm for six", "to switch the fan off", "to read the news",
         "to turn the aircon up", "to put the kettle on", "to find my phone", "to stop the music",
         "what's for tea"]
_FACTS = ["it's going to rain", "the bins go out tonight", "dinner's at seven",
          "the bus is late", "it'll be thirty degrees", "the game starts at eight",
          "the shop shuts at five", "it's cold outside", "we're out of milk",
          "the train's cancelled", "there's a storm coming", "the parcel arrived",
          "the oven's still on", "it's nearly midnight", "the kids are asleep"]
_PLACES = ["shelf", "table", "bookcase", "coffee table", "kitchen bench", "desk",
           "floor", "couch", "windowsill", "top shelf"]
_PEOPLE = ["Mum", "Dad", "Sam", "Jess", "Nan", "Tom", "Chloe", "Liam", "the kids", "Grandpa"]
_ACTS = ["turn the lights off", "lock the door", "set the alarm", "play that song",
         "turn the heater off", "close the blinds", "start the dishwasher",
         "turn the volume down", "remind us", "order more coffee"]
_ACTS_PAST = ["turned the lights off", "locked the door", "set the alarm",
              "played that song", "switched the heater off", "closed the blinds",
              "started the dishwasher", "turned the music down", "reminded us",
              "got it wrong again"]
FRAMES = [
    ("ask Atlas about {topic}", "topic"), ("can you ask Atlas about {topic}", "topic"),
    ("I asked Atlas about {topic}", "topic"), ("just ask Atlas about {topic}", "topic"),
    ("can you ask Atlas {req}", "req"), ("I'll ask Atlas {req}", "req"),
    ("tell Atlas {req}", "req"), ("we could ask Atlas {req}", "req"),
    ("Atlas said {fact}", "fact"), ("Atlas says {fact}", "fact"),
    ("Atlas reckons {fact}", "fact"), ("according to Atlas, {fact}", "fact"),
    ("apparently Atlas thinks {fact}", "fact"), ("well, Atlas told me {fact}", "fact"),
    ("the atlas on the {place}", "place"), ("put the atlas back on the {place}", "place"),
    ("the old atlas is on the {place}", "place"), ("have you seen the atlas on the {place}", "place"),
    ("there's an atlas on the {place}", "place"), ("grab the road atlas off the {place}", "place"),
    ("{person} asked Atlas {req}", "person_req"), ("{person} told Atlas to {act}", "person_act"),
    ("did Atlas {act}", "act"), ("can Atlas {act}", "act"), ("I think Atlas {act_past}", "act_past"),
    ("has Atlas {act_past}", "act_past"), ("Atlas already {act_past}", "act_past"),
    ("I don't think Atlas {act_past}", "act_past"), ("so Atlas {act_past}", "act_past"),
    ("hey, did Atlas {act}", "act"), ("hey, can you ask Atlas {req}", "req"),
    ("Atlas, {act}", "act"), ("okay Atlas, {act}", "act"), ("right, Atlas will {act}", "act"),
    ("is Atlas listening to {topic}", "topic"), ("Atlas knows about {topic}", "topic"),
    ("look up {topic} in the atlas", "topic"), ("what did Atlas say about {topic}", "topic"),
    ("why does Atlas keep talking about {topic}", "topic"), ("Atlas was wrong about {topic}", "topic"),
    ("{person} asked Atlas about {topic}", "person_topic"),
    ("{person} said Atlas {act_past}", "person_act_past"),
    ("did Atlas tell {person} {fact}", "person_fact"),
    ("ask Atlas {req} for {person}", "person_req"),
    ("{person}'s atlas is on the {place}", "person_place"),
    ("when Atlas {act_past}, {person} laughed", "person_act_past"),
    ("I told Atlas {fact}", "fact"),
]


def _fill(frame, kind):
    if kind == "topic":
        return [frame.format(topic=x) for x in _TOPICS]
    if kind == "req":
        return [frame.format(req=x) for x in _REQS]
    if kind == "fact":
        return [frame.format(fact=x) for x in _FACTS]
    if kind == "place":
        return [frame.format(place=x) for x in _PLACES]
    if kind == "act":
        return [frame.format(act=x) for x in _ACTS]
    if kind == "act_past":
        return [frame.format(act_past=x) for x in _ACTS_PAST]
    if kind == "person_req":
        return [frame.format(person=p, req=r) for p, r in itertools.product(_PEOPLE, _REQS)]
    if kind == "person_act":
        return [frame.format(person=p, act=a) for p, a in itertools.product(_PEOPLE, _ACTS)]
    if kind == "person_topic":
        return [frame.format(person=p, topic=x) for p, x in itertools.product(_PEOPLE, _TOPICS)]
    if kind == "person_act_past":
        return [frame.format(person=p, act_past=a) for p, a in itertools.product(_PEOPLE, _ACTS_PAST)]
    if kind == "person_fact":
        return [frame.format(person=p, fact=f) for p, f in itertools.product(_PEOPLE, _FACTS)]
    if kind == "person_place":
        return [frame.format(person=p, place=x) for p, x in itertools.product(_PEOPLE, _PLACES)]
    raise ValueError(kind)


def mid_sentence_texts():
    """[(frame_id, text)], about 2,000 sentences, 'Atlas' never right after 'hey'."""
    out = []
    for fi, (frame, kind) in enumerate(FRAMES):
        for text in _fill(frame, kind):
            assert not T.is_wake_phrase(text), text
            out.append((f"f{fi:02d}", text))
    return out


# The v1 weak spots, many variants each (texts new in v2; v1's own texts keep v1's split)
CONFUSABLES_V2 = [
    ("hi_atlas", t) for t in ["hi Atlas", "hi, Atlas", "hi Atlas!", "hi Atlas?", "hiya Atlas",
                              "oh hi Atlas", "hi Atlas, how are you", "hi there Atlas",
                              "hi Atlas, good morning", "hi again Atlas"]
] + [
    ("pay_atlas", t) for t in ["pay Atlas", "I'll pay Atlas", "pay Atlas back", "pay Atlas later",
                               "pay, Atlas", "did you pay Atlas", "pay Atlas tomorrow",
                               "we have to pay Atlas", "pay the Atlas invoice"]
] + [
    ("hey_alice", t) for t in ["hey Alice, dinner's ready", "hey Alice, where are you",
                               "hey Alice?", "oh hey Alice", "hey Alice, come and look",
                               "hey Alice, good morning", "hey, Alice!"]
] + [
    ("hey_alex", t) for t in ["hey Alex, dinner's ready", "hey Alex, where are you", "hey Alex?",
                              "oh hey Alex", "hey Alex, come and look", "hey Alex, good morning",
                              "hey, Alex!", "hey Alexis"]
] + [
    ("at_last", t) for t in ["at last, it's Friday", "oh at last", "at last you're home",
                             "finally, at last", "at last the rain stopped", "home at last!",
                             "we're here at last", "at last, some sun"]
]

V2_GROUPS = ["mid_atlas", "hi_atlas", "pay_atlas", "hey_alice", "hey_alex", "at_last"]


def _split_items(keys, seed):
    keys = sorted(set(keys))
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(keys))
    n = len(keys)
    n_val = max(1, int(round(0.1 * n)))
    n_test = max(1, int(round(0.1 * n)))
    out = {}
    for rank, i in enumerate(order):
        out[keys[i]] = "validation" if rank < n_val else "test" if rank < n_val + n_test else "train"
    return out


def v2_negative_texts():
    """[(group, text, split)] for the new v2 hard negatives."""
    rows = []
    mids = mid_sentence_texts()
    fsplit = _split_items([f for f, _ in mids], NEW_SPLIT_SEED)
    rows += [("mid_atlas", t, fsplit[f]) for f, t in mids]
    for gi, g in enumerate(V2_GROUPS[1:]):
        texts = [t for gg, t in CONFUSABLES_V2 if gg == g]
        s = _split_items(texts, NEW_SPLIT_SEED + 1 + gi)
        rows += [(g, t, s[t]) for t in texts]
    for _, t, _ in rows:
        assert not T.is_wake_phrase(t), t
    return rows


def v2_positive_ipa():
    """[(family, phonemes, split)] for the new hand-written positives."""
    rows = []
    for fi, fam in enumerate(["au2", "nz", "casual"]):
        phs = [p for f, p in POSITIVE_IPA_V2 if f == fam]
        s = _split_items(phs, NEW_SPLIT_SEED + 10 + fi)
        rows += [(fam, p, s[p]) for p in phs]
    return rows


if __name__ == "__main__":
    import collections
    neg = v2_negative_texts()
    print("new negatives:", len(neg), collections.Counter((g, s) for g, _, s in neg))
    print("new positive IPA:", collections.Counter((f, s) for f, _, s in v2_positive_ipa()))
