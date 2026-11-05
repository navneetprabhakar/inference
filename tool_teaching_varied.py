"""Deterministic synthetic tool lessons with real offline broker observations."""
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import random

from local_chat import tool_view
from tool_teaching import display, proposal, reply, u
from tools import FixtureSession, execute

# A form binds its verbal roles to a numeric domain. Counts are never negative;
# signed meter readings and decimal arithmetic occur only in forms that support them.
ARITHMETIC = {
    "add": {
        "signed": [
            "Add the reading {a} to {b}.",
            "Apply a signed adjustment of {b} to an initial reading of {a}. Where does it finish?",
            "The two components of my total are {a} and {b}. Combine them.",
            "What single number comes from adding {a} and {b}?",
            "My starting balance is {a} credits. A transaction changes it by {b} credits. What is the resulting balance?",
            "Calculate the value at the end of these two changes from zero: first {a}, then {b}.",
        ],
        "positive": [
            "The short segment is {a} units long, and the extension is {b} units. What is the whole length?",
            "One jug holds {a} litres. Pour in another {b} litres. How much liquid is there?",
            "I entered {b} on the second line and {a} on the first. What is their total?",
        ],
        "count": [
            "The late delivery contained {b} notebooks. There were already {a} on the shelf. How many are there now?",
            "An audience of {a} people at the first show and {b} at the second. Count both shows together.",
            "Two teams logged {a} and {b} completed tests. What combined count should I report?",
            "A basket of {a} pears is joined by a second basket of {b}. Give the number of pears.",
        ],
    },
    "subtract": {
        "signed": [
            "What is {a} less {b}? Give the result of the ordered subtraction.",
            "Starting from {a}, subtract {b}.",
            "From the reading {a}, take the signed quantity {b}. What remains?",
            "An instrument previously read {b} and now reads {a}. What was the signed change, new minus old?",
            "We need the offset of {a} relative to {b}. Use the first value minus the second.",
            "How far above {b} is {a}? Keep the sign if it is below.",
        ],
        "positive": [
            "{b} metres were cut from a roll that had {a} metres. How many metres are left?",
            "Of {a} litres in storage, {b} litres leaked out. What remains?",
            "To get the net weight, deduct the packaging weight of {b} from the gross weight of {a}.",
        ],
        "count": [
            "Yesterday's count was {b}; today's is {a}. Report today's count minus yesterday's.",
            "{b} attendees left a room that held {a}. How many stayed?",
            "There are {a} seats available. A group reserved {b}. How many seats can still be booked?",
            "Out of {a} files, {b} have finished downloading. How many are pending?",
        ],
    },
    "multiply": {
        "signed": [
            "Scale {a} by a factor of {b}.",
            "Evaluate the product with factors {a} and {b}.",
            "The coefficients in my expression are {a} and {b}. What is their product?",
            "I need {b} multiplied by {a}; what number do I get?",
        ],
        "positive": [
            "A rectangle measures {a} metres by {b} metres. Compute its area.",
            "My material costs {a} credits per metre. What do {b} metres cost?",
            "The rate is {a} litres each minute for {b} minutes. What volume passes through?",
            "A map uses {a} real kilometres per map unit. How far away is a mark {b} units from the start?",
        ],
        "count": [
            "Each shelf fits {a} folders and there are {b} identical shelves. What is the capacity?",
            "There are {b} trays with {a} rolls on every tray. Count the rolls.",
            "For a mosaic, repeat a row of {a} tiles {b} times. How many tiles do I need?",
            "Order {b} boxes. Each box contains {a} pieces. How many pieces is that altogether?",
        ],
    },
    "divide": {
        "signed": [
            "Find {a} over {b}.",
            "What quotient results when the dividend is {a} and the divisor is {b}?",
            "Use {b} as the denominator and {a} as the numerator. Evaluate the fraction.",
            "By what factor must {b} be multiplied to obtain {a}?",
            "Compute the signed ratio of the first reading, {a}, to the second, {b}.",
        ],
        "positive": [
            "A line {a} metres long is divided into {b} equal sections. What's the length of one?",
            "A machine processes {a} litres over {b} minutes. What is the rate per minute?",
            "The total is {a} credits for {b} identical units. Find the price per unit.",
            "Each portion has {b} litres. How many portions fit into {a} litres?",
        ],
        "count": [
            "If each crate takes {b} bottles, how many full crates does the shipment of {a} bottles fill?",
            "Distribute {a} badges equally across {b} booths. How many should each booth get?",
            "There are {a} chairs arranged equally in {b} rows. How many chairs are in a row?",
        ],
    },
}
INTERNAL_ARITHMETIC = {
    "add": {"signed": ["A subtotal of {a} needs the posted delta {b} applied. Read back the updated subtotal."],
            "count": ["A morning counter logged {a}; an evening counter logged {b}. What figure goes in the daily combined field?"]},
    "subtract": {"signed": ["My baseline was {b}. A sample came in at {a}. How much did the sample exceed the baseline, signed?"],
                 "positive": ["Please remove the tare of {b} from the scale indication of {a} to determine the contents alone."]},
    "multiply": {"positive": ["A plot spans {a} units in one direction and {b} in the other. How many square units does it cover?"],
                 "count": ["I stamped {a} labels per sheet for {b} full sheets. What number of labels did I stamp?"]},
    "divide": {"signed": ["The lower number of a displayed fraction is {b}; the upper number is {a}. What value does the display represent?"],
               "count": ["A workshop used {a} screws assembling {b} identical chairs. How many screws went into each chair?"]},
}
UNIT_WORDS = {
    "mm": ("millimetre","millimeter"), "cm": ("centimetre","centimeter"),
    "m": ("metre","meter"), "km": ("kilometre","kilometer"),
    "g": ("gram",), "kg": ("kilogram",), "ml": ("millilitre","milliliter"),
    "l": ("litre","liter"), "s": ("second",), "min": ("minute",),
    "h": ("hour",), "day": ("day",),
}
UNIT_PAIRS = {
    "length": [("km","m"),("m","cm"),("cm","mm"),("m","mm")],
    "mass": [("kg","g")], "volume": [("l","ml")],
    "time": [("day","h"),("h","min"),("min","s"),("h","s")],
}
CONVERSIONS = [
    "My instrument reads {v} {s}. Show that value in {d}.",
    "In {d}, how much would {v} {s} be?",
    "I need a label in {d}, but the old label says {v} {s}. What value should replace it?",
    "What figure in {d} is equivalent to {v} {s}?",
    "Use {d} as the output unit and {s_plural} as the input unit. The input number is {v}.",
    "Change the unit on a measurement of {v} {s} so that it is expressed in {d}.",
    "Record {v} {s} on a form expecting {d}. What should I enter?",
    "Which quantity in {d} represents the same measurement as {v} {s}?",
    "Convert this entry from {s_plural} into {d}: {v}.",
    "The destination unit is {d}. The measurement I have is {v} {s}. Give the converted quantity.",
    "Move my reading to the {d} column: {v} {s}.",
    "How would a reading of {v} {s} appear on a scale graduated in {d}?",
]
INTERNAL_CONVERSIONS = [
    "My worksheet's heading is {d}. A source record contains {v} {s}. What goes in the cell?",
    "Show the equivalent count for {v} {s} when the display is set to {d}.",
    "Input unit {s_plural}, requested output unit {d}, input value {v}. Compute the displayed value.",
]
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()


