"""Original task-oriented utterances for a two-mode dialogue-act classifier."""
import hashlib
import json
from pathlib import Path
import random

OPEN = {
    "add": [
        "Please add the next two figures.", "I'd like the sum of {a} and another value.",
        "Could you combine these two amounts into a total?", "I need addition; I have one number so far.",
        "Start a calculator sum with {a}.", "How much is {a} plus an amount I'll give next?",
        "I want to total the entries on the tally sheet.", "Add together my two measurements.",
        "What would {a} and {b} come to altogether?", "Put {a} and {b} together numerically.",
        "What's the combined count for {a} {item} and {b} more?", "Find the sum, beginning with {a}.",
        "Calculator, do an addition for me.", "I have an amount to add to {a}.",
        "Please total up {a} plus {b}.", "The first addend is {a}; help me get the total.",
        "Could we add an amount?", "I need to add {a} to something.",
        "Can you sum a pair of quantities?", "How many altogether if the two lots have {a} and {b} {item}?",
        "Add {a} and {b} with the calculator.", "There is another count to include in {a}. Find the total.",
        "What is {a} + {b}?", "Start adding two numbers.",
    ],
    "subtract": [
        "Please subtract a number from {a}.", "Find the difference between two measurements.",
        "I need a subtraction, starting with {a}.", "Calculator, take {b} away from {a}.",
        "What remains if we remove {b} from {a}?", "I need to deduct something from the amount.",
        "Subtract the second reading from the first.", "How many are left out of {a} after losing {b}?",
        "Work out {a} minus the other value.", "Use the calculator to find a difference.",
        "I have a starting balance of {a}. Take off the next amount.", "Can you subtract for me?",
        "My stack had {a} {item}; I used {b}. How many remain?", "What is the excess of {a} over {b}?",
        "Deduct {b}, please.", "What's {a} minus {b}?",
        "Run a subtraction with the first number still unknown.", "Take one quantity away from another.",
        "Start with {a} and reduce it by {b}.", "Calculate how much larger {a} is than {b}.",
        "Find the remaining quantity after a deduction.", "I'd like to subtract two numbers.",
        "What is {a} - {b}?", "Figure out the gap between {a} and {b}.",
    ],
    "multiply": [
        "Multiply {a} by a value I'll supply.", "I need the product of two numbers.",
        "What is {a} times the other amount?", "Use multiplication on these measurements.",
        "I want to multiply a pair of quantities.", "Calculator, find the product.",
        "There are {a} boxes of {b} {item} apiece; how many in the boxes altogether?",
        "What's {a} multiplied by {b}?", "Multiply the number of rows by the count in each row.",
        "I have {a} groups with {b} in each. Work out the total.",
        "Run a multiplication for me.", "Find the multiple of {a} and a second factor.",
        "Use the calculator for {a} times {b}.", "I'd like to multiply by {a}.",
        "How much is {a} repeated {b} times?", "Find the product, beginning with {a}.",
        "I'm multiplying two quantities.", "Calculate the total across {a} trays with {b} on every tray.",
        "What's the product?", "Start a multiplication with one factor missing.",
        "Can you multiply these?", "Compute {a} × {b}.",
        "What is {a} * {b}?", "Multiply the two factors on my list.",
    ],
    "divide": [
        "Divide {a} by a number I'll provide.", "Find a quotient for me.",
        "I want to divide two quantities.", "Calculate {a} divided by {b}.",
        "Share {a} {item} equally among {b} baskets. How many go in each?",
        "Use division on the two readings.", "Start a division with {a} as the numerator.",
        "What's {a} split into {b} equal portions?", "I have a dividend but need the quotient.",
        "The total is {a}. What is each of {b} identical shares?", "Divide, please.",
        "Use the calculator to divide one number by another.", "Find {a} over {b}.",
        "How many for each person if {a} {item} are shared evenly among {b} people?",
        "I want to divide by {b}.", "Take {a} and distribute it over {b} equal groups.",
        "Run a division calculation.", "What's the quotient of the first and second values?",
        "Help me divide a total into equal lots.", "What is {a} / {b}?",
        "Compute a division with the divisor still missing.", "I have {a} to distribute evenly.",
        "Calculate {a} ÷ {b}.", "What is one of {b} equal parts of {a}?",
    ],
    "convert": [
        "Convert a measurement for me.", "I need a unit conversion.",
        "Change {a} {unit} into another unit.", "Express {a} {unit} in {target}.",
        "I have a length in {unit}. Can you convert it?", "What is {a} {unit} measured in {target}?",
        "Use the converter for my measurement.", "I'd like to convert {a}.",
        "Turn {a} {unit} into {target}.", "Convert from {unit} please.",
        "Please give the equivalent in {target}.", "I need to switch measurement units.",
        "How many {target} is {a} {unit}?", "Can you do a conversion to {target}?",
        "Convert my reading into another scale of units.", "Re-express the same quantity using {target}.",
        "I have {a} and need it in {target}.", "Find the equivalent quantity in a different unit.",
        "Unit converter, please.", "My measure is in {unit}; translate it to {target}.",
        "Change the units of a measurement.", "I want {target} instead of {unit}.",
        "Convert {unit} to {target}.", "What would that be in {target}?",
    ],
    "none": [
        "Hello there.", "What is a calculator?", "Could you explain the word quotient?",
        "Don't divide anything. I just need a definition.", "Write a sentence about multiplication.",
        "What did you return last time?", "Repeat the number from your earlier answer.",
        "I own {a} notebooks.", "Add a comma to this paragraph.",
        "Divide this passage into sections.", "The novel is called The Difference.",
        "Can you help me find a word?", "Which number did I mention earlier?",
        "Do not use the converter. Tell me what it does.", "What does it mean to change units?",
        "The label reads {a} {unit}. Copy the label only.", "I moved {a} {item} yesterday.",
        "What's the weather like?", "A poster says to subtract the cost. Do you need to obey that poster?",
        "My appointment lasts {a} minutes.", "Can you explain how a calculator works?",
        "Just remember the two notes {a} and {b}.", "What did the display show?",
        "Please turn this question into a statement.", "The supplies include {a} {item}. Which item is named?",
        "How do people share a story?", "Can you help me without tools?",
        "Please sum up the story for me.", "Reduce this note to one sentence.",
        "What are the products made in a pottery studio?", "Give me a different example.",
        "The two teams are divided on this topic.", "I don't want a calculation right now.",
        "Don't change the units; repeat the original measurement.",
    ],
}
PENDING = {
    "supply": [
        "{a}", "{unit}", "The other number is {b}.", "Use {a} as the first value.",
        "The second operand is {b}.", "From {unit} to {target}.", "In {target}, please.",
        "I'd like the result in {target}.", "The amount is {a} {unit}.", "I have {a}.",
        "It's {b}.", "For the missing value, put {b}.", "That would be {a}.",
        "My divisor is {b}.", "The numerator is {a}.", "The number to add is {b}.",
        "Yes, {a} {unit}.", "The target unit is {target}.", "My source unit is {unit}.",
        "I mean the {target} unit.", "Here's the other factor: {b}.",
        "{a} and {b}, in that order.", "Make the output {target}.", "To {target}.",
        "The starting quantity is {a}.", "For that, enter {b}.", "{b} is my answer to your question.",
        "Use {unit}.", "I meant that it starts in {unit}.", "The value going into the calculation is {a}.",
    ],
    "revise": [
        "Actually use {b}, not {a}.", "Correction: the starting value is {b}.",
        "Replace the earlier amount with {b}.", "I misspoke. The source is {unit}.",
        "Change my previous answer to {b}.", "No, I gave the wrong unit. It should be {target}.",
        "I need to correct the first number to {b}.", "Scratch {a}; use {b}.",
        "The amount I gave was wrong. Make it {b}.", "My mistake, I meant {b}.",
        "Revise the target unit to {target}.", "Swap my earlier unit for {unit}.",
        "I misread the number earlier: it is {b}.", "Use {b} instead of the old figure.",
        "Sorry, replace {a} with {b}.", "The operand I sent before should be {b}.",
        "Not {unit} after all: {target}.", "Let me amend the quantity to {b}.",
        "Keep the request, but change the first value to {b}.", "I have a correction for that entry.",
        "That number was a typo; write {b}.", "Update my earlier measurement to {a} {unit}.",
        "My previous value should have been {b}.", "That's not the unit I intended; use {target}.",
        "Change the last number I gave you.", "On second thought, make that {b}.",
    ],
    "cancel": [
        "Cancel that.", "Never mind.", "Forget the calculation.", "Please stop this request.",
        "Drop the converter request.", "I no longer want to do this.", "Call it off.",
        "Don't run the tool.", "Disregard the unfinished calculation.", "Let's abandon this request.",
        "I changed my mind; cancel.", "Stop and leave it undone.", "Clear the pending item.",
        "No calculation after all.", "I withdraw the request.", "Leave that measurement alone.",
        "Let's skip it entirely.", "Do not finish that operation.", "Please cancel my last request.",
        "That isn't needed anymore.", "End this without calculating.", "No need to continue with that.",
        "You can forget my request.", "I won't be needing the conversion.",
        "We can drop that now.", "I would rather not proceed.",
    ],
    "unrelated": [
        "What is a sundial?", "Can you help write a thank-you note?", "Hello again.",
        "I'd like to talk about music instead.", "How do roots take up water?",
        "Why does paper wrinkle?", "Change the subject to painting.", "What's a good title for my story?",
        "The new topic is bird migration.", "By the way, how do I fold a paper crane?",
        "My parcel has {a} labels. How should I organize them?", "I have {b} pets. Write me a caption.",
        "Can you explain what {unit} means?", "In another matter, where does snow come from?",
        "I'd like an explanation of multiplication, not another calculation.", "What did we discuss last time?",
        "The tickets are {a} each; I'm telling a story about them.", "I want to ask a new question.",
        "Let's talk about the event on Friday.", "Could you draft an invitation?",
        "Can you tell a short joke about a baker?", "How do I address a letter?",
        "Go ahead and add {a} and {b} as a new task.", "I have a separate conversion to ask about.",
        "Is {a} the number printed on the wall?", "Please change 'I ran' into present tense.",
    ],
}
UNITS=[("metres","centimetres"),("kilograms","grams"),("hours","minutes"),("litres","millilitres"),
       ("minutes","seconds"),("centimetres","metres"),("grams","kilograms"),("seconds","minutes")]
