"""Round 2: this house's device/room names in Atlas's real reply shapes (owner-supplied; values made up).
Writes variations so every training name appears at least twice in different shapes; the eight held-out names
(heldout_r3/house_heldout.txt) never appear. Deterministic, seed 20261021."""
import random, sys
from gen_numbers import words

NAMES = """atrium; atrium blind; atrium spotlight left; atrium spotlight right; dining room; dining room lamp; dining room pendant; ensuite downlight; fountain spotlight; garage; garage ceiling left; garage ceiling right; garden spotlight; guest bedroom; guest bedroom ceiling; guest bedroom lamp; hallway; hallway downlight; hallway downlight back; hallway downlight front; kitchen; kitchen ceiling; kitchen chandelier one; kitchen chandelier two; kitchen chandelier three; kitchen downlight left; kitchen downlight right; laundry; laundry downlight; living room; living room chandelier one; living room chandelier two; living room chandelier three; living room chandelier four; living room chandelier five; living room chandelier six; living room door blind; living room downlight back; living room downlight front; living room lamp; living room window blind; loft; loft downlight left; loft downlight middle; loft downlight right; loft lamp; master bedroom; master bedroom ceiling; master bedroom lamp; mirror ambiance; patio; pergola floodlight one; pergola floodlight two; pergola floodlight three; pergola spotlight one; pergola spotlight two; pergola spotlight three; porch; porch downlight one; porch downlight two; porch downlight three; porch downlight four; range hood one; range hood two; robe downlight; study; study ceiling; wall floodlight; wall light; lounge; upstairs; downstairs; ground floor; outside; living room lights; porch lights; patio lights; kitchen lights; loft lights; study lights; garage lights; laundry lights; hallway lights; atrium lights; dining room lights; guest bedroom lights; master bedroom lights; living room blinds""".split("; ")
HELD = {"fountain spotlight", "mirror ambiance", "robe downlight", "ensuite downlight", "wall floodlight", "wall light",
        "pergola floodlight three", "living room chandelier six"}
AREAS = {"atrium", "dining room", "garage", "guest bedroom", "hallway", "kitchen", "laundry", "living room", "loft",
         "master bedroom", "patio", "porch", "study", "lounge", "upstairs", "downstairs", "ground floor", "outside"}
names = [n for n in NAMES if n not in HELD]
areas = [n for n in names if n in AREAS]
devices = [n for n in names if n not in AREAS]
blinds = [n for n in devices if "blind" in n]
dimmable = [n for n in devices if "blind" not in n and "range hood" not in n]
plural = lambda n: n.endswith("lights") or n.endswith("blinds")
title = lambda n: " ".join(w.capitalize() for w in n.split())
cap = lambda s: s[0].upper() + s[1:]
pct = lambda: words(random.choice(range(10, 100, 5)))


def clock(ap=True):
    h, m = random.randint(1, 12), random.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
    t = words(h) + ("" if m == 0 else (" oh " + words(m) if m < 10 else " " + words(m)))
    return t + (" " + random.choice(["p m", "a m"]) if ap else "")


def onoff():
    return random.choice(["on", "off"])