def spoken(value):
    if value < 0:
        return "minus " + spoken(-value)
    if value >= 100:
        return display(value)
    whole, _, frac = display(value).partition(".")
    n = int(whole)
    word = ONES[n] if n < 20 else TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    return word + (" point " + " ".join(ONES[int(d)] for d in frac) if frac else "")


def surface(value, rng):
    return spoken(value) if rng.randrange(4) == 0 else display(value)


def operands(op, domain, rng):
    if domain == "count":
        a, b = rng.randint(3, 52), rng.randint(2, 12)
        return (a*b,b) if op=="divide" else (max(a,b),min(a,b)) if op=="subtract" else (a,b)
    if domain == "positive":
        b = rng.choice([1,2,3,4,5,8,10,12])
        a = rng.randint(3,80)/rng.choice([1,2,4])
        if op == "divide":
            return a*b,b
        if op == "subtract":
            return a+b,b
        return a,b
    a = rng.randint(-150,160)/rng.choice([1,2,4])
    b = rng.choice([-8,-4,-2,-1,1,2,4,8]) if op=="divide" else rng.randint(-50,70)/rng.choice([1,2,4])
    return a,b


def spelled_unit(code, count, rng):
    name = rng.choice(UNIT_WORDS[code])
    return name if abs(count)==1 else name+"s"


