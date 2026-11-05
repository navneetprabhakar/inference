"""Train-only paired teaching scenarios. No reading of evaluation or archive data."""
import json
import random
from string import Formatter
from collections import Counter
from hashlib import sha256
from pathlib import Path

SEED = 1459
PAIRS_PER_FORM = 105

# Four turns per form. Braces reference the *current* member's synthetic world.
# Paired members keep all nonfocus facts constant while the focused value changes.
FORMS = {
    "introduce_recall": [
        ("Hi, I'm {a}.", "Hello! How can I help?", "What did I say my name was?", "{a}"),
        ("Call me {a} during our chat.", "Sure. What would you like to discuss?", "Which name should you call me?", "{a}"),
        ("Before we start, my name is {a}. My colleague is {b}.", "Nice to meet you.", "Remind me of my own name, not my colleague's.", "{a}"),
        ("{b} introduced us yesterday. I'm {a}.", "Hello! What brings you here?", "What do I go by?", "{a}"),
        ("Let me introduce myself: {a}.", "Welcome!", "Repeat my name by itself.", "{a}"),
        ("You can put {a} on my badge.", "Got it. What else should it show?", "Just the name I gave you. What is it?", "{a}"),
        ("Hello there! People here know me as {a}.", "Hello! It's good to meet you.", "How did I introduce myself?", "{a}"),
        ("We have two guests: I'm {a}, and my friend is {b}.", "Hello to both of you.", "Which guest am I?", "{a}"),
        ("My friend uses the name {b}. I use {a}.", "Thanks for the introductions.", "If you address me directly, what name will you use?", "{a}"),
    ],
    "greeting_context": [
        ("Hey, is anyone here?", "Hello! I'm here. How can I help?", "My name's {a}. Say hello to me by name.", "Hello, {a}!"),
        ("Good morning!", "Good morning! What would you like to do?", "I'm {a}. How would you greet me now?", "Good morning, {a}!"),
        ("Hello! I'm new to the group.", "Welcome! What name would you like to use?", "Please use {a}. Write a short welcome.", "Welcome, {a}!"),
        ("Hi there, can we chat?", "Of course. What's on your mind?", "First, introduce me as {a}.", "This is {a}."),
        ("Nice to meet you.", "Nice to meet you too!", "My name is {a}. Could you say it back?", "{a}"),
        ("Are you around for a quick question?", "Yes. What would you like to ask?", "My badge reads {a}. What's the name on it?", "{a}"),
        ("Hello again.", "Hello! What would you like help with today?", "Call me {a}. Can you greet me in one short sentence?", "Hello, {a}!"),
    ],
    "binding": [
        ("{facts} What tag belongs to {a}?", "{x}", "And what about {b}?", "{y}"),
        ("{facts} Name the person who has tag {y}.", "{b}", "Which tag is assigned to the other person?", "{x}"),
        ("{assignment} Which value should go next to {a}?", "{x}", "Read out the value beside {b}.", "{y}"),
        ("{containers} What is inside the {left} container?", "{x}", "What did the other container hold?", "{y}"),
        ("{orders} Who requested {x}?", "{a}", "What did the other person request?", "{y}"),
        ("{facts} Which of these tags can I get from {b}?", "{y}", "Who would have the remaining tag?", "{a}"),
        ("{allocation} If I look for {x}, whom should I ask?", "{a}", "And if I want {y}?", "{b}"),
        ("{containers} I just need the label in the {right} container.", "{y}", "The {left} one instead?", "{x}"),
        ("{assignment} Tell me {b}'s value without repeating the whole list.", "{y}", "Now identify the person paired with {x}.", "{a}"),
    ],
    "correction": [
        ("The tag on my {item} reads {z}. What is its tag?", "{z}", "I misread the label. It actually says {x}. Give me the corrected tag.", "{x}"),
        ("{facts} What's {a}'s tag?", "{x}", "I need to fix the list: {b} now has {z}, and {a} has {y}. What does {a} have now?", "{y}"),
        ("I put down {z} as the destination. Which destination did I write?", "{z}", "Cross that out and use {x}. Which destination belongs on the new card?", "{x}"),
        ("For the first draft, use the title {z}. Repeat the title.", "{z}", "That was the working title. The final one is {x}. Return the final title only.", "{x}"),
        ("The earlier code was {z} but the active code is {x}. Which is active?", "{x}", "I need the superseded code for my notes. Which one was that?", "{z}"),
        ("The last stop was going to be {z}. Which stop did we plan?", "{z}", "The map changed. End at {x}, though {z} remains marked on it. Where should we end?", "{x}"),
        ("My colleague expected {z}; the reading actually shows {x}. What did we measure?", "{x}", "Which result did the colleague expect?", "{z}"),
        ("{allocation} Tell me who has {x}.", "{a}", "They exchange their items. Who holds {x} after the exchange?", "{b}"),
        ("Start the log with {z}. What value have we entered so far?", "{z}", "First change that to {y}, then change it once more to {x}. What is the latest entry?", "{x}"),
    ],
    "ordered_choice": [
        ("{route} Which place is reached first?", "{x}", "Now give the last place.", "{z}"),
        ("{route} What stop lies between the other two?", "{y}", "Which stop do I reach immediately after it?", "{z}"),
        ("{queue} Who is last in line?", "{c}", "Who was immediately ahead of that person?", "{b}"),
        ("In order, the three labels are {x}, {y}, {z}. Read the last label.", "{z}", "Read the one just before it.", "{y}"),
        ("{route} Reverse that route. Where would you start?", "{z}", "Where would the reversed route finish?", "{x}"),
        ("The register starts with {a} and ends with {c}. {b} is between them. Who is the middle entry?", "{b}", "Remove the first name. Which name is first now?", "{b}"),
        ("A helper processes {x} before {y}, then processes {z}. What comes after {x}?", "{y}", "Suppose {y} is skipped. What comes immediately after {x} now?", "{z}"),
        ("{route} Where were we immediately before arriving at {z}?", "{y}", "Which stop would we have visited just before {y}?", "{x}"),
        ("{queue} If only the first person is admitted, who gets in?", "{a}", "The first person leaves the line. Who is at the front now?", "{b}"),
    ],
    "missing_evidence": [
        ("The slip identifies {a} as the owner of a {item}. Does it mention when it was bought?", "No. The purchase date isn't given.", "Who is the known owner?", "{a}"),
        ("Someone carried a {item} into {x}. Can you name the person from that alone?", "No. The person isn't identified.", "A witness says {a} carried it. Who was it?", "{a}"),
        ("The box labeled {x} was delivered. Can we tell what it weighs?", "No. Its weight isn't given.", "Which label is actually in the account?", "{x}"),
        ("Our note says the meeting will be in {x}. When does it start?", "The note gives the place but not the start time.", "Which place does it give?", "{x}"),
        ("{a} and {b} both volunteered. Does that say which one arrived first?", "No. Their arrival order isn't stated.", "{a} says {b} was already there on arrival. Who arrived first?", "{b}"),
        ("A {item} is wrapped in plain paper. Can you infer its color?", "No. The wrapping doesn't tell us its color.", "We unwrap it and see that it is {color}. What color is it?", "{color}"),
        ("The request mentions {x}; no one is named. Who submitted it?", "The requester is unknown.", "The signature is finally visible: {a}. Who signed it?", "{a}"),
        ("The message reads '{x}'. Was it sent today?", "The message contains no date.", "What did the message actually say?", "{x}"),
    ],
    "clarification": [
        ("Can you shorten it for me?", "Which text would you like me to shorten?", "Shorten 'The {item} that belongs to {a}' to a possessive phrase.", "{a}'s {item}"),
        ("Which one did I ask for?", "Which choices are you referring to?", "There were two labels, {x} and {y}. I asked for {x}. Which one?", "{x}"),
        ("Please tell me the destination.", "Which trip are you asking about?", "The trip that starts in {z} and ends in {x}. Give its destination.", "{x}"),
        ("Can you write the name in the blank?", "Whose name should I use?", "Use {a}, not {b}. Return only the name.", "{a}"),
        ("I need the label from my ticket.", "What does the ticket say?", "It says '{x}'. Copy just the label.", "{x}"),
        ("Help me address this note.", "Who is the note for?", "It is for {a}. Start it with Dear and the name.", "Dear {a},"),
        ("Can you settle which entry is current?", "What entries are you comparing, and which was updated?", "The earlier entry was {z}. The latest is {x}. Which is current?", "{x}"),
        ("Which container should I use?", "What are the containers for?", "The {left} container is for {x}; the {right} one is for {y}. I have {x}. Which container?", "{left}"),
    ],
    "constrained_rewrite": [
        ("Copy this two-word label: '{x} {item}'.", "{x} {item}", "Keep the object but replace the first word with {y}. Return only the revised label.", "{y} {item}"),
        ("Turn 'Please bring the {item}' into a question.", "Could you bring the {item}?", "Address your question to {a}.", "{a}, could you bring the {item}?"),
        ("Put brackets around {x}.", "[{x}]", "Use parentheses around the same text instead.", "({x})"),
        ("Write '{a} carried the {item}' in the present tense.", "{a} carries the {item}.", "Now change only the subject to {b}.", "{b} carries the {item}."),
        ("Copy the code {x} in uppercase.", "{upper_x}", "Write the same code in lowercase only.", "{lower_x}"),
        ("Give me a short label for the {item} that belongs to {a}.", "{a}'s {item}", "The owner is now {b}. Revise only the name.", "{b}'s {item}"),
        ("Write the two labels {x} and {y} separated by a comma.", "{x}, {y}", "Reverse their order and keep the comma.", "{y}, {x}"),
        ("Thank {a} for the {item} in one sentence.", "Thank you, {a}, for the {item}.", "Keep the sentence but address it to {b}.", "Thank you, {b}, for the {item}."),
        ("Copy only the last word of '{color} {item}'.", "{item}", "Now copy only the first word of that same phrase.", "{color}"),
    ],
    "conditional": [
        ("The rule says use {x} when the flag is open and {y} when it is closed. It is open. Which label?", "{x}", "The flag closes. Which label now?", "{y}"),
        ("If the request is for paper, ask {a}. If it is for cloth, ask {b}. I need cloth. Who can help?", "{b}", "I change my request to paper. Who should I ask?", "{a}"),
        ("For a {color} mark choose {x}; for a {color2} mark choose {y}. The mark is {color2}. What do I choose?", "{y}", "The mark is redrawn in {color}. What do I choose now?", "{x}"),
        ("The club opens {left} only for members; visitors must use {right}. I'm a visitor. Which entrance?", "{right}", "I become a member. Which entrance is reserved for members?", "{left}"),
        ("When the switch is up the screen shows {x}; when down it shows {z}. The screen shows {x}. Where is the switch?", "Up.", "I lower the switch. What does the screen show?", "{z}"),
        ("Take {x} if {a} arrives first; take {y} if {b} arrives first. {a} gets here first. Which do I take?", "{x}", "Instead, suppose {b} arrives before {a}. What would I take?", "{y}"),
        ("We send small parcels to {x} and large parcels to {z}. This parcel is large. Where should it go?", "{z}", "The next one is small. What is its destination?", "{x}"),
        ("A round stamp means {a}; a square stamp means {b}. The stamp is round. Who does it identify?", "{a}", "It has been replaced with a square stamp. Who now?", "{b}"),
    ],
}