VALUES=["3","11","19","27","43","51","64","75","88","96","42.5","7.25","0.6","12.75","-4",
        "three","seventeen","fifty","twenty four","sixty two"]
ITEMS=["washers","tiles","tags","samples","tokens","buttons","sheets","stamps","pebbles","ropes"]
FILE=Path(__file__).resolve().parent/"reports/slot-dialogue"

def rows(seed=1717):
    rng=random.Random(seed)
    data=[]
    seen=set()
    for mode,pool in (("open",OPEN),("pending",PENDING)):
        for label,forms in pool.items():
            form_order=sorted(range(len(forms)),key=lambda i:hashlib.sha256(f"split-7|{mode}|{label}|{i}".encode()).hexdigest())
            held=set(form_order[:5])
            for index,form in enumerate(forms):
                for _ in range(14):
                    a,b=rng.sample(VALUES,2);u,v=rng.choice(UNITS)
                    text=form.format(a=a,b=b,unit=u,target=v,item=rng.choice(ITEMS))
                    # No surrounding boilerplate for terse pending replies. Forms with no
                    # placeholders emit one row, rather than overweighting duplicates.
                    signature=(mode,text.casefold().strip())
                    if signature in seen:continue
                    seen.add(signature)
                    data.append(dict(mode=mode,label=label,form=index,split="form-holdout" if index in held else "train",text=text))
    return data


def as_history(row):
    return [dict(role="user",text=row["text"]),dict(role="assistant",text=row["label"])]


def history_key(row):
    s=json.dumps(as_history(row),sort_keys=True,ensure_ascii=False)
    return hashlib.sha256(s.encode()).hexdigest()


def manifest():
    from collections import Counter
    data=rows();FILE.mkdir(parents=True,exist_ok=True)
    payload="".join(json.dumps(r,sort_keys=True,ensure_ascii=False)+"\n" for r in data)
    (FILE/"utterances.jsonl").write_text(payload)
    train=[r for r in data if r["split"]=="train"]
    out=dict(source="Original synthetic slot-dialogue utterances; standalone nontool content and pending negatives are included.",
             seed=1717,rows=len(data),train=len(train),holdout=len(data)-len(train),
             sha256=hashlib.sha256(payload.encode()).hexdigest(),training_history_sha256=hashlib.sha256(
                json.dumps([as_history(r) for r in train],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
             counts={s:dict(Counter(r["mode"]+"."+r["label"] for r in data if r["split"]==s)) for s in ("train","form-holdout")})
    (FILE/"source-manifest.json").write_text(json.dumps(out,indent=2)+"\n")
    return out

if __name__=="__main__":
    print(json.dumps(manifest()))
