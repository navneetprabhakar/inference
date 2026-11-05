"""Original conversational teaching examples and a reviewed 12-exchange OASST2 slice."""
from hashlib import sha256
import json
from pathlib import Path
import random

DATA = Path(__file__).resolve().parent / "reports/chat-teaching"
LICENSED_HASH = "db8feea675c6dd93d8771a69a670a7b0a8ae8527075c41edd461c904eb704888"
NAMES = "Anya Bo Cora Dan Emre Faye Hugo Isha Jade Kira Leon Noor Owen Pia Ravi Tara".split()
OBJECTS = "notebook lantern compass apron pouch ribbon flask hammer basket jacket".split()
COLORS = "red blue green yellow brown purple orange white grey black pink silver".split()
PLACES = ["the porch", "the studio", "the shed", "the loft", "the pantry", "the hallway", "the cellar", "the workshop"]
DAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
EVENTS = ["the rehearsal", "the reading", "the practice", "the lesson", "the meeting", "the concert"]
INSTRUCTIONS = [
    ("close the window", "close the window", "Please close the window.", "Could you close the window?"),
    ("bring the tray", "bring the tray", "Please bring the tray.", "Could you bring the tray?"),
    ("return the folder", "return the folder", "Please return the folder.", "Could you return the folder?"),
    ("move the stool", "move the stool", "Please move the stool.", "Could you move the stool?"),
    ("pass the brush", "pass the brush", "Please pass the brush.", "Could you pass the brush?"),
    ("open the gate", "open the gate", "Please open the gate.", "Could you open the gate?"),
    ("water the herbs", "water the herbs", "Please water the herbs.", "Could you water the herbs?"),
    ("wash the cups", "wash the cups", "Please wash the cups.", "Could you wash the cups?"),
]
EXPLAIN = [
    ("Why does a shadow form?", "An object blocks light from reaching a surface.", "a wall", "A lamp shining past your hand leaves a dark shape on a wall."),
    ("What does a sieve do?", "It separates pieces by size. Small pieces pass through its holes.", "sand", "Sand can fall through while large stones stay behind."),
    ("What is a draft of a story?", "It is an early version that the writer can revise.", "a story about birds", "A writer might change how the birds meet in the next draft."),
    ("Explain a bookmark.", "It marks your place so you can return to the same page.", "a paper strip", "Put the paper strip between the pages before you close the book."),
    ("What makes an echo?", "Sound reflects off a surface and returns to the listener.", "a tunnel", "A shout can bounce off the tunnel walls and come back to you."),
    ("What is a map legend?", "It explains what the symbols on a map mean.", "a campsite", "A little tent on the map might mark a campsite."),
    ("What is a hinge?", "It joins two parts and lets one swing relative to the other.", "a cabinet", "A hinge lets the cabinet door swing open."),
    ("Explain a queue.", "A queue is a line in which the first arrival is served first.", "a bakery", "At a bakery, the first person in line buys bread first."),
    ("What is a rough estimate?", "It is an approximate answer based on limited information.", "a bowl of beads", "You could guess the count from the size of the bowl."),
    ("Why label storage bins?", "Labels help people find the right bin without opening each one.", "spare buttons", "A bin marked 'buttons' is easy to find."),
    ("What is a table of contents?", "It lists sections of a book and helps you find them.", "a cookbook", "Look up the bread section in the contents."),
    ("Why are instructions numbered?", "Numbers show the order in which to do the steps.", "folding a box", "Do the first fold before moving on to the second."),
    ("What is a compass used for?", "It helps you find directions using a magnetic needle.", "a trail", "Use the needle to check which way is north on the trail."),
    ("What does a lid do?", "It covers the opening of a container.", "a jar", "A lid can keep dust out of the jar."),
    ("How does a zipper work?", "A slider guides two rows of teeth together or apart.", "a coat", "Pull the slider upward to close the coat."),
    ("What does a subtitle do?", "It shows speech as text on the screen.", "a silent room", "You can read the dialogue when the volume is off."),
]
SMALL_TALK = [
    ("Hello.", "Hello! What would you like to work on?", "I just wanted to say hi.", "Hi! It's nice to hear from you."),
    ("Good morning.", "Good morning! How can I help?", "I need to organize my day.", "Start by choosing the most important thing you want to finish today."),
    ("Can you help me write a note?", "Sure. Who is the note for, and what should it say?", "For a friend who lent me a book.", "Thank you for lending me the book. I enjoyed reading it."),
    ("I'm looking for something to draw.", "Try drawing an object you can see from where you're sitting.", "I can see a mug.", "Start with its oval rim, add the sides, then sketch the handle."),
    ("I don't understand my assignment.", "Which part is unclear?", "It asks for a summary.", "Give the main idea and the essential details in your own words."),
    ("I'm trying to name a small garden.", "What grows there?", "Mostly mint.", "Mint Corner would be a simple name."),
    ("Could you suggest a simple game?", "Try a word chain. Each new word starts with the last letter of the word before it.", "Start with apple.", "Apple ends in e, so my word is egg."),
    ("I want to practice telling a story.", "Start with a character who wants something.", "A mouse wants a blanket.", "The mouse searched the old cupboard for a blanket before winter."),
    ("I need a polite way to decline an invitation.", "Thanks for inviting me. I won't be able to come this time.", "Can you make it warmer?", "Thank you for thinking of me. I wish I could join you, and I hope you have a lovely time."),
    ("I want to describe a quiet night.", "The street was still, and only the leaves moved.", "Make it shorter.", "Only the leaves moved."),
    ("What should I put on a packing list?", "Where are you going, and for how long?", "One night in a cabin.", "Pack a change of clothes, toiletries, water, and a light."),
    ("Can you tell me if the package arrived?", "I don't have tracking information. What does the latest tracking update say?", "It says delivered.", "The tracking update says it was delivered."),
    ("Can you see the label on my box?", "I can't see the box here. Please type the label.", "It says wool.", "The label says wool."),
    ("Could you make my sentence sound friendlier?", "Sure. What sentence would you like to change?", "Give me the pen.", "Could you pass me the pen, please?"),
    ("Can you tell me tomorrow's local weather?", "I don't have a weather report. Do you have a forecast I can read?", "The forecast says rain.", "Rain is forecast for tomorrow."),
    ("I forgot what we decided before this conversation.", "I only have the messages here. Can you remind me what you were deciding?", "We decided to paint the fence.", "The decision was to paint the fence."),
    ("My friend learned to swim.", "That sounds worth celebrating. Would you like help writing a message?", "Yes, make it short.", "Congratulations on learning to swim!"),
    ("I wrote a poem.", "Would you like to share it or get feedback on it?", "I want feedback on the ending.", "Paste the poem and I'll focus on the ending."),
    ("I am making a poster for a bake sale.", "What details should the poster include?", "Saturday in the school hall.", "Bake Sale This Saturday in the School Hall"),
    ("I have a pile of loose notes.", "Try grouping them by topic before putting them in folders.", "Two are about repairs.", "Put the repair notes together and label the folder Repairs."),
    ("Please send a letter for me.", "I can help draft it here. Who is it for?", "For the garden club.", "Dear Garden Club,"),
    ("Did you turn on the lamp?", "No. I can't control the lamp from here.", "What can you help with?", "I can help you work through the instructions if you share them."),
    ("Read the number from the ticket.", "Please share the ticket text first.", "Ticket number nineteen.", "The ticket number is nineteen."),
    ("Say something encouraging before my rehearsal.", "Take it one phrase at a time. You can start again if you miss a note.", "Make it just three words.", "One phrase first."),
]


