"""Synthetic offline conversations. Teacher calls use the same validated local adapters as serving."""
import random
from tools import execute

OPERATIONS = {
    "add": ["Add {a} and {b}.","How much is {a} plus {b}?","What is the sum of {a} and {b}?",
            "I packed {a} parcels and then {b} more. Find the total.","Calculate {a} + {b}.",
            "What's the combined count for {a} and {b}?","Use the calculator to add {a} to {b}.",
            "The two readings are {a} and {b}. Please add them."],
    "subtract": ["Subtract {b} from {a}.","How much is {a} minus {b}?","Take {b} away from {a}.",
                 "I started with {a} pieces and gave away {b}. How many remain?","Calculate {a} - {b}.",
                 "Find the difference: {a} less {b}.","Use the calculator for {a} minus {b}."],
    "multiply": ["Multiply {a} by {b}.","What is {a} times {b}?","Find the product of {a} and {b}.",
                 "There are {a} packs of {b} cards. How many cards altogether?","Calculate {a} * {b}.",
                 "Use the calculator to multiply {a} and {b}.","{a} shelves hold {b} books each. Count the books."],
    "divide": ["Divide {a} by {b}.","What is {a} divided by {b}?","Find the quotient of {a} and {b}.",
               "Share {a} counters equally among {b} players. How many each?","Calculate {a} / {b}.",
               "Use the calculator for {a} divided by {b}."],
}
UNITS = [('m','metres','cm','centimetres'),('km','kilometres','m','metres'),('kg','kilograms','g','grams'),
         ('l','litres','ml','millilitres'),('h','hours','min','minutes'),('min','minutes','s','seconds'),
         ('day','days','h','hours'),('m','meters','mm','millimeters')]
CONVERSIONS=["Convert {v} {s} to {d}.","How many {d} are in {v} {s}?","Use the converter on {v} {s}, in {d}.",
             "Express {v} {s} in {d}.","I measured {v} {s}. Give me that in {d}.",
             "Change {v} {s} into {d} using unit conversion."]


def u(text):
    return dict(role='user',text=text)


def reply(text):
    return dict(role='assistant',text=text)


def proposal(name,args):
    return dict(role='assistant',call=dict(name=name,arguments=args))


def display(value):
    return str(int(value)) if int(value)==value else f"{value:.9g}"


def observed(name,args,call_id,fixture=None):
    try:
        value=execute(name,args) if fixture is None else fixture
        payload={"name":name,"id":call_id,"result":value}
        answer=display(value)
    except ValueError as e:
        payload={"id":call_id,"error":str(e)}
        answer="I couldn't complete the calculation: "+str(e)+"."
    return [proposal(name,args),dict(role='tool',result=payload),reply(answer)]


def examples(seed):
    rng=random.Random(seed+3)
    chats=[]
    for i in range(6400):
        op=list(OPERATIONS)[i%4]
        a,b=rng.randint(1,99),rng.randint(1,19)
        if op=='divide':
            a=b*rng.randint(1,15)
            if i%29==0:
                b=0
        args=dict(op=op,a=a,b=b)
        ask=rng.choice(OPERATIONS[op]).format(a=a,b=b)
        if i%7==0:
            ask="Please use the calculator. "+ask
        fixture=rng.randint(10,99) if i%7==2 and b!=0 else None
        h=[u(ask),*observed('calculate',args,'c1',fixture)]
        if i%3==0 and b:
            value=h[-2]['result']['result']
            if i%2==0:
                h.extend([u(rng.choice(["What was the result?","Repeat that number.","What did the calculator return?"])),reply(display(value))])
            else:
                extra=rng.randint(1,9)
                h.extend([u(rng.choice(["Now add {b} to that.","Add {b} to that result.","Increase that by {b}."]).format(b=extra)),
                          *observed('calculate',dict(op='add',a=value,b=extra),'c2')])
        chats.append(h)
    for i in range(2400):
        src,s,dst,d=rng.choice(UNITS)
        if i%2:
            src,dst,s,d=dst,src,d,s
        value=rng.choice([.5,1,1.5,2.5,10,20,60,100,120,500,1000,rng.randint(1,99)])
        args={'value':value,'from':src,'to':dst}
        ask=rng.choice(CONVERSIONS).format(v=value,s=s,d=d)
        h=[u(ask),*observed('convert',args,'c1')]
        if i%3==0:
            h.extend([u("What was the original unit?"),reply(s)])
        chats.append(h)
    for i in range(420):
        n=rng.randint(1,99)
        h=rng.choice([
            [u(f"Convert {n} metres."),reply("Which unit should I convert metres to?")],
            [u("I want to divide two numbers."),reply("Which numbers would you like to divide?")],
            [u("What does a calculator do?"),reply("It performs arithmetic on numbers.")],
            [u(f"Write the number {n} without using a tool."),reply(str(n))],
            [u("Explain what a converter does. Don't call one."),reply("It expresses a measurement in another unit.")],
            [u("Did you send my message?"),reply("I haven't sent a message.")],
        ])
        chats.append(h)
    return chats
