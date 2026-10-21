"""Atlas STT test set: 151 short household commands and questions in Atlas's style.

Sources: the house's device/room names from voice-lewis-small (corpus/train_ext4, corpus/heldout_r3 and scripts/gen_house.py NAMES,
including the eight held-out names), the scenes Good Night and Wind Down, energy words (kilowatt hours, ZeroCharge, battery, solar),
and the owner's 22 real phrasings (atlas-current/owner-phrasings.json, branch atlas-current-input), written out in normal spelling.

Each item: id, cat, text (the reference transcript), say (what the TTS voice reads, only where it differs: digits and symbols spelled
out the way a person says them), slots (what must be heard right for the action to be understood; "a|b" = either). Writes
testset/commands.jsonl. Deterministic; no randomness here.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "testset", "commands.jsonl")

# (text, slots, say or None)
LIGHTS = [
    ("Turn on the atrium lights.", ["atrium", "on"]),
    ("Turn off the atrium spotlight left.", ["atrium spotlight left", "off"]),
    ("Switch on the pergola floodlight two.", ["pergola floodlight 2", "on"]),
    ("Turn the pergola spotlights off.", ["pergola spotlight", "off"]),
    ("Turn on the ensuite downlight.", ["ensuite downlight", "on"]),
    ("Turn off the loft lamp.", ["loft lamp", "off"]),
    ("Loft lights on.", ["loft light", "on"]),
    ("Turn the laundry lights off.", ["laundry light", "off"]),
    ("Turn on the laundry downlight.", ["laundry downlight", "on"]),
    ("Switch off the garage ceiling right.", ["garage ceiling right", "off"]),
    ("Turn on porch downlight three.", ["porch downlight 3", "on"]),
    ("Turn off the patio lights.", ["patio light", "off"]),
    ("Turn on the fountain spotlight.", ["fountain spotlight", "on"]),
    ("Turn the mirror ambiance on.", ["mirror ambiance|mirror ambience", "on"]),
    ("Turn off the robe downlight.", ["robe downlight", "off"]),
    ("Turn on the wall floodlight.", ["wall floodlight", "on"]),
    ("Wall light off, please.", ["wall light", "off"]),
    ("Turn on kitchen chandelier two.", ["kitchen chandelier 2", "on"]),
    ("Turn off living room chandelier six.", ["living room chandelier 6", "off"]),
    ("Turn on range hood one.", ["range hood 1", "on"]),
    ("Turn off all the lights upstairs.", ["upstairs", "off"]),
    ("Turn off the downstairs lights.", ["downstairs", "off"]),
    ("Turn on the ground floor lights.", ["ground floor", "on"]),
    ("Turn on the hallway downlight front.", ["hallway downlight front", "on"]),
    ("Switch off the dining room pendant.", ["dining room pendant", "off"]),
    ("Turn on the guest bedroom lamp.", ["guest bedroom lamp", "on"]),
    ("Turn off the master bedroom ceiling.", ["master bedroom ceiling", "off"]),
    ("Turn on the study ceiling.", ["study ceiling", "on"]),
    ("Turn off the kitchen downlight left.", ["kitchen downlight left", "off"]),
    ("Turn the outside lights on.", ["outside light", "on"]),
]
BRIGHT = [
    ("Set the atrium spotlight right to forty percent.", ["atrium spotlight right", "40 percent"]),
    ("Dim the loft lamp to twenty percent.", ["loft lamp", "20 percent"]),
    ("Dim the living room lamp to thirty-five percent.", ["living room lamp", "35 percent"]),
    ("Brighten the kitchen ceiling to eighty percent.", ["kitchen ceiling", "80 percent"]),
    ("Set the pergola floodlights to fifty percent.", ["pergola floodlight", "50 percent"]),
    ("Make the dining room pendant seventy-five percent.", ["dining room pendant", "75 percent"]),
    ("Dim the master bedroom lamp to ten percent.", ["master bedroom lamp", "10 percent"]),
    ("Set the ensuite downlight to fifteen percent.", ["ensuite downlight", "15 percent"]),
    ("Turn the hallway downlight back up to sixty percent.", ["hallway downlight back|hallway downlight", "60 percent"]),
    ("Put the guest bedroom ceiling on at forty-five percent.", ["guest bedroom ceiling", "45 percent"]),
    ("Can you dim the atrium lights a bit?", ["dim", "atrium"]),
    ("Make the loft brighter.", ["loft", "brighter"]),
    ("Set the laundry downlight to full brightness.", ["laundry downlight", "full"]),
    ("Set the porch lights to five percent.", ["porch light", "5 percent"]),
    ("Dim living room chandelier three to twenty-five percent.", ["living room chandelier 3", "25 percent"]),
]
TIMERS = [
    ("Turn the porch lights off at 10:15 pm.", ["porch light", "off", "1015 pm"], "Turn the porch lights off at ten fifteen p m."),
    ("Turn off the loft lamp in twenty-five minutes.", ["loft lamp", "off", "25 minute"]),
    ("Turn the atrium lights off at 11:30.", ["atrium", "off", "1130"], "Turn the atrium lights off at eleven thirty."),
    ("Switch on the garden spotlight at 7:30 pm.", ["garden spotlight", "on", "730 pm"], "Switch on the garden spotlight at seven thirty p m."),
    ("Turn the kitchen lights off in half an hour.", ["kitchen light", "off", "half hour|30 minute"]),
    ("In ten minutes, turn off the laundry lights.", ["10 minute", "off", "laundry light"]),
    ("Turn on pergola spotlight one at 6:45.", ["pergola spotlight 1", "on", "645"], "Turn on pergola spotlight one at six forty-five."),
    ("Turn the study lights off at 9:05 pm.", ["study light", "off", "905 pm"], "Turn the study lights off at nine oh five p m."),
    ("Turn the garage lights off in an hour.", ["garage light", "off", "hour"]),
    ("Turn the living room lamp off at midnight.", ["living room lamp", "off", "midnight"]),
    ("Turn off the master bedroom lamp at 12:40 am.", ["master bedroom lamp", "off", "1240 am"], "Turn off the master bedroom lamp at twelve forty a m."),
    ("Turn the hallway lights on at 6 am tomorrow.", ["hallway light", "on", "6 am", "tomorrow"], "Turn the hallway lights on at six a m tomorrow."),
    ("Turn the ensuite downlight off in five minutes.", ["ensuite downlight", "off", "5 minute"]),
    ("Turn the outside lights off at quarter past eleven.", ["outside light", "off", "quarter past 11|1115"]),
    ("Run Good Night at 10:30 pm.", ["goodnight", "1030 pm"], "Run Good Night at ten thirty p m."),
    ("Start Wind Down in fifteen minutes.", ["wind down", "15 minute"]),
    ("Cancel that.", ["cancel"]),
    ("Cancel the porch lights timer.", ["cancel", "porch light"]),
    ("What timers do I have?", ["timer"]),
    ("Turn the pergola floodlights on at sunset.", ["pergola floodlight", "on", "sunset"]),
]
SCENES = [
    ("Good night.", ["goodnight"]),
    ("Run Good Night.", ["goodnight"]),
    ("Activate the Good Night scene.", ["goodnight"]),
    ("Start Wind Down.", ["wind down"]),
    ("Wind Down, please.", ["wind down"]),
    ("Put the Wind Down scene on.", ["wind down"]),
    ("Set the house to Wind Down.", ["wind down"]),
    ("Undo that.", ["undo"]),
]
BLINDS = [
    ("Close the atrium blind.", ["atrium blind", "close"]),
    ("Open the atrium blind halfway.", ["atrium blind", "open", "halfway|half way|half"]),
    ("Set the atrium blind to thirty percent.", ["atrium blind", "30 percent"]),
    ("Close the living room door blind.", ["living room door blind", "close"]),
    ("Open the living room window blind.", ["living room window blind", "open"]),
    ("Lower the living room blinds to twenty percent.", ["living room blind", "20 percent"]),
    ("Raise the atrium blind all the way.", ["atrium blind", "raise"]),
    ("Close all the blinds.", ["close", "blind"]),
    ("Open the atrium blind at 1 pm.", ["atrium blind", "open", "1 pm"], "Open the atrium blind at one p m."),
    ("Is the atrium blind down?", ["atrium blind", "down"]),
    ("Put the living room window blind at seventy percent.", ["living room window blind", "70 percent"]),
    ("Yes, close it.", ["yes", "close"]),
]
ENERGY = [
    ("What's the battery at?", ["battery"]),
    ("How many kilowatt hours have we used today?", ["kwh", "today"]),
    ("How many kWh did the solar make yesterday?", ["kwh", "solar", "yesterday"], "How many K W H did the solar make yesterday?"),
    ("What's the solar doing right now?", ["solar"]),
    ("Are we exporting to the grid?", ["exporting|export", "grid"]),
    ("How much are we selling to the grid?", ["selling", "grid"]),
    ("When does ZeroCharge start?", ["zerocharge", "start"], "When does Zero Charge start?"),
    ("Is it ZeroCharge time yet?", ["zerocharge"], "Is it Zero Charge time yet?"),
    ("How long is left in the ZeroCharge window?", ["zerocharge", "left"], "How long is left in the Zero Charge window?"),
    ("Should I run the dishwasher during ZeroCharge?", ["dishwasher", "zerocharge"], "Should I run the dishwasher during Zero Charge?"),
    ("What's the house using right now?", ["using"]),
    ("How much power is the house drawing?", ["power", "drawing"]),
    ("Is the battery charging?", ["battery", "charging"]),
    ("What percentage is the battery at?", ["battery", "percentage"]),
    ("Will the battery last the night?", ["battery", "night"]),
    ("How much did we import from the grid today?", ["import", "grid", "today"]),
    ("What's our usage in kilowatt hours this week?", ["usage", "kwh", "week"]),
    ("How much solar are we getting?", ["solar"]),
    ("Should I run the washing machine now or at eleven?", ["washing machine", "11"]),
    ("Can I run the dryer on solar?", ["dryer", "solar"]),
    ("Is it cheaper to run the pool pump at midday?", ["pool pump", "midday"]),
    ("How many kilowatt hours is a full battery?", ["kwh", "full battery"]),
]
CLIMATE = [
    ("What's the temperature in the atrium?", ["temperature", "atrium"]),
    ("How warm is it in the loft?", ["warm", "loft"]),
    ("What's the temperature outside?", ["temperature", "outside"]),
    ("Is it going to rain today?", ["rain", "today"]),
    ("What's the forecast for the weekend?", ["forecast", "weekend"]),
    ("How hot will it get tomorrow?", ["hot", "tomorrow"]),
    ("What's the UV index?", ["uv"], "What's the U V index?"),
    ("Is it humid in the laundry?", ["humid", "laundry"]),
    ("Should I put the aircon on?", ["ac", "on"]),
    ("Set the air conditioner to twenty-two degrees.", ["ac", "22 degrees"]),
    ("Will it be cold tonight?", ["cold", "tonight"]),
    ("What was the overnight low?", ["overnight", "low"]),
]
STATUS = [
    ("Which lights are on?", ["light", "on"]),
    ("Are any lights on upstairs?", ["light", "upstairs"]),
    ("Is the loft lamp on?", ["loft lamp", "on"]),
    ("Did the laundry lights go off?", ["laundry light", "off"]),
    ("Is the pergola lit up?", ["pergola"]),
    ("Is the garage door shut?", ["garage door", "shut"]),
    ("What time is it?", ["time"]),
    ("Thanks, Atlas.", ["thanks|thank you"]),
    ("Never mind.", ["never mind"]),
    ("Leave the atrium lights on.", ["leave", "atrium", "on"]),
]
# The owner's real phrasings (owner-phrasings.json), in normal spelling; the person's intended words where the old STT garbled them.
OWNER = [
    ("How's the battery holding up?", ["battery", "holding up"]),
    ("What kWh is that equal to?", ["kwh", "equal"], "What kilowatt hours is that equal to?"),
    ("How full is the battery?", ["full", "battery"]),
    ("What's the weather doing?", ["weather"]),
    ("What's the temp?", ["temp|temperature"]),
    ("Should I run the AC?", ["ac"], "Should I run the A C?"),
    ("What's the weather like tomorrow?", ["weather", "tomorrow"]),
    ("Create an AC plan putting the heat on at 11 am until 12 pm at 22 degrees.", ["ac", "heat", "11 am", "12 pm", "22"],
     "Create an A C plan putting the heat on at eleven a m until twelve p m at twenty-two degrees."),
    ("Turn on the study light.", ["study light", "on"]),
    ("Turn the study light to 100%.", ["study light", "100 percent"], "Turn the study light to one hundred percent."),
    ("Turn off the outside lights.", ["outside light", "off"]),
    ("Hello.", ["hello"]),
    ("Can you turn off the living room lights?", ["living room light", "off"]),
    ("Turn on the living room lights.", ["living room light", "on"]),
    ("How's the battery going?", ["battery", "going"]),
    ("How is the home?", ["home"]),
    ("Shouldn't the atrium blind be down in that case?", ["atrium blind", "down"]),
    ("Why didn't it go down?", ["go down"]),
    ("Close the atrium blind to 30%. Open it completely at 1 pm.", ["atrium blind", "close", "30 percent", "open", "1 pm"],
     "Close the atrium blind to thirty percent. Open it completely at one p m."),
    ("Can you do basic arithmetic?", ["arithmetic"]),
    ("What's 2 + 8?", ["2", "8"], "What's two plus eight?"),
    ("I have a small dishwasher load. Will I run it tonight or run it in the morning?", ["dishwasher", "tonight", "morning"]),
]
GROUPS = [("lights", LIGHTS), ("brightness", BRIGHT), ("timers", TIMERS), ("scenes", SCENES), ("blinds", BLINDS), ("energy", ENERGY),
          ("climate", CLIMATE), ("status", STATUS), ("owner", OWNER)]
HOUSE_WORDS = ["atrium", "pergola", "ensuite", "loft", "laundry", "goodnight", "wind down", "kwh", "zerocharge"]


def main():
    sys.path.insert(0, HERE)
    from textnorm import canon
    rows, n = [], 0
    for cat, items in GROUPS:
        for it in items:
            n += 1
            text, slots = it[0], it[1]
            say = it[2] if len(it) > 2 else None
            c = canon(text)
            tricky = sorted({w for w in HOUSE_WORDS if w in c} | ({"number"} if any(ch.isdigit() for ch in c) else set()))
            rows.append({"id": f"C{n:03d}", "cat": cat, "text": text, "say": say or text, "slots": slots, "tricky": tricky})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{len(rows)} commands -> {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