STARTS = ("Az","Bell","Cev","Drav","Es","Flin","Gav","Hes","Ivr","Jev","Kelm","Lun","Mav","Nir","Osk","Pav","Quil","Rov","Sel","Tor","Ulv","Ves","Wyr","Xav","Yor","Zel")
MIDS = ("ala","eri","avo","eli","oro","anu","ira","uva","aro","emi","ito","oru","avi","uli","ena","esu","ani","ido","aro","evu","iru","oba","ilu","eya")
ENDS = ("ven","sil","reth","mor","lin","dak","sen","ril","dor","vin","mir","tal","rin","sas","mar","dyn")
ITEMS = ("chisel","medallion","portfolio","flagon","whistle","satchel","sash","brooch","anklet","folio","flute","bonnet","slate","die","stencil","stamp","trowel","gauge","mallet","plaque","brocade","roller")
COLORS = ("copper","turquoise","beige","indigo","scarlet","umber","violet","olive","pearl","cerulean","cream","bronze","gold","amber","teal","navy")
CONTAINERS = ("narrow","wide","striped","patterned","painted","round","square","short","tall","polished","plain","woven")


def word(rng):
    return rng.choice(STARTS) + rng.choice(MIDS) + rng.choice(ENDS)


def novel_values(rng, count):
    values = []
    while len(values) < count:
        value = word(rng)
        if value not in values:
            values.append(value)
    return values