DEV = [  # shapes taking one device (or device group)
    lambda n: f"Done: {cap(n) if random.random() < .5 else title(n)} {onoff()}. Checked.",
    lambda n: f"Done: {title(n)} on at {pct()} percent. Checked." if n in dimmable else f"Done: {title(n)} {random.choice(['open', 'closed'])}. Checked.",
    lambda n: f"I've turned the {n} {onoff()} for you.",
    lambda n: f"I have turned the {n} on at {pct()} percent." if n in dimmable else f"I've closed the {n} for you.",
    lambda n: f"I've {random.choice(['dimmed', 'brightened'])} the {n} to {pct()} percent." if n in dimmable else f"I've opened the {n} halfway.",
    lambda n: f"Timer set: {title(n)} {onoff()} at {clock()}. Say \"cancel that\" to stop it.",
    lambda n: f"Timer set: {cap(n)} {onoff()} in {words(random.choice([5, 10, 15, 20, 25, 30, 45]))} minutes. Say \"cancel that\" to stop it.",
    lambda n: f"Cancelled: the {n} timer.",
    lambda n: f"The {n} {'are' if plural(n) else 'is'} already {onoff()}. I didn't change anything.",
    lambda n: f"{title(n)} {'are' if plural(n) else 'is'} already on at {pct()} percent. I didn't change anything." if n in dimmable else f"The {n} {'are' if plural(n) else 'is'} already closed. I didn't change anything.",
    lambda n: f"What time would you like the {n} turned {onoff()}?",
    lambda n: f"The {n} at {pct()} percent?" if n in dimmable else f"Close the {n} at {clock()}?",
    lambda n: f"How bright would you like the {n}, as a percentage?" if n in dimmable else f"Open the {n} at {clock()} tomorrow?",
    lambda n: f"You have one timer: the {n} {'go' if plural(n) else 'goes'} {onoff()} at {clock()}.",
    lambda n: f"The {n} {'are' if plural(n) else 'is'} now at full brightness." if n in dimmable else f"The {n} {'are' if plural(n) else 'is'} now fully open.",
    lambda n: f"{cap(n)} {onoff()}. " + random.choice(["Do mind the stairs.", "Nothing else has changed.", "As requested.", "That should do nicely.", "I'll leave the rest as they are."]),
]
AREA = [  # shapes taking a room/area
    lambda a: f"It's {words(random.randint(14, 27))} point {words(random.randint(0, 9))} degrees in the {a}." if a not in ("outside", "upstairs", "downstairs") else f"It's {words(random.randint(5, 30))} degrees {a}.",
    lambda a: f"Done: {cap(a)} lights {onoff()}, {words(k := random.randint(1, 4))} of {words(k + (j := random.randint(1, 4)))} changed; the other {words(j)} already were. Checked.",
    lambda a: f"Which lights in the {a} do you mean?" if a not in ("outside", "upstairs", "downstairs") else f"Which lights {a} do you mean?",
    lambda a: f"Nobody's been in the {a} for an hour, so I've turned the lights off." if a not in ("outside", "upstairs", "downstairs") else f"Nobody's been {a} for an hour, so I've turned the lights off.",
    lambda a: f"Timer set: {title(a)} lights off at {clock()}. Say \"cancel that\" to stop it.",
]


def main():
    random.seed(20261021)
    out, count = [], {n: 0 for n in names}
    for rnd in range(2):  # every name twice, with different shapes
        for n in names:
            pool = DEV if n in devices else AREA
            used = {s for s in out}
            for _ in range(20):
                s = random.choice(pool)(n)
                if s not in used:
                    break
            out.append(s)
    # mixed pairs: which-of-two questions and combined replies
    for _ in range(40):
        a, b = random.sample(dimmable, 2)
        out.append(random.choice([
            f"Did you mean the {a}, or the {b}?",
            f"I've turned the {a} {onoff()} and the {b} {onoff()}.",
            f"Done: {title(a)} and {title(b)} off. Checked.",
            f"The {a} is on, but the {b} is already off.",
        ]))
    for _ in range(12):
        a, b = random.sample([x for x in areas if x not in ("outside", "upstairs", "downstairs", "ground floor")], 2)
        out.append(f"Which room do you mean, the {a} or the {b}?")
    # energy shapes with new values
    for _ in range(20):
        out.append(random.choice([
            f"The home battery is at {words(random.randint(10, 99))} point {words(random.randint(0, 9))} percent.",
            f"Solar is making {words(random.choice(range(150, 6000, 50)))} watts right now.",
            f"The house is using {words(random.choice(range(200, 4000, 10)))} watts, and you're {random.choice(['selling', 'buying'])} {words(random.randint(0, 4))} point {words(random.randint(1, 9))} kilowatts {random.choice(['to', 'from'])} the grid.",
            f"You've made {words(random.randint(1, 35))} point {words(random.randint(0, 9))} kilowatt hours of solar today.",
            f"If the sun holds, the battery should be full by about {words(random.randint(10, 12)) if False else words(random.randint(1, 4))} p m.",
        ]))
    import os
    corpus = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "corpus")
    fixed = {l.strip() for f in ("train_ext4/house_given.txt", "heldout_r3/house_heldout.txt")
             for l in open(os.path.join(corpus, f), encoding="utf-8") if l.strip() and not l.startswith("#")}
    seen, uniq = set(fixed), []
    for s in out:
        if s not in seen and not any(h in s.lower() for h in HELD):
            seen.add(s); uniq.append(s)
    low = [n for n in names if sum((" " + n + " ") in (" " + s.lower().replace(".", " ").replace(",", " ").replace("?", " ") + " ") for s in uniq) < 2]
    print("# Round 2: house names in Atlas reply shapes (scripts/gen_house.py, seed 20261021).")
    print("\n".join(uniq))
    if low:
        print("names used fewer than twice:", low, file=sys.stderr)


if __name__ == "__main__":
    main()
