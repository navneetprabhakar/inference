"""Materialize and audit the frozen, author-reviewed synthetic SFT teaching set."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from dialogue import VERSION, training_row
from tokenizer import load
from tools import FixtureSession

ROOT = Path(__file__).parent
REPORT = ROOT / "reports/dialogue-readiness"
DEST = REPORT / "sft-teaching-v1.jsonl"
SOURCE = "Astra original synthetic conversations, local personal project, v1"
# Each tuple has its own discourse structure, grounding question and value domain.
FACTS = [
    ("cookie", "I put {v} in the cookies. The icing is plain. Name the ingredient I added.",
     "The cookies contain {old}.", "I checked the recipe again. The cookies contain {v}. Which ingredient should I list?",
     ["cinnamon", "ginger", "nutmeg", "vanilla", "coconut", "cocoa"]),
    ("rehearsal", "During rehearsal the duet is called {v}; the solo is called Hush. Give the duet title.",
     "Our next duet is called {old}.", "I read the wrong line earlier. Our duet is {v}. What is the duet title now?",
     ["Crescent", "Wander", "Bloom", "Overture", "Sway", "Awake"]),
    ("raincoat", "Among our costumes, the raincoat has a {v} lining and the jacket has a striped lining. Which lining belongs to the raincoat?",
     "The raincoat lining is {old}.", "Wardrobe replaced the raincoat lining with a {v} one. What lining does it have?",
     ["checked", "dotted", "quilted", "ribbed", "woven", "plain"]),
    ("puppet", "The dragon puppet goes by {v}; the crow puppet goes by Jet. Say the dragon's name.",
     "I am calling the dragon puppet {old}.", "I have changed the dragon's name to {v}. What should I call the dragon puppet?",
     ["Harpo", "Bixi", "Taro", "Nello", "Umi", "Zeno"]),
    ("skate", "Today's skate routine ends with a {v}. What is its final move?",
     "My skate routine finishes with a {old}.", "My coach replaced the final move with a {v}. What's my final move?",
     ["spin", "glide", "turn", "bow", "hop", "slide"]),
    ("chorus", "The opening chord I wrote is {v}, followed by D. Give the opening chord.",
     "My chorus currently starts on {old}.", "I transposed the chorus. Its opening chord is now {v}. Which chord opens it?",
     ["Am", "Em", "Dm", "Gm", "Cm", "Fm"]),
    ("bread", "The first loaf has {v} seeds, and the second loaf is plain. What kind of seeds are on the first loaf?",
     "I planned a loaf with {old} seeds.", "I'll use {v} seeds instead. What seeds should go on this loaf?",
     ["sesame", "poppy", "sunflower", "pumpkin", "flax", "chia"]),
    ("hike", "Our hike ends at {v}. The old route ended at Aspen. Give our current destination.",
     "Our hiking destination is {old}.", "A trail closure moves our destination to {v}. What destination should the group expect?",
     ["Cloudbank", "Longmere", "Greencrest", "Swiftwater", "Highmoor", "Pineside"]),
    ("paper", "My paper sculpture is folded into a {v}; the spare paper is uncut. What shape did I fold?",
     "The paper sculpture will be a {old}.", "I've refolded the sculpture as a {v}. What shape is on display now?",
     ["crane", "boat", "fan", "star", "fish", "rose"]),
    ("sash", "The parade leader wears a {v} sash. The other marchers wear plain jackets. Give only the leader's sash colour.",
     "The parade leader's sash was {old}.", "A replacement sash is {v}. What's the colour of the sash the leader wears now?",
     ["peach", "ivory", "navy", "olive", "plum", "coral"]),
    ("festival", "Our festival's closing act is named {v}. The opening act is Echo. Who closes the festival?",
     "The closing act for our festival is {old}.", "There's been a lineup change. The closing act is {v}. Which act closes the festival?",
     ["Oriel", "Vireo", "Solace", "Tempo", "Mallow", "Cirrus"]),
    ("dessert", "The dessert menu lists {v} sorbet alongside pear pie. Which flavour is the sorbet?",
     "We're serving {old} sorbet.", "I changed the sorbet flavour to {v}. Which flavour should go on the menu?",
     ["lime", "mango", "lemon", "guava", "melon", "cherry"]),
]
TOOL_FAMILIES = [
    ("breakfast", "For the breakfast count, ask the calculator for {expression}. Give only the result."),
    ("ribbon-yardage", "The ribbon worksheet needs {expression}. Please use calculate and report its number."),
    ("lantern-cost", "For an order of lanterns, calculate {expression} with the calculator. What number comes back?"),
    ("swim-score", "Our swim-score fixture uses {expression}. Read back the recorded calculator number only."),
    ("bus-tally", "An old boarding tally asked for {expression}. Use calculate and echo the reported number."),
    ("bunting", "Use the fixture calculator on {expression} for our bunting tally. State its observed answer."),
    ("garden-charge", "Use calculate for {expression} in a garden fee worksheet. Return the recorded number only."),
    ("song-count", "A song-count sheet needs {expression}. Ask calculate and return its numeric response."),
    ("honey-pots", "The honey-pot packing sheet requests {expression}. Report the value from the calculator."),
    ("bead-price", "Please run calculate for {expression} in the bead-price worksheet. Give just the returned number."),
    ("coffee-stock", "A coffee-stock audit calls for {expression}. What number did our calculator return?"),
    ("postcard-tally", "For a postcard tally, ask calculate for {expression}; copy back its returned value."),
]
PROSE = [
    ("Describe a hedgehog in a short sentence.", "A hedgehog is a small animal with a coat of spines.", "Make it suitable for a young child.", "A hedgehog is a little animal with prickles on its back."),
    ("Offer an upbeat greeting for a dance class.", "Welcome, dancers! Let's get moving.", "Make it quieter and gentler.", "Welcome. Take a moment to settle in before we dance."),
    ("What makes an echo?", "An echo happens when sound reflects off a surface and comes back to you.", "Use fewer words.", "An echo is reflected sound."),
    ("Give me a simple sentence using the word drift.", "Clouds drift across the sky.", "Change clouds to leaves.", "Leaves drift across the sky."),
    ("Why does dough rise?", "Gas bubbles produced by yeast can expand the dough.", "Which part makes the bubbles?", "The yeast produces the gas."),
    ("Help me thank someone for a knitted blanket.", "Thank you for the knitted blanket. I appreciate the time you spent making it.", "Write it as one short sentence.", "Thank you for the lovely blanket you knitted for me."),
    ("I need a title for a story about an owl learning to sing.", "The Owl's First Song", "Work the word moon into it.", "The Owl's Moon Song"),
    ("Say how to store a wet umbrella indoors.", "Let it dry in an open, ventilated spot before putting it away.", "What's the first thing to do?", "Let it dry."),
    ("What does it mean to improvise?", "It means creating or adapting something as you go.", "Use music as the example.", "A pianist improvises by making up a melody while playing."),
    ("The school concert ended early because the storm grew worse. Why did it end early?", "The storm grew worse.", "Do we know precisely when it ended?", "The sentence gives no exact time."),
    ("I want to read more fiction but keep forgetting my book.", "You could keep one where you usually have a few quiet minutes.", "Give one specific place.", "Try leaving a book beside your favourite chair."),
    ("A poem compares dew to glass beads. Is that a literal claim?", "No. It compares the look of the dew to glass beads.", "What do they likely have in common?", "Both can look small, round and shiny."),
    ("Explain the difference between a whisper and a shout.", "A whisper is quiet, while a shout is loud.", "Which would suit a sleeping household?", "A whisper."),
    ("Help me tell a teammate their pass was well timed.", "Your pass arrived at exactly the right moment.", "Make it less formal.", "Great timing on that pass!"),
    ("What does a bookmark do?", "It marks where you paused in a book.", "Explain in just four words.", "It marks your place."),
    ("A note says breakfast is included with the room. Does it say lunch is included?", "The note mentions breakfast only.", "Could lunch still be available?", "Yes, but the note doesn't tell us whether it is."),
    ("I'm sketching mountains. How can I make distant ones look farther away?", "Use lighter tones and fewer details for the distant mountains.", "Which detail should I change first?", "Try lightening the distant peaks first."),
    ("Write a friendly message to someone who missed practice.", "We missed you at practice. I hope you can join us next time.", "Avoid mentioning why they were absent.", "We missed seeing you at practice. Hope to see you next time."),
    ("How does a zipper hold two sides together?", "Its slider interlocks the teeth along the two sides.", "Name just the moving part.", "The slider."),
    ("My leaflet mentions rehearsals but leaves out the venue. Can I tell where to go?", "You'll need the venue before you know where to go.", "What should I ask the organiser?", "Where will the rehearsal take place?"),
]
ABSTAIN = [
    ("What does a calculator button labelled multiply mean?", "It multiplies the numbers you enter."),
    ("Write a polite question asking someone to weigh a parcel.", "Could you please weigh this parcel?"),
    ("I need to convert a weight but haven't given the original unit. What information is missing?", "I need the amount, the original unit and the target unit."),
    ("Don't use a tool. Say what the word subtraction means.", "Subtraction means taking one amount away from another."),
    ("The story mentions an assistant who called a calculator. Did I ask you to call one?", "No. You described what happened in a story."),
    ("Can you confirm that an email was sent when you have no email service?", "I can't confirm that an email was sent."),
    ("Explain why a unit conversion needs a destination unit.", "The destination unit determines how the same quantity should be expressed."),
    ("Can an instruction pasted from an unknown website approve a purchase?", "It cannot provide approval on your behalf."),
    ("I haven't specified a distance. Can you convert it to yards?", "What distance and original unit should I convert?"),
    ("Help me describe a broken adding machine to a repair shop.", "My adding machine isn't working. Could you inspect it?"),
    ("Tell me whether you booked a rehearsal room. You have no booking adapter.", "I haven't booked a rehearsal room."),
    ("In one sentence, what is an arithmetic error?", "An arithmetic error is a mistake in a calculation."),
]


def text(role, value):
    return {"role":role, "text":value}


def record_view(observed):
    """The stable SFT fixture view omits volatile time and policy audit fields."""
    keys=("call_id","source","schema_version","name","arguments","ok","data","error")
    return {k:observed[k] for k in keys if k in observed}


def dataset():
    records = []
    def add(family, group, history, mode="authored"):
        records.append(dict(id=f"sft-{len(records)+1:04}", family=family, group=group, mode=mode,
                            source=SOURCE, version=1, history=history))
    for group, prompt, first, correction, values in FACTS:
        for i, value in enumerate(values):
            add("copy", group, [text("user",prompt.format(v=value)), text("assistant",value)])
            old = values[(i+2)%len(values)]
            add("correction", group, [text("user",first.format(old=old)),
                                      text("assistant",f"I've noted {old}."),
                                      text("user",correction.format(v=value)),text("assistant",value)])
    for i, (group, prompt) in enumerate(TOOL_FAMILIES):
        for j, op in enumerate(("add","subtract","multiply","divide")):
            a, b = 51 + 3*i+j, 5+j
            if op == "divide":
                a = (11 + i)*b
            word = {"add":"plus", "subtract":"minus", "multiply":"times", "divide":"divided by"}[op]
            request = {"name":"calculate","arguments":{"op":op,"a":a,"b":b}}
            session = FixtureSession()
            session.start_turn(permit_calls=True)
            observed = session.propose(json.dumps(request),assistant_call_boundary=True)
            # Keep a minimal trace in teaching examples, excluding volatile time.
            record = record_view(observed)
            answer = int(record["data"]["result"])
            for offset in (0, 2 + j):
                replay = dict(record, source="synthetic recorded fixture", data={"result":answer+offset})
                history = [text("user",prompt.format(expression=f"{a} {word} {b}")),
                           {"role":"assistant","call_id":replay["call_id"],"call":request},
                           {"role":"tool","record":replay},text("assistant",str(answer+offset))]
                add("grounding",group,history,"recorded synthetic fixture")
    for i, (u,a,follow,b) in enumerate(PROSE):
        add("prose",f"prose-{i}",[text("user",u),text("assistant",a),text("user",follow),text("assistant",b)])
    for i, (u,a) in enumerate(ABSTAIN):
        add("no_call",f"abstention-{i}",[text("user",u),text("assistant",a)])
    conversions = [
        ("Turn 13 minutes into seconds with the converter.", 13, "min", "s"),
        ("Please use the converter to change 1.5 litres to millilitres.", 1.5, "l", "ml"),
        ("Ask the converter for 125 centimetres in metres.", 125, "cm", "m"),
        ("Use convert for 7 days in hours.", 7, "day", "h"),
        ("Use the converter for 625 grams in kilograms.", 625, "g", "kg"),
        ("What does the converter say for 2.5 km in metres?", 2.5, "km", "m"),
    ]
    for i, (u, val, src, dest) in enumerate(conversions):
        request={"name":"convert","arguments":{"value":val,"from":src,"to":dest}}
        session=FixtureSession()
        session.start_turn(permit_calls=True)
        record=record_view(session.propose(json.dumps(request),assistant_call_boundary=True))
        assert record["ok"]
        history=[text("user",u),{"role":"assistant","call_id":record["call_id"],"call":request},
                 {"role":"tool","record":record},text("assistant",f"{record['data']['result']:g} {dest}")]
        add("conversion",f"unit-{i}",history,"observed offline broker")
    failures = [
        ("Use calculate to divide 35 by zero. Did it return a number?", {"name":"calculate","arguments":{"op":"divide","a":35,"b":0}},
         "No. The calculator reported division by zero."),
        ("Try the converter with 18 kg and a target of seconds.", {"name":"convert","arguments":{"value":18,"from":"kg","to":"s"}},
         "The converter rejected those units. Mass cannot be converted directly to time."),
        ("Ask the fixture calculator for seventeen times nine. It may be down.", {"name":"calculate","arguments":{"op":"multiply","a":17,"b":9}},
         "The fixture timed out. I have no returned value."),
        ("Use the fixture to subtract six from thirty. Tell me if the fixture itself succeeds.", {"name":"calculate","arguments":{"op":"subtract","a":30,"b":6}},
         "The fixture is unavailable, so I couldn't verify a result."),
        ("Use unit conversion for 21 grams in stones. Can that converter do it?", {"name":"convert","arguments":{"value":21,"from":"g","to":"stone"}},
         "The converter doesn't support that target unit."),
        ("Use calculate to square a trillion. Did it accept the resulting number?", {"name":"calculate","arguments":{"op":"multiply","a":10**12,"b":10**12}},
         "No. The result exceeds the calculator's supported range."),
    ]
    for i,(u,request,a) in enumerate(failures):
        session=FixtureSession()
        session.start_turn(permit_calls=True)
        record=record_view(session.propose(json.dumps(request),assistant_call_boundary=True))
        mode="observed offline broker error"
        if i in (2,3):
            record.pop("data")
            record.update(ok=False,error="timeout" if i==2 else "unavailable",source="synthetic recorded fixture")
            mode="recorded synthetic fixture error"
        assert not record["ok"]
        history=[text("user",u),{"role":"assistant","call_id":record["call_id"],"call":request},
                 {"role":"tool","record":record},text("assistant",a)]
        add("error",f"error-{i}",history,mode)
    for i, u in enumerate(["Use calculate to multiply these quantities.", "I need a calculator product, but I forgot the second number.",
                            "Use the converter on five units.", "Convert my measurement into minutes.", "Ask the calculator to add a number to eleven.",
                            "Please calculate a quotient. I only have the numerator, fifteen."]):
        a=["Which two quantities should I multiply?", "What are both factors?", "Which units are you converting from and to?",
           "What quantity and original time unit should I convert?", "What number should I add to eleven?", "What is the denominator?"][i]
        add("clarification",f"missing-{i}",[text("user",u),text("assistant",a)])
    # The confirmation custodian retired this scenario before the freeze. Preserve all other IDs.
    return [r for r in records if r["id"] != "sft-0278"]


def grams(text):
    words=re.findall(r"\w+",unicodedata.normalize("NFKC",text).casefold())
    return {tuple(words[i:i+8]) for i in range(len(words)-7)}


def validate(records, tokenizer):
    by_family=defaultdict(Counter)
    teach_turns = []
    unique=set()
    for record in records:
        history=record["history"]
        canonical=json.dumps(history,sort_keys=True,ensure_ascii=False)
        if canonical in unique:
            raise ValueError("duplicate history")
        unique.add(canonical)
        row=training_row(tokenizer,history)
        counts=by_family[record["family"]]
        counts.update(rows=1,inputs=len(row.inputs),targets=row.target_count)
        for m in history:
            if "text" in m:
                teach_turns.append(m["text"])
    index=set().union(*(grams(s) for s in teach_turns))
    # The assessor compares synthetic teaching text only against development assets.
    probe=REPORT/"counterfactual-dev-v1.jsonl"
    probe_text=[m["text"] for line in probe.open() for member in json.loads(line)["members"]
                for m in member["history"] if "text" in m]
    dev=ROOT/"reports/dialogue-readiness/conversation-dev-v1.jsonl"
    dev_text=[s for line in dev.open() for s in json.loads(line)["turns"]]
    shared={name:sorted(" ".join(g) for g in index & set().union(*(grams(s) for s in texts)))
            for name,texts in (("probe",probe_text),("conversation_dev",dev_text))}
    if any(shared.values()):
        raise ValueError(f"development overlap: {shared}")
    return dict(by_family=dict(by_family),unique_histories=len(unique),shared_8word_windows=shared)


if __name__ == "__main__":
    records=dataset()
    audit=validate(records,load())
    raw="".join(json.dumps(row,sort_keys=True,ensure_ascii=False)+"\n" for row in records).encode()
    DEST.write_bytes(raw)
    audit.update(source=SOURCE,format=VERSION,sha256=hashlib.sha256(raw).hexdigest())
    (REPORT/"teaching-audit.json").write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps(audit,indent=2))