def history(*texts):
    return [{"role": "user" if i % 2 == 0 else "assistant", "text": text} for i, text in enumerate(texts)]


def authored(seed):
    rng = random.Random(seed)
    for origin in SMALL_TALK:
        yield "conversation", history(*origin)
    for q, ans, situation, example in EXPLAIN:
        yield "explanation", history(q, ans, f"Give an example involving {situation}.", example)
        yield "explanation", history(q, ans)
    for action, _, polite, question in INSTRUCTIONS:
        for name in NAMES:
            yield "rewrite", history(f"Make this instruction polite: {action}.", polite,
                                     f"Address it to {name}.", f"{name}, please {action}.")
            yield "rewrite", history(f"Turn '{action}' into a question.", question,
                                     "Now give the direct instruction again.", action.capitalize()+".")
    for i in range(360):
        a,b = rng.sample(NAMES, 2)
        x,y = rng.sample(OBJECTS,2)
        c,k,l = rng.sample(COLORS,3)
        p,q = rng.sample(PLACES,2)
        first, new = rng.sample(DAYS,2)
        event = rng.choice(EVENTS)
        forms = [
            ("color", history(f"The {x} is {c}. The {y} is {k}. Which color is the {x}?", c.capitalize()+".",
                              f"I repainted the {x} {l}. What color is it now?", l.capitalize()+".",
                              f"And the {y}?", k.capitalize()+".")),
            ("location", history(f"{a} left the {x} in {p}. Where did {a} leave it?", p.capitalize()+".",
                                 f"{b} moved it to {q}. Where is it now?", q.capitalize()+".")),
            ("owner", history(f"{a} owns the {x}; {b} owns the {y}. Who owns the {y}?", b+".",
                              f"{b} gave the {y} to {a} to keep. Who owns it now?", a+".")),
            ("schedule", history(f"{event.capitalize()} is on {first}. Which day should I write down?", first+".",
                                  f"It moved to {new}. Update the note.", f"{event.capitalize()} is on {new}.")),
            ("evidence", history(f"The {x} was found in {p}. Who left it there?", "The note doesn't say who left it.",
                                  f"{b} tells us it belonged to {a}. Whose was it?", a+".")),
            ("preference", history(f"{a} prefers {c}; {b} prefers {k}. Which color should I choose for {b}?", k.capitalize()+".",
                                    f"Actually the gift is for {a}. Which color?", c.capitalize()+".")),
            ("extraction", history(f"Read this label: '{a} / {x} / {p}'. Return only the item.", x,
                                    "Now give only the name.", a)),
            ("social-writing",history(f"Thank {b} for lending the {x}.",f"Thank you, {b}, for lending me the {x}.",
                                      f"Replace the {x} with the {y}.",f"Thank you, {b}, for lending me the {y}.")),
            ("clarification",history(f"Which day is {event}?", "I don't have its date. What does the notice say?",
                                     f"The notice says {first}.", f"{event.capitalize()} is on {first}.")),
            ("recall",history(f"My name is {a}.",f"Hello, {a}.",
                              f"I brought a {c} {x}. What did I bring?",f"A {c} {x}.",
                              "What is my name?",a+".")),
            ("order",history(f"First clean the {x}, then put it in {p}. Which step comes first?",f"Clean the {x}.",
                             "I've finished that step. What is next?",f"Put it in {p}.")),
            ("format",history(f"Write '{c} {x}' in uppercase only.",f"{c} {x}".upper(),
                              "Now give just the object name in lowercase.",x)),
        ]
        yield from forms


