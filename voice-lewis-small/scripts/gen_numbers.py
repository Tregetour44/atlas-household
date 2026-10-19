"""Generate the templated spoken-number family (train/numbers_generated.txt), deterministic (seed 20261019).
Numbers are written as words so the teacher's audio and the Piper transcript agree exactly."""
import random, sys

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " and " + words(rest))
    th, rest = divmod(n, 1000)
    return words(th) + " thousand" + ("" if rest == 0 else (" and " if rest < 100 else " ") + words(rest))


def clock(h, m):
    hw = words(h)
    if m == 0:
        return random.choice([f"{hw} o'clock", hw])
    if m == 15:
        return f"a quarter past {hw}"
    if m == 30:
        return random.choice([f"half past {hw}", f"{hw} thirty"])
    if m == 45:
        return f"a quarter to {words(h % 12 + 1)}"
    if m < 10:
        return f"{hw} oh {words(m)}"
    return f"{hw} {words(m)}"


ROOMS = ["the lounge", "the study", "the kitchen", "the main bedroom", "the kids' room", "the laundry", "the spare room", "the garage"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ORD = "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split()
MONTHS = "January February March April May June July August September October November December".split()


def ordinal(d):
    if d <= 20:
        return ORD[d - 1]
    t, o = divmod(d, 10)
    return ("twenty" if t == 2 else "thirty") + ("" if o == 0 else "-" + ORD[o - 1]) if o else ("twentieth" if t == 2 else "thirtieth")


T = [
    lambda: f"The battery is at {words(random.randint(5, 99))} percent.",
    lambda: f"Solar is producing {words(random.randint(1, 9))} point {words(random.randint(0, 9))} kilowatts right now.",
    lambda: f"It's {words(random.randint(12, 31))} degrees in {random.choice(ROOMS)}.",
    lambda: f"Outside it's {words(random.randint(3, 42))} degrees, with {words(random.randint(20, 95))} percent humidity.",
    lambda: f"It's {clock(random.randint(1, 12), random.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 7, 3]))}.",
    lambda: f"The timer has {words(random.randint(2, 59))} minutes left.",
    lambda: f"The dishwasher will finish at {clock(random.randint(1, 12), random.choice([0, 10, 15, 20, 30, 40, 45, 50]))}.",
    lambda: f"Power costs {words(random.randint(8, 65))} cents a kilowatt hour at the moment.",
    lambda: f"Today the house used {words(random.randint(6, 40))} kilowatt hours, and the panels made {words(random.randint(4, 45))}.",
    lambda: f"The car is at {words(random.randint(10, 100))} percent, with about {words(random.choice(range(40, 460, 10)))} kilometres of range.",
    lambda: f"That comes to {words(random.randint(2, 480))} dollars and {words(random.choice(range(5, 100, 5)))} cents.",
    lambda: f"There's a {words(random.choice(range(10, 100, 10)))} percent chance of rain on {random.choice(DAYS)}.",
    lambda: f"The appointment is on {random.choice(DAYS)} the {ordinal(random.randint(1, 30))} at {clock(random.randint(8, 12), random.choice([0, 15, 30, 45]))}.",
    lambda: f"{random.choice(DAYS)} the {ordinal(random.randint(1, 30))} of {random.choice(MONTHS)}.",
    lambda: f"The rain gauge shows {words(random.randint(1, 60))} millimetres since this morning.",
    lambda: f"The lights in {random.choice(ROOMS)} have been on for {words(random.randint(2, 9))} hours.",
    lambda: f"I'll turn the heating off in {words(random.choice([5, 10, 15, 20, 30, 45]))} minutes.",
    lambda: f"The wind is gusting to {words(random.randint(15, 90))} kilometres an hour.",
    lambda: f"Sunset is at {clock(random.randint(5, 8), random.randint(1, 59))} this evening.",
    lambda: f"The year is two thousand and {words(random.randint(1, 30))}.",
    lambda: f"The phone number ends in {' '.join(words(random.randint(0, 9)) if True else '' for _ in range(4))}.",
    lambda: f"That's {words(random.randint(2, 12))} out of {words(random.randint(12, 20))}, if anyone's keeping score.",
]

random.seed(20261019)
n = int(sys.argv[1]) if len(sys.argv) > 1 else 110
seen, out = set(), []
while len(out) < n:
    s = random.choice(T)()
    s = s[0].upper() + s[1:]
    if s not in seen:
        seen.add(s); out.append(s)
print("# Templated spoken numbers (scripts/gen_numbers.py, seed 20261019).")
print("\n".join(out))