def calculate(op,a,b):
    return {"name":"calculate","arguments":{"op":op,"a":a,"b":b}}


def convert(value,source,target):
    return {"name":"convert","arguments":{"value":value,"from":source,"to":target}}


@dataclass
class Lesson:
    family: str
    history: list
    observations: list
    policy: list


class Builder:
    def __init__(self, family):
        self.family = family
        self.history = []
        self.observations = []
        self.policy = []
        self.session = FixtureSession()

    def user(self, text, *, permit=True, fixture_for=None, fixture=None):
        self.session.start_turn(permit_calls=permit,fixture_for=fixture_for,fixture=fixture)
        self.history.append(u(text))
        self.policy.append(dict(permit_calls=permit,fixture_for=fixture_for,fixture=fixture))

    def call(self, call):
        observation=self.session.propose(json.dumps(call),assistant_call_boundary=True)
        self.history.extend((proposal(call["name"],call["arguments"]),{"role":"tool","result":tool_view(observation)}))
        # Drop volatile wall time from the auditable source record and retain fixture provenance.
        self.observations.append({k:v for k,v in observation.items() if k!="timestamp"})
        return observation

    def answer(self,text):
        self.history.append(reply(text))

    def finish(self):
        return Lesson(self.family,self.history,self.observations,self.policy)


def standard_reply(record):
    if record["ok"]:
        return display(record["data"]["result"])
    return f"The fixture returned an error: {record['error']}. No number was returned."


def recorded_result(call, rng):
    ordinary = execute(call["name"], call["arguments"])
    result = round(ordinary + rng.choice([-11,-7,-3,5,9])/2, 6)
    if result == ordinary:
        raise AssertionError("counterfactual needs two distinct values")
    return {"result":result}


def followup(builder, call, obs, rng, mode):
    args = call["arguments"]
    value = obs["data"]["result"]
    if mode=="recall":
        builder.user(rng.choice(["What number did that tool report?","Remind me of its actual reading.",
                                 "Repeat only the result already returned."]),permit=False)
        builder.answer(display(value))
    elif mode=="chain":
        factor = rng.choice([-3,-2,2,3,4])
        builder.user(f"Use the calculator to multiply that returned number by {surface(factor,rng)}.")
        builder.answer(standard_reply(builder.call(calculate("multiply",value,factor))))
    elif mode=="original":
        if call["name"]=="calculate":
            builder.user("What was the first operand actually sent to the calculator?",permit=False)
            builder.answer(display(args["a"]))
        else:
            builder.user("Which unit did I start with? Give its abbreviation.",permit=False)
            builder.answer(args["from"])