def world(rng):
    a,b,c,x,y,z,alternative=novel_values(rng,7)
    left,right=rng.sample(CONTAINERS,2)
    color,color2=rng.sample(COLORS,2)
    return dict(a=a,b=b,c=c,x=x,y=y,z=z,left=left,right=right,
                color=color,color2=color2,item=rng.choice(ITEMS)),alternative


def phrases(values, fact_order, mode):
    v = dict(values)
    a,b,c,x,y,z,left,right=(v[k] for k in ("a","b","c","x","y","z","left","right"))
    def combine(first,second):
        return f"{first} {second}" if fact_order else f"{second} {first}"
    v["facts"] = combine(f"{a} has tag {x}.", f"{b} has tag {y}.")
    v["assignment"] = combine(f"The value for {a} is {x}.", f"The value for {b} is {y}.")
    v["allocation"] = combine(f"{x} went to {a}.", f"{y} went to {b}.")
    v["containers"] = combine(f"The {left} container holds {x}.", f"The {right} container holds {y}.")
    v["orders"] = combine(f"{a} requested {x}.", f"{b} requested {y}.")
    v["queue"] = (f"From front to back the people waiting are {a}, {b}, {c}."
                  if mode else f"{c} waits behind {b}, and {a} is directly ahead of {b}.")
    v["route"] = (f"The route starts at {x}, passes {y}, and ends at {z}."
                  if mode else f"We finish at {z} after passing {y}. The starting point is {x}.")
    v["upper_x"],v["lower_x"] = x.upper(),x.lower()
    return v


