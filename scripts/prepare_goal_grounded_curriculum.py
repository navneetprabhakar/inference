"""Programmatic, auditable short grounded dialogues. Not natural teacher authoring."""
import hashlib,json,random,re,string
from collections import Counter
from pathlib import Path
from tokenizers import Tokenizer
from sft_common import ROOT,system,call_text,execute,result_answer,encode_episode

def norm(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    rng=random.Random(2026110307);out=ROOT/'data/eight-hour-grounded-v1';out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():raise RuntimeError('Frozen data already exists')
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));protected=set();evalroot=ROOT/'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2'
    for split in ['development','confirmation']:
        for line in (evalroot/(split+'.jsonl')).read_text().splitlines():protected.add(norm(json.loads(line)['turns'][0]['user']))
    rows=[];seen=set();names=['Asha','Ben','Cora','Dev','Eli','Faye','Gus','Hana','Ivo','Jules','Kira','Luis'];colors=['amber','violet','silver','orange','teal','brown','pink','white'];words=['Maple','Otter','Quartz','Cedar','Falcon','Willow','Pebble','Harbor','Birch','Comet','Linden','Coral']
    def add(family,turns,facts,sys=None):
        messages=([{'role':'system','content':sys}] if sys else [])+turns
        for message in messages: message['content']=message['content'].replace(' a amber',' an amber').replace(' a orange',' an orange').replace(' A amber',' An amber').replace(' A orange',' An orange')
        key=norm(next(m['content'] for m in messages if m['role']=='user'))
        if key in seen or key in protected:return False
        encoded=encode_episode(tok,messages)
        if encoded is None:raise RuntimeError('context overflow')
        seen.add(key);rows.append({'id':f'grounded-{family}-{len(rows):05d}','family':family,'messages':messages,'oracle_facts':facts,'provenance':{'kind':'deterministic_programmatic_grounded_dialogue','generator':'scripts/prepare_goal_grounded_curriculum.py','seed':2026110307,'not_natural_authored_conversation':True}});return True
    def chat(family,u1,a1,u2,a2,facts,sys=None):return add(family,[{'role':'user','content':u1},{'role':'assistant','content':a1},{'role':'user','content':u2},{'role':'assistant','content':a2}],facts,sys)
    for family in ['location_update','numeric_comparison','ordered_items','stated_rule','memo_recall','uppercase_copy','small_arithmetic','polite_rewrite','no_tool_arithmetic','missing_tool_argument','unavailable_calendar','division_error']:
        count=0;target=200 if family not in ['missing_tool_argument','unavailable_calendar','division_error'] else 100
        while count<target:
            good=False
            if family=='location_update':
                person,other=rng.sample(names,2);color,othercolor=rng.sample(colors,2);x,y,z=rng.sample(range(101,999),3)
                u=rng.choice([f'{person} put the {color} token in drawer {x}; {other} put the {othercolor} token in drawer {y}. Where is the {color} token?',f'In our game, drawer {x} contains a {color} token and drawer {y} contains a {othercolor} token. Give the location of the {color} token.',f'My note says: {color} token — drawer {x}; {othercolor} token — drawer {y}. Which drawer holds the {color} one?'])
                good=chat(family,u,f'Drawer {x}.',f'I move the {color} token to locker {z}. Where is it now?',f'Locker {z}.',{'initial':x,'other':y,'updated':z})
            elif family=='numeric_comparison':
                a,b=rng.sample(range(21,499),2);x,y=rng.sample(words,2);small=x if a<b else y
                u=rng.choice([f'Parcel {x} weighs {a} g and parcel {y} weighs {b} g. Which parcel is lighter?',f'I weighed two parcels: {x}, {a} grams; {y}, {b} grams. Name the lighter parcel.',f'The labels show {a} g for {x} and {b} g for {y}. Which has less weight?'])
                good=chat(family,u,f'{small}.','How much lighter is it?',f'{abs(a-b)} g.',{'a':a,'b':b,'names':[x,y]})
            elif family=='ordered_items':
                a,b,c=rng.sample(words,3);tag=rng.randint(100,999)
                u=rng.choice([f'Queue {tag} has this order: {a}, {b}, {c}. Which item follows {b}?',f'For list {tag}, I wrote {a} first, {b} second, and {c} third. What comes immediately after {b}?',f'List {tag}: {a} then {b} then {c}. Name the item after {b}.'])
                good=chat(family,u,f'{c}.',f'Move {a} to the end and give the new order.',f'{b}, {c}, {a}.',{'order':[a,b,c]})
            elif family=='stated_rule':
                required,wrong=rng.sample(colors,2);actual=rng.choice([required,wrong]);person=rng.choice(names);tag=rng.randint(100,999)
                u=rng.choice([f'Game {tag} has one entry rule: the ticket must be {required}. {person} has a {actual} ticket. Does this satisfy the entry rule?',f'Only a {required} ticket permits entry to room {tag}. {person} carries a {actual} ticket. Does it meet the rule?',f'For exercise {tag}, the entry condition is a {required} ticket; {person} has a {actual} one. Is that condition satisfied?'])
                answer=f'Yes. The ticket is {required}.' if actual==required else f'No. A {required} ticket is required.'
                good=chat(family,u,answer,'Which ticket color is required?',f'{required.capitalize()}.',{'required':required,'actual':actual})
            elif family=='memo_recall':
                day,wrong=rng.sample(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],2);tag=rng.randint(10000,99999)
                u=rng.choice([f'The memo says package {tag} arrives on {day}. Does it say {wrong}?',f'For shipment {tag}, the stated arrival day is {day}. Is {wrong} the day in the note?',f'I wrote “package {tag}: {day}”. Did I write {wrong} as its arrival day?'])
                good=chat(family,u,f'No. It says {day}.','Repeat only the arrival day from the note.',day,{'day':day,'wrong_day':wrong,'tag':tag})
            elif family=='uppercase_copy':
                code=''.join(rng.choices(string.ascii_lowercase,k=3))+'-'+str(rng.randint(101,999))+'-'+''.join(rng.choices(string.ascii_lowercase,k=2))
                u=rng.choice([f'Write this code in uppercase, with no extra text: {code}',f'Convert {code} to capital letters. Output only the code.',f'Uppercase the letters in {code}; keep its digits and hyphens unchanged. Return only that code.'])
                good=chat(family,u,code.upper(),'Did the digits change?','No. The digits stayed the same.',{'code':code})
            elif family in ['small_arithmetic','no_tool_arithmetic']:
                a,b=rng.randint(11,89),rng.randint(12,59);c=rng.randint(2,10);total=a+b
                if family=='small_arithmetic':
                    obj=rng.choice(['shells','buttons','marbles','stickers','beads','clips']);u=rng.choice([f'I have {a} {obj} and receive another {b}. How many do I have?',f'Combine a group of {a} {obj} with {b} more. What is the total?',f'There are {a} {obj} in one tray and {b} in another. How many altogether?'])
                    good=chat(family,u,f'{total} {obj}.',f'I give away {c}. How many are left?',f'{total-c} {obj}.',{'a':a,'b':b,'subtract':c,'object':obj})
                else:
                    u=rng.choice([f'Do not use tools. What is {a} plus {b}?',f'Answer directly without calling any tools: add {a} and {b}.',f'No tool calls for this question. Calculate {a} + {b}.'])
                    good=chat(family,u,str(total),'Did you call a tool?','No.',{'a':a,'b':b},system())
            elif family=='polite_rewrite':
                verb,obj=rng.choice([('bring','notebook'),('close','gate'),('clean','shelf'),('return','marker'),('check','label'),('move','chair'),('open','window'),('wash','cup')]);color=rng.choice(colors);when=rng.choice(['before lunch','this evening','after breakfast','before the meeting','tomorrow morning']);command=f'{verb} the {color} {obj} {when}'
                u=rng.choice([f'Rewrite this as a polite question: “{command}”.',f'Make “{command}” into one polite request question.',f'Ask politely in one question instead of ordering: {command}.'])
                good=chat(family,u,f'Could you please {command}?','Is your sentence a question or a statement?','It is a question.',{'command':command})
            elif family=='missing_tool_argument':
                a,b=rng.randint(101,999),rng.randint(101,999);call={'name':'calculate','arguments':{'op':'add','a':a,'b':b}};value=execute(call)
                turns=[{'role':'user','content':f'Use the calculator to add {a} to another number. I have not supplied the other number yet.'},{'role':'assistant','content':'What is the other number?'},{'role':'user','content':f'The other number is {b}.'},{'role':'assistant','content':call_text(call)},{'role':'tool','content':json.dumps(value,separators=(',',':'))},{'role':'assistant','content':result_answer(call,value)}]
                good=add(family,turns,{'a':a,'b':b},system(['calculate']))
            elif family=='division_error':
                a=rng.randint(101,999);call={'name':'calculate','arguments':{'op':'divide','a':a,'b':0}};value=execute(call)
                turns=[{'role':'user','content':f'Try dividing {a} by zero with the calculator and report its response.'},{'role':'assistant','content':call_text(call)},{'role':'tool','content':json.dumps(value,separators=(',',':'))},{'role':'assistant','content':'The calculator reports division by zero. A nonzero divisor is required.'},{'role':'user','content':'Can zero be used as the divisor for a valid division?'},{'role':'assistant','content':'No. Use a nonzero divisor.'}]
                good=add(family,turns,{'a':a,'b':0},system(['calculate']))
            else:
                person=rng.choice(names);hour=rng.randint(8,19);minute=rng.choice([0,15,30,45]);day=rng.choice(['Monday','Wednesday','Friday','Saturday']);time=f'{hour:02d}:{minute:02d}'
                u=rng.choice([f'Is {person} free at {time} on {day}? You do not have their private calendar.',f'Without any access to {person}’s calendar, can you confirm availability for {day} at {time}?',f'Check whether {person} has a private appointment on {day} at {time}. No calendar access has been provided.'])
                good=chat(family,u,'I cannot determine that without the relevant calendar information. Please share the appointments for that time.','Can the available fixture tools check that private calendar?','No. None of these tools provides access to the private calendar.',{'person':person,'day':day,'time':time},system())
            count+=int(good)
    path=out/'batch-001.jsonl';path.write_text(''.join(json.dumps(r,separators=(',',':'),ensure_ascii=False)+'\n' for r in rows))
    manifest={'records':len(rows),'families':dict(Counter(r['family'] for r in rows)),'records_sha256':digest(path),'generator_sha256':digest(Path(__file__)),'seed':2026110307,'status':'prepared_not_trained','protected_opening_exact_overlap':0,'limitations':['Programmatic templates with varied facts, not natural authored dialogues.','No claim of semantic independence from broad task categories.','No confirmation outputs read or used.']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