def arithmetic_lessons(rng, forms, repeats):
    for op, domains in forms.items():
        for domain, templates in domains.items():
            for idx, template in enumerate(templates):
                family=f"arith/{op}/{domain}/{digest_text(template)[:12]}"
                for variant in range(repeats):
                    a,b = operands(op,domain,rng)
                    call=calculate(op,a,b)
                    text=template.format(a=surface(a,rng),b=surface(b,rng))
                    builder=Builder(family)
                    replay=variant%12==3
                    if replay:
                        text+=" Use the offline fixture and tell me its observed result."
                        builder.user(text,fixture_for=call,fixture=recorded_result(call,rng))
                    else:
                        builder.user(text)
                    obs=builder.call(call)
                    result=standard_reply(obs)
                    builder.answer("The fixture reported "+result+"." if replay else result)
                    if variant%3==0:
                        followup(builder,call,obs,rng,["recall","chain","original"][(variant//3)%3])
                    yield builder.finish()


def conversion_lessons(rng, templates, repeats, *, internal=False):
    for domain, pairs in UNIT_PAIRS.items():
        for idx, template in enumerate(templates):
            family=f"convert/{domain}/{digest_text(template)[:12]}"
            for variant in range(repeats):
                src,dst=pairs[(idx+variant//2)%len(pairs)]
                if variant%2:
                    src,dst=dst,src
                value=rng.choice([.125,.25,.5,.75,1,1.5,2,2.5,3.25,4,5,8,12,15,20,24,30,45,60,72,100,120,250,500])
                if internal:
                    value=rng.choice([7.75,11.25,13.75,21.25,17.25,31.5,41.75,91.25,18.5])
                if src in ("min","h","s","day"):
                    # Pick exact quotients when converting to larger time units.
                    if execute("convert",{"value":1,"from":src,"to":dst})<1:
                        dest_values=[2.25,3.25,4.75,6.5,8.75] if internal else [.5,1,1.5,2,3,4,8]
                        value=round(execute("convert",{"value":rng.choice(dest_values),"from":dst,"to":src}),6)
                s=spelled_unit(src,value,rng)
                s_plural=spelled_unit(src,2,rng)
                d=spelled_unit(dst,2,rng)
                text=template.format(v=surface(value,rng),s=s,s_plural=s_plural,d=d)
                call=convert(value,src,dst)
                builder=Builder(family)
                replay=variant%12==4
                if replay:
                    text+=" Quote what the fixture actually returns."
                    builder.user(text,fixture_for=call,fixture=recorded_result(call,rng))
                else:
                    builder.user(text)
                obs=builder.call(call)
                rendered=standard_reply(obs)
                builder.answer(f"The fixture reported {rendered} {dst}." if replay else f"{rendered} {dst}")
                if variant%4==0:
                    followup(builder,call,obs,rng,["original","recall","chain"][(variant//4)%3])
                yield builder.finish()


def digest_text(text):
    return sha256(text.encode()).hexdigest()

SPECIAL = {
    "missing_divisor": [
        "Use the calculator to divide {a}.",
        "There are {a} sheets to share equally. What does each person get?",
        "My numerator is {a}. Can you get the quotient?",
    ],
    "missing_start": [
        "I removed {b} units. How many remain?",
        "Subtract {b} for me, but I've only written down the amount to take away.",
    ],
    "missing_target": [
        "The source value is {a} {s}. Please convert it.",
        "I measured {a} {s}. Can you express that in a different unit?",
        "Convert my {a} {s} reading. I'll give you the target unit if you need it.",
    ],
    "missing_source": [
        "My reading is {a}. Convert it to {d}.",
        "The display should show {d}. The input says {a}, but its unit isn't printed.",
    ],
    "no_call_expression": [
        "Without using any tools, write the multiplication expression for {a} groups of {b}. Don't evaluate it.",
        "No tool calls. Show the product of {a} and {b} as an unevaluated expression.",
    ],
    "permission_change": [
        "Don't use a calculator yet. What operation combines {a} units and {b} more?",
        "Do not call any tools. Tell me which operation belongs between {a} and {b} to find their total.",
    ],
    "no_call_after": [
        "Use the calculator for {a} plus {b}. I may ask for that reading again.",
        "Add {a} to {b} with the calculator and remember the result.",
    ],
    "correct_input": [
        "Find the remainder after taking {b} from {a}.",
        "Compute the new balance if {b} is withdrawn from {a}.",
    ],
    "two_calls": [
        "Add {a} and {b} with the calculator, then divide its result by {z}. Give the final value.",
        "Calculate the combined length {a} plus {b}, then split the total into {z} equal pieces.",
        "First total {a} and {b}. Next find one of {z} equal shares of that total. Use the calculator for both steps.",
    ],
    "convert_chain": [
        "Convert {a} {s} to {d}. Use the calculator to double the converted value.",
        "I need twice the converted quantity: start with {a} {s}, convert to {d}, then multiply the returned number by two.",
    ],
    "transient": [
        "Try the offline calculator for {a} times {b}. Tell me if it responds.",
        "Please find {a} multiplied by {b} using the fixture, even if the fixture is unavailable.",
    ],
    "zero_divisor": [
        "What does the calculator report for {a} divided by zero?",
        "Try {a} as the numerator with a denominator of 0. Report what happens.",
    ],
    "signed_conversion": [
        "An offset is {neg} {s}. What is the signed offset in {d}?",
        "Use {d} for the result. My displacement is {neg} {s}; preserve its sign.",
    ],
    "paired_observation": [
        "Ask the fixture for {a} minus {b} and quote the value it actually supplies.",
        "I am checking the calculator display for {a} minus {b}. Tell me its observed reading.",
    ],
}
INTERNAL_SPECIAL = {
    "missing_divisor": ["The invoice total {a} needs distributing evenly. I didn't include the recipient count. What do you need?"],
    "missing_start": ["The consumption entry is {b}; can you tell me the stock left on hand?"],
    "missing_target": ["I want to express {a} {s} on a different scale. Which other detail is required?"],
    "missing_source": ["Under the heading {d}, I'd like to enter the converted value of {a}. The original label is missing."],
    "no_call_expression": ["No tools. Put {a} lots of {b} on the page as an expression, leaving its value blank."],
    "permission_change": ["Without calling a tool, identify the arithmetic needed to merge amounts {a} and {b}."],
    "no_call_after": ["Use the calculator to total {a} and {b}; I'll need the display value later."],
    "correct_input": ["Take a deduction of {b} off an allocation of {a}. What's the revised allocation?"],
    "two_calls": ["My worksheet asks for one of {z} shares after merging {a} and {b}. Run the sum first and then the quotient."],
    "convert_chain": ["Compute the equivalent in {d} for {a} {s}, then calculate two times that reported reading."],
    "transient": ["Query the multiplication fixture for {a} by {b} and describe the actual response."],
    "zero_divisor": ["The denominator column is zero and the numerator is {a}. Run that quotient through the calculator."],
    "signed_conversion": ["For a relative shift of {neg} {s}, enter the same signed displacement using {d}."],
    "paired_observation": ["Read the fixture's reported difference when its inputs are {a} less {b}. Quote what comes back."],
}


def special_lessons(rng, templates, repeats):
    for mode, forms in templates.items():
        for template in forms:
            family="special/"+mode+"/"+digest_text(template)[:12]
            for index in range(repeats):
                a,b = rng.randint(18,90),rng.randint(2,12)
                z=rng.choice([2,4,5,8])
                src,dst = UNIT_PAIRS["length"][index%4]
                if index%2:
                    src,dst=dst,src
                neg=-rng.choice([.5,1.25,2,3.5,5,7.25,11,18])
                text=template.format(a=surface(a,rng),b=surface(b,rng),z=surface(z,rng),
                                     s=spelled_unit(src,a,rng),d=spelled_unit(dst,2,rng),
                                     neg=surface(neg,rng))
                builder=Builder(family)
                if mode in ("missing_divisor","missing_start","missing_target","missing_source"):
                    builder.user(text,permit=False)
                    question, clarification, call = {
                        "missing_divisor": ("What number should I divide by?",f"Divide it by {b}.",calculate("divide",a,b)),
                        "missing_start": ("What was the starting quantity?",f"I started with {a}.",calculate("subtract",a,b)),
                        "missing_target": ("Which unit should I convert to?",f"Use {spelled_unit(dst,2,rng)}.",convert(a,src,dst)),
                        "missing_source": ("What is the original unit?",f"The source label is {spelled_unit(src,2,rng)}.",convert(a,src,dst)),
                    }[mode]
                    builder.answer(question)
                    builder.user(clarification)
                    val=standard_reply(builder.call(call))
                    builder.answer(val+" "+dst if call["name"]=="convert" else val)
                elif mode=="no_call_expression":
                    builder.user(text,permit=False)
                    builder.answer(f"{a} × {b}")
                elif mode=="permission_change":
                    builder.user(text,permit=False)
                    builder.answer("Addition.")
                    builder.user("Now you may use the calculator. Give me the sum.")
                    builder.answer(standard_reply(builder.call(calculate("add",a,b))))
                elif mode=="no_call_after":
                    builder.user(text)
                    obs=builder.call(calculate("add",a,b))
                    builder.answer(standard_reply(obs))
                    builder.user("Repeat the earlier result without using any tools.",permit=False)
                    builder.answer(standard_reply(obs))
                elif mode=="correct_input":
                    builder.user(text)
                    builder.answer(standard_reply(builder.call(calculate("subtract",a,b))))
                    builder.user(f"Correction: the starting amount was {a+z}, but the deduction stays the same.")
                    builder.answer(standard_reply(builder.call(calculate("subtract",a+z,b))))
                elif mode in ("two_calls","convert_chain"):
                    first=calculate("add",a,b) if mode=="two_calls" else convert(a,src,dst)
                    override=recorded_result(first,rng) if index%6==0 else None
                    if override is not None:
                        text+=" Use the fixture's observed first value for the second step."
                    builder.user(text,fixture_for=first if override else None,fixture=override)
                    first_obs=builder.call(first)
                    intermediate=first_obs["data"]["result"]
                    second=calculate("divide",intermediate,z) if mode=="two_calls" else calculate("multiply",intermediate,2)
                    rendered=standard_reply(builder.call(second))
                    builder.answer(rendered+" "+dst if mode=="convert_chain" else rendered)
                elif mode=="transient":
                    call=calculate("multiply",a,b)
                    error=rng.choice(["fixture timeout","service unavailable","fixture rate limit"])
                    builder.user(text,fixture_for=call,fixture={"error":error})
                    first=builder.call(call)
                    builder.answer(standard_reply(first))
                    if index%2==0:
                        builder.user("Try that same call once more now.")
                        builder.answer(standard_reply(builder.call(call)))
                    else:
                        builder.user("Was a numeric result returned? No tools.",permit=False)
                        builder.answer("No numeric result was returned.")
                elif mode=="zero_divisor":
                    builder.user(text)
                    builder.answer(standard_reply(builder.call(calculate("divide",a,0))))
                elif mode=="signed_conversion":
                    builder.user(text)
                    obs=builder.call(convert(neg,src,dst))
                    builder.answer(standard_reply(obs)+" "+dst)
                elif mode=="paired_observation":
                    call=calculate("subtract",a,b)
                    for override in (None,recorded_result(call,rng)):
                        pair=Builder(family)
                        pair.user(text,fixture_for=call if override else None,fixture=override)
                        returned=pair.call(call)
                        pair.answer("The fixture reported "+standard_reply(returned)+".")
                        pair.user("What did that same fixture return? Do not use a tool.",permit=False)
                        pair.answer(standard_reply(returned))
                        yield pair.finish()
                    continue
                yield builder.finish()


def build(seed, internal):
    rng=random.Random(seed+(883 if internal else 137))
    lesson_streams=(
        arithmetic_lessons(rng,INTERNAL_ARITHMETIC if internal else ARITHMETIC,24 if internal else 55),
        conversion_lessons(rng,INTERNAL_CONVERSIONS if internal else CONVERSIONS,15 if internal else 38,internal=internal),
        special_lessons(rng,INTERNAL_SPECIAL if internal else SPECIAL,12 if internal else 32),
    )
    result=[]
    seen=set()
    for stream in lesson_streams:
        for lesson in stream:
            key=digest_text(json.dumps(lesson.history,ensure_ascii=False,sort_keys=True))
            if key not in seen:
                seen.add(key)
                result.append(lesson)
    rng.shuffle(result)
    return result


def records(seed):
    """Training records only. The fitting path never loads the internal transfer lesson set."""
    return build(seed,False)


def examples(seed):
    """Return plain role/text/call/result histories compatible with tool_teaching.examples."""
    return [lesson.history for lesson in records(seed)]


def first_proposal_key(lesson):
    for msg in lesson.history:
        if "call" in msg:
            return json.dumps(msg["call"],sort_keys=True,separators=(",",":"))
    return None


def internal_records(seed):
    # Separate scenarios and phrasings, additionally dropping overlapping first-call
    # signatures even when numeric coincidence is incidental. No global holdout is accessed.
    train=records(seed)
    seen={first_proposal_key(lesson) for lesson in train} - {None}
    train_forms={lesson.family for lesson in train}
    candidates=build(seed,True)
    if train_forms & {lesson.family for lesson in candidates}:
        raise ValueError("Internal form reused in training")
    return [l for l in candidates if first_proposal_key(l) not in seen]