def records(seed):
    rng=random.Random(seed)
    seen = set()
    formatter = Formatter()
    for family,forms in FORMS.items():
        for form_id,form in enumerate(forms):
            # Focus the pair on one slot that determines the final response.
            fields = [field for _,field,_,_ in formatter.parse(form[3]) if field]
            if not fields:
                fields = [field for _,field,_,_ in formatter.parse(form[1]) if field]
            if not fields:
                raise ValueError(f"Missing answer slot for {family}/{form_id}")
            for pair in range(PAIRS_PER_FORM):
                values,alternative = world(rng)
                focus = rng.choice(fields)
                if focus in ("lower_x","upper_x"):
                    focus = "x"
                if focus.startswith("color"):
                    alternative = rng.choice([c for c in COLORS if c not in (values["color"],values["color2"])])
                elif focus in ("left","right"):
                    alternative = rng.choice([c for c in CONTAINERS if c not in (values["left"],values["right"])])
                elif focus == "item":
                    alternative = rng.choice([item for item in ITEMS if item != values["item"]])
                order, mode = rng.randrange(2), rng.randrange(2)
                members = []
                for variant in range(2):
                    cell = dict(values)
                    if variant:
                        cell[focus] = alternative
                    slots = phrases(cell,order,mode)
                    turns = [dict(role=role,text=text.format(**slots))
                             for role,text in zip(("user","assistant","user","assistant"),form)]
                    members.append(turns)
                assert members[0][1:] != members[1][1:]
                keys = [tuple(m["text"] for m in h) for h in members]
                if any(key in seen for key in keys):
                    continue
                seen.update(keys)
                for variant,h in enumerate(members):
                    yield dict(family=family,form=form_id,pair=pair,variant=variant,focus=focus,history=h)


def examples(seed: int):
    rows=[r["history"] for r in records(seed)]
    random.Random(seed).shuffle(rows)
    return rows


if __name__ == "__main__":
    rows=list(records(SEED))
    from tokenizer import load
    from dialogue import training_row
    tokenizer=load()
    seen=set()
    counts=Counter()
    max_tokens=0
    for r in rows:
        h=r["history"]
        assert len(h)==4 and all(m["text"].strip() for m in h)
        key=json.dumps(h,ensure_ascii=False,sort_keys=True)
        counts[r["family"]]+=1
        seen.add(key)
        max_tokens=max(max_tokens,len(training_row(tokenizer,h).inputs))
    report=dict(seed=SEED,source="original programmatically generated; reviewed forms + deterministic world-state substitution",
                histories=len(rows),distinct_histories=len(seen),families=dict(counts),forms={s:len(v) for s,v in FORMS.items()},
                max_dialogue_v1_input_tokens=max_tokens,
                histories_sha256=sha256(json.dumps(examples(SEED),sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                examples_by_family={s:next(r["history"] for r in rows if r["family"]==s) for s in FORMS})
    root=Path("reports/compositional-teaching");root.mkdir(exist_ok=True)
    (root/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print({k:v for k,v in report.items() if k not in ("examples_by_family","forms")})
