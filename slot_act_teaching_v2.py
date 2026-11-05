"""Second slot-head curriculum. V1 training-only forms plus separate role-contrast examples."""
from pathlib import Path
from hashlib import sha256
import json,random
from slot_act_teaching import OPEN,PENDING,UNITS,VALUES,ITEMS

OUT=Path(__file__).resolve().parent/"reports/slot-dialogue/v2"
TRAIN={
"open":{
"add":"""I'd like an added total.
Please run a sum for me.
I want two amounts added.
Join the two amounts and tell me their total.
How many in both piles altogether?
Can you work out the sum of two counts?
What's the total once both amounts are included?
I want to add a missing quantity to {a}.
Plus another {b}, please calculate the total.
Compute the sum of {a} and a second amount.
Can I get a total for {a} {item} and another batch?
I have two addends. Please calculate with them.""",
"subtract":"""I want two amounts subtracted.
Please run a difference calculation.
Find how much is left after taking some away.
What is the remainder after we remove the second count?
Can you work out how much less the second number is?
Take the second measurement off the first.
I need to find how far apart two counts are.
Minus {b} from my original total.
What remains of {a} once another amount is taken away?
I want the difference for {a} and a second value.
Deduct a missing charge from the total.
Please calculate a subtraction.""",
"multiply":"""I want two amounts multiplied.
Please run a product calculation.
Find how many across equal groups.
What's the total when each group has the same count?
Could you work out how many across all the rows?
There are {a} equal batches. Calculate their combined amount from the size of each batch.
Do {a} times a second value.
Use the factors to get the product.
I need one number scaled by a second one.
Product of {a} with another value, please.
Could we multiply two readings?
I want to use times rather than plus.""",
"divide":"""I want two amounts divided.
Please run a quotient calculation.
Work out the size of one equal share.
If we split a total evenly what's the amount per share?
Can you find how many each receives?
Take the total over the number of slots.
Divide the dividend by a second value.
Use {a} and a divisor to get a quotient.
I need the per-person share from a common total.
How many in one lot when {a} is shared evenly?
Compute the number per unit by division.
I want to use division rather than multiplication.""",
"convert":"""I'd like an equivalent measurement in a different unit.
Please change from one unit to another.
Can you work a unit conversion for me?
Express this distance in different units.
I want the corresponding amount measured in {target}.
Please translate a measurement from {unit}.
I'm using a different measuring unit; what is the equivalent?
Take a measurement in {unit} and put it in {target}.
Translate {a} {unit} into another unit.
Show the equivalent quantity with {target} as the output.
Could the converter take a measurement?
Can we change from {unit} into {target}?""",
"none":"""Explain what doing a sum means.
Tell me the meaning of a quotient without doing a calculation.
What do people mean by a unit of length?
Why do people learn multiplication?
Please don't add the numbers. I just want them copied.
I have two choices; I want a suggestion, not arithmetic.
Do not convert anything here.
Rewrite the phrase add a little color.
How would I spell divide?
I would like a summary of a book.
The sign says use the product. Is that an instruction?
I have {a} minutes free. What should I read?
Add a heading to this letter.
Remove a word from the sentence.
Which tool did you say you used earlier?
Could you repeat what the calculator showed before?""",
},
"pending":{
"supply":"""My unit is {unit}.
I'd like {target} as the output.
My input is in {unit}.
The value to enter is {a}.
Put {a} in the missing place.
The field you're asking about is {b}.
{unit} is the starting unit.
{target} is where I want to end up.
For the output, {target}.
For the input, {unit}.
My supplied unit: {unit}.
The missing number is {b}.
The figure you still need is {a}.
I'm giving you {b}.
I'd put {b} there.
That quantity is {b}.
Use {a} for that slot.
The right-hand operand is {b}.
In this case it is {a} {unit}.
My answer to that is {target}.
I want the target unit to be {target}.
The target is {target}.
The source is {unit}.
The measurement I have is {a} {unit}.
I have {a} {unit} and need {target}.
The remaining one should read {b}.
Start with {a}.
By {b}.
From {unit}.
To {target}, thanks.
Yes: {a}.
{a} {unit}.""",
"revise":"""Change the unit I already gave to {unit}.
Instead of {a}, I now want {b}.
Rather than {unit}, use {target}.
Correct my earlier slot to {b}.
I want to revise the answer I just supplied.
The previous value wasn't right.
That was the wrong operand; it is {b}.
No, the earlier input should say {unit}.
I need to amend that previous value.
Don't use the old number. It should be {b}.
Actually, replace the first entry with {b}.
Let me update the number already on file.
I need to revise that target unit to {target}.
Sorry, switch my earlier answer to {b}.
The input I just supplied was a mistake.
Change it; {b} is what I meant.
Replace the source that I just gave you rather than filling a new slot.
Use {target} instead this time.
The last unit I entered needs correcting.
Switch the earlier reading from {a} to {b}.
Let's modify that filled slot.
Discard {a} but keep working on the same request with {b}.
I meant {b}, not {a}.
Amend the source unit; I entered it incorrectly.
Make the previous amount {a} {unit} instead.
I typed the wrong thing earlier. The right value is {b}.
I misunderstood; revise the second operand to {b}.
Please substitute {target} for the unit already entered.
That earlier reply was in error.
Correction to what I just said: {b}.""",
"cancel":"""Cancel this operation.
Scratch the whole request.
Drop the unfinished task altogether.
Please stop collecting details.
No more on this calculation, thanks.
Let's leave this undone.
I don't need that tool run now.
Abandon the request completely.
Never mind about the tool.
Forget this particular operation.
I am cancelling that pending calculation.
I'm not going ahead.
Stop, please; don't carry this out.
Clear this unfinished conversion.
Withdraw the calculation I asked for.
I no longer need it.
We won't finish this tool request.
Leave it there, no need to continue.
I want to end the request here.
Forget about calculating anything.
No need to work it out after all.
I take back the request.
Stop before calling anything.
I don't want a result any more.
That's cancelled, thanks.
Let's leave this calculation unfinished.""",
"unrelated":"""Let me ask about a poem instead.
I have a different question about a poster.
What is a noun?
Could you edit my note?
What do you think of this title?
I want to switch subjects to gardening.
On another subject, how do moths find light?
Do you know what a sundial is?
I'd rather hear a short story.
Now help me plan a craft activity.
Tell me what my message means.
Can you explain this sentence?
Different topic: I want some writing help.
I'm curious about stars.
What did my earlier note say?
How can I sort my notebooks?
Forget the arithmetic and tell me about paper.
I have a separate task: calculate {a} plus {b}.
Let's start a different request to convert {a} {unit}.
The game uses {a} cards. Tell me how to describe it.
I'm actually asking about a letter rather than a number.
What does the word metre mean?
The label says {a} {unit}. Can you reread the printed text?
Please greet me.
Could you restate the last sentence?
I want an example of a simile.""",
}}
# New forms were written before fitting the second model. No v1 holdout or sealed wording.
PANEL={
"open":{
"add":"""I need to add my first count to a second one.
Get me the sum; I'll supply the figures shortly.
Can the calculator total two batches of {item}?
I'd like the amount from {a} plus a second number.
Show the combined total of these two counts.
Please put {a} and {b} into an addition.
Taking both lots together, how many is that?
Work out the sum of {a} with the next figure.""",
"subtract":"""I'd like the value after subtracting {b}.
Get the difference; I'll send the numbers shortly.
I want to know how many {item} remain once some are removed.
Find the result of deducting one figure from the other.
How many are left after {b} are taken away from {a}?
Please put {a} minus another figure through the calculator.
Take the second amount off the first.
Calculate the gap between my two measurements.""",
"multiply":"""I need one count multiplied by a second.
Get the product; the values will follow.
Can the calculator give a total for equal groups of {item}?
I'd like {a} times a second factor.
How many across {a} containers if each contains {b}?
Please multiply the entries from two columns.
The factor is {a}, and I need multiplication.
What is the total for {a} identical packs of {b}?""",
"divide":"""I need one value divided by a second.
Get the quotient; I'll send the quantities shortly.
Please split our supply into equal parts and find one part.
I'd like {a} divided by another figure.
How many per container if {a} {item} are shared evenly among {b}?
Use the calculator for a division.
The divisor is {b}; help me find one share.
Find the result of dividing the two entries.""",
"convert":"""I'd like {a} expressed in another measurement unit.
Can the unit converter help me with a value?
What's the equivalent quantity in {target}?
Please convert a measurement; I haven't given both units yet.
The input is in {unit}. I need a unit change.
Recalculate my measurement in {target}.
How much is {a} {unit} when stated in {target}?
I need the converter to switch units.""",
"none":"""Can you define the term product?
Explain the idea of adding without using a tool.
No calculation. Just echo the original value.
I want to add a title to my poem.
Which unit did I give earlier?
I have {a} parcels; that's a detail in my story.
Why does a calculator have so many buttons?
Could you divide this list into categories?""",
},
"pending":{
"supply":"""For the amount you requested, use {a}.
I'd like {target} for the output unit.
The unit that I am starting with is {unit}.
My second value is {b}.
Use {b} for the empty slot.
It's {a} {unit} on my label.
I'm giving the missing quantity now: {b}.
That should be in {target}.""",
"revise":"""Amend the value I sent before to {b}.
Use {b} in place of {a}.
I got the starting unit wrong. Make it {unit}.
My previous entry needs to be changed.
That was a typo; the second value is {b}.
No, I want to correct the target unit to {target}.
Switch the earlier amount to {b}.
I entered {a} incorrectly. Replace it with {b}.""",
"cancel":"""Forget the whole pending calculation.
I won't be proceeding with that request.
Please abandon this conversion.
Never mind the unfinished calculation.
Stop working on that tool request.
Don't finish this one after all.
Remove the pending request completely.
Call off that operation, please.""",
"unrelated":"""Actually I have a question about books.
Can you explain what a rhyme is?
New topic: help me organize a shelf.
I want to talk about the concert.
Compose a line about a quiet river.
I have {a} sketches; which one should I frame?
Can we try a separate addition of {a} and {b}?
What does the word unit mean here?""",
}}
def materialize():
    rng=random.Random(2801);data=[];seen=set()
    for split,source in [('train',TRAIN),('challenge',PANEL)]:
        for mode,labels in source.items():
            for label,forms in labels.items():
                for i,f in enumerate(forms.splitlines()):
                    for _ in range(12 if split=='train' else 6):
                        a,b=rng.sample(VALUES,2);u,v=rng.choice(UNITS)
                        text=f.format(a=a,b=b,unit=u,target=v,item=rng.choice(ITEMS))
                        if (mode,text.casefold()) in seen:continue
                        seen.add((mode,text.casefold()))
                        data.append(dict(index=len(data),user=text,mode=mode,label=label,split=split,form=f"v2-{label}-{split}-{i}"))
    return data

if __name__=='__main__':
    d=materialize();s=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in d)
    (OUT/'custody-input.jsonl').write_text(s)
    print(len(d),sha256(s.encode()).hexdigest())
