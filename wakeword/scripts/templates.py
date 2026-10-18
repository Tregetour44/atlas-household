"""Text and phoneme templates for "Hey Atlas" positives and hard negatives.

Every template has a stable id and a group. Splits are made per template
(stratified by group) and per voice, before any augmentation.

Positives are given as phoneme strings, because espeak-ng has no en-AU voice:
the Australian-sounding variants are hand-written IPA (the [hæɪ] "hey", a
schwa or [ɪ] in "-las", a glottal "t"). The other variants come from
espeak-ng's own English voices, phonemized once at synthesis time.
"""

# (template_id, family, espeak voice or None, text or IPA phonemes)
# When the voice is None, the string is already phonemes.
POSITIVE_TEXTS = [
    "Hey Atlas",
    "Hey, Atlas",
    "Hey Atlas!",
    "Hey Atlas.",
    "Hey, Atlas?",
]
POSITIVE_ESPEAK_VOICES = ["en-us", "en", "en-gb-x-rp", "en-gb-scotland", "en-029"]

POSITIVE_IPA = [
    # Australian-sounding variants
    ("au", "hˈæɪ ˈætləs"),
    ("au", "hˈæɪ, ˈætləs"),
    ("au", "hˈæɪ ˈætləs!"),
    ("au", "hˈɐɪ ˈætlɐs"),
    ("au", "hˈæɪ ˈɛtləs"),
    ("au", "hˈæɪ ˈætlɪs"),
    ("au", "hˈæɪ ˈæʔləs"),
    ("au", "hˈæe ˈætləs."),
    ("au", "hˈɐɪ, ˈɛtlɪs"),
    ("au", "hˈæɪ ˈætlɐs?"),
    # Other hand-written variants (stress and vowel spread)
    ("misc", "hˌeɪ ˈætləs"),
    ("misc", "hˈeɪ ˈætlɪs"),
    ("misc", "hˈeɪ ˈatlɐs"),
    ("misc", "hˈɛɪ ˈætləs"),
]

# Hard negatives: (group, text). Never the exact wake phrase "Hey Atlas"
# (with or without punctuation); check_negatives() enforces that.
HARD_NEGATIVES = [
    # "Atlas" without "hey"
    ("atlas", "Atlas"), ("atlas", "Atlas."), ("atlas", "Atlas?"),
    ("atlas", "an atlas"), ("atlas", "the atlas"), ("atlas", "my atlas"),
    ("atlas", "a road atlas"), ("atlas", "the world atlas"),
    ("atlas", "open the atlas"), ("atlas", "where's the atlas"),
    ("atlas", "I bought an atlas"), ("atlas", "check the atlas"),
    ("atlas", "Atlas was a titan"), ("atlas", "the atlas is on the shelf"),
    ("atlas", "pass me that atlas"), ("atlas", "an old atlas of Europe"),
    ("atlas", "the Atlas Mountains"), ("atlas", "okay Atlas"),
    ("atlas", "say Atlas"), ("atlas", "they atlas"),
    ("ask_atlas", "ask Atlas tomorrow"), ("ask_atlas", "ask Atlas"),
    ("ask_atlas", "tell Atlas"), ("ask_atlas", "I'll ask Atlas tomorrow"),
    ("ask_atlas", "we can ask Atlas later"), ("ask_atlas", "ask Atlas about it"),
    ("rocket", "the Atlas rocket"), ("rocket", "an Atlas rocket launch"),
    ("rocket", "the Atlas five rocket"), ("rocket", "Atlas V lifted off"),
    ("rocket", "watch the Atlas rocket"), ("rocket", "the Atlas rocket is ready"),
    ("at_last", "at last"), ("at_last", "at last!"), ("at_last", "free at last"),
    ("at_last", "home at last"), ("at_last", "at last we're done"),
    ("at_last", "at long last"), ("at_last", "at last it's here"),
    ("at_last", "and at last"), ("at_last", "that last"), ("at_last", "add less"),
    # "hey" + another name
    ("hey_name", "hey Alice"), ("hey_name", "hey Alice!"), ("hey_name", "hey, Alice"),
    ("hey_name", "hey Alex"), ("hey_name", "hey Alex!"), ("hey_name", "hey, Alex"),
    ("hey_name", "hey Alexa"), ("hey_name", "hey Alexa!"), ("hey_name", "hey, Alexa"),
    ("hey_name", "hey Jarvis"), ("hey_name", "hey Jarvis!"), ("hey_name", "hey, Jarvis"),
    ("hey_name", "hey Alexa, turn on the lights"), ("hey_name", "hey Alice, come here"),
    ("hey_name", "hey Alex, what's up"), ("hey_name", "hey Jarvis, what's the time"),
    ("hey_name", "hey Alan"), ("hey_name", "hey Ellis"), ("hey_name", "hey Alison"),
    ("hey_name", "hey Atlanta"), ("hey_name", "hey Atlantis"), ("hey_name", "hey Athena"),
    ("hey_name", "hey Atticus"), ("hey_name", "hey Adam"), ("hey_name", "hey Alfie"),
    ("hey_name", "hey Annabel"), ("hey_name", "hey Alessa"), ("hey_name", "hey Matilda"),
    ("hey_name", "hey Siri"), ("hey_name", "hey Google"), ("hey_name", "hey Mycroft"),
    ("hey_name", "hey Callum"), ("hey_name", "hey Dallas"), ("hey_name", "hey Talia"),
    ("okay_nabu", "okay Nabu"), ("okay_nabu", "okay Nabu!"), ("okay_nabu", "okay, Nabu"),
    ("okay_nabu", "okay Nabu, turn off the kitchen lights"), ("okay_nabu", "ok Nabu"),
    # "hey" with no "Atlas"
    ("hey", "hey"), ("hey", "hey!"), ("hey", "hey."), ("hey", "hey there"),
    ("hey", "hey you"), ("hey", "hey, what's up"), ("hey", "hey, look at this"),
    ("hey", "hey mate"), ("hey", "hey guys"), ("hey", "hey, hello"), ("hey", "oh hey"),
    ("hey", "hey, how are you"), ("hey", "hey hey"), ("hey", "hey, at the shops"),
    ("hey", "hey, that's lovely"), ("hey", "hey, I'm home"), ("hey", "hey, listen"),
    ("hey", "hey, thanks"), ("hey", "hey, last one"), ("hey", "hey, have a look"),
    # Other near sounds
    ("other", "a tassel"), ("other", "hat lace"), ("other", "Atlassian"),
    ("other", "battle us"), ("other", "Dallas"), ("other", "atlases"),
    ("other", "at least"), ("other", "a cutlass"), ("other", "the lattice"),
    ("other", "haystack"), ("other", "eight lasses"), ("other", "hate less"),
]
HARD_NEGATIVE_VOICES = ["en-us", "en", "en-gb-x-rp", "en-029"]

# Probe-only confusables: used to report false accepts per phrase on test
# voices, never trained on. "hey, at last" sounds very close to the wake
# phrase, so it is measured rather than taught.
PROBE_ONLY = [
    ("probe", "hey, at last"), ("probe", "hey at last"), ("probe", "hi Atlas"),
    ("probe", "they had less"), ("probe", "hey Alice and Atlas"),
]


def _norm(text):
    return "".join(c for c in text.lower() if c.isalpha() or c == " ").split()


def is_wake_phrase(text):
    """True if the text contains the words "hey atlas" in a row."""
    words = _norm(text)
    return any(a == "hey" and b == "atlas" for a, b in zip(words, words[1:]))


def check_negatives():
    for _, text in HARD_NEGATIVES:
        assert not is_wake_phrase(text), text


check_negatives()