def records(seed):
    seen=set()
    for family, conversation in authored(seed):
        key=json.dumps(conversation, ensure_ascii=False,sort_keys=True)
        if key not in seen:
            seen.add(key)
            yield family, "original-synthetic", conversation
    raw=(DATA/"oasst-selected.jsonl").read_bytes()
    if sha256(raw).hexdigest()!=LICENSED_HASH:
        raise ValueError("OASST teaching selection hash mismatch")
    for line in raw.splitlines():
        yield "licensed-dialogue","OpenAssistant/oasst2",json.loads(line)["history"]


def examples(seed: int):
    result=[h for _,_,h in records(seed)]
    random.Random(seed).shuffle(result)
    return result


def natural_records():
    files = {
        "natural-turns.txt": "f2c9f67849e7d73869b5aecfda5a2fa139e0e56e02ff7840b9df1969d58d984b",
        "everyday-selected.jsonl": "d19ca0e7107b96253b36d97bfd42856f3b15e9c7d151ea74babbe8a8ef0950a4",
        "oasst-selected.jsonl": LICENSED_HASH,
    }
    for name, expected in files.items():
        raw = (DATA / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError(f"Natural dialogue artifact hash mismatch: {name}")
        for index, line in enumerate(raw.decode().splitlines(), 1):
            if name == "natural-turns.txt":
                texts = [part.strip() for part in line.split("|")]
                if len(texts) != 4 or not all(texts):
                    raise ValueError(f"Malformed authored dialogue on line {index}")
                yield "original-synthetic", str(index), history(*texts)
            else:
                record = json.loads(line)
                if name == "everyday-selected.jsonl":
                    yield "everyday-conversations", str(record["row_id"]), record["history"]
                else:
                    yield "OpenAssistant/oasst2", record["tree"], record["history"]
    for i, parts in enumerate(SMALL_TALK):
        yield "original-synthetic", f"small-talk-{i}", history(*parts)
    for i, (question, answer, situation, example) in enumerate(EXPLAIN):
        followup = f"Give an example involving {situation}."
        yield "original-synthetic", f"explain-{i}", history(question, answer, followup, example)


def natural_examples(seed: int):
    """Distinct editorially reviewed situations for separate sampling from slot drills."""
    result = [conversation for _,_,conversation in natural_records()]
    random.Random(seed).shuffle(result)
    return result
