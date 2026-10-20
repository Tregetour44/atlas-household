"""Round 2 templated family (train_ext2/numbers2.txt): times, percentages, energy and weather in Atlas's phrasing.
Deterministic (seed 20261020); shares the number-to-words helpers with gen_numbers.py."""
import random, sys
from gen_numbers import words, clock, ordinal, ROOMS, DAYS

ROOMS2 = ROOMS + ["the hallway", "the bathroom", "the dining room", "the nursery"]
T = [
    lambda: f"Battery at {words(random.randint(5, 100))} percent.",
    lambda: f"The battery's at {words(random.randint(5, 99))} percent, and the panels are making {words(random.randint(1, 7))} point {words(random.randint(0, 9))} kilowatts.",
    lambda: f"We're {words(random.randint(30, 100))} percent self-powered today.",
    lambda: f"It's {words(random.randint(1, 40))} degrees outside and {words(random.randint(15, 27))} in {random.choice(ROOMS2)}.",
    lambda: f"Top of {words(random.randint(12, 41))} today, low of {words(random.randint(2, 22))} tonight.",
    lambda: f"There's a {words(random.choice(range(10, 100, 10)))} percent chance of rain after {clock(random.randint(1, 8), random.choice([0, 30]))}.",
    lambda: f"It's {clock(random.randint(1, 12), random.randint(0, 59))}.",
    lambda: f"It's {clock(random.randint(1, 12), random.choice([0, 15, 30, 45]))}, and {random.choice(['the house is quiet', 'all the doors are locked', 'the battery is holding up', 'the kettle has boiled'])}.",
    lambda: f"{random.choice(['Lights', 'Heater', 'Air con', 'Fan', 'Music'])} off in {words(random.choice([2, 5, 10, 15, 20, 30]))} minutes.",
    lambda: f"The {random.choice(['washing machine', 'dryer', 'dishwasher', 'oven timer', 'robot vacuum'])} will be done at {clock(random.randint(1, 12), random.choice([0, 5, 10, 15, 20, 30, 40, 45, 50]))}.",
    lambda: f"Grid power is {words(random.randint(6, 70))} cents a kilowatt hour until {clock(random.randint(1, 11), random.choice([0, 30]))}.",
    lambda: f"So far today we've used {words(random.randint(3, 30))} kilowatt hours and exported {words(random.randint(0, 25))}.",
    lambda: f"The car's at {words(random.randint(10, 100))} percent. It'll be full by {clock(random.randint(1, 8), random.choice([0, 30]))}.",
    lambda: f"Humidity is {words(random.randint(20, 98))} percent, and the wind is {words(random.randint(5, 60))} kilometres an hour.",
    lambda: f"Sunrise is at {clock(random.randint(5, 7), random.randint(1, 59))}, and sunset at {clock(random.randint(5, 8), random.randint(1, 59))}.",
    lambda: f"Your next reminder is at {clock(random.randint(1, 12), random.choice([0, 15, 30, 45]))} on {random.choice(DAYS)}.",
    lambda: f"That's {words(random.randint(2, 9))} hours and {words(random.randint(2, 55))} minutes of battery left at this rate.",
    lambda: f"The thermostat in {random.choice(ROOMS2)} is set to {words(random.randint(16, 26))} degrees.",
    lambda: f"The {ordinal(random.randint(1, 28))} is a {random.choice(DAYS)}.",
]

def main():
    random.seed(20261020)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seen, out = set(), []
    while len(out) < n:
        s = random.choice(T)()
        s = s[0].upper() + s[1:]
        if s not in seen:
            seen.add(s); out.append(s)
    print("# Round 2 templated numbers (scripts/gen_numbers2.py, seed 20261020).")
    print("\n".join(out))

if __name__ == "__main__":
    main()
