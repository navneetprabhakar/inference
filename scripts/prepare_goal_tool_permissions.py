"""Explicit no-tool and supplied-fact episodes; programmatic, not natural authoring."""
import hashlib,json,random,re,difflib
from pathlib import Path
from fractions import Fraction
from tokenizers import Tokenizer
from sft_common import ROOT,SCHEMAS,system,execute,encode_episode
from audit_teacher_fixture_trajectories import audit

def norm(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def main():
 out=ROOT/'data/eight-hour-tool-permissions-v1';out.mkdir(exist_ok=False)
 ev=ROOT/'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2';protected=[];pins={}
 for split in ['development','confirmation']:
  p=ev/(split+'.jsonl');pins[split]=hashlib.sha256(p.read_bytes()).hexdigest()
  protected += [norm(json.loads(s)['turns'][0]['user']) for s in p.read_text().splitlines()]
 rng=random.Random(2026110392);tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));rows=[];seen=set();rejected=0
 prefixes=['Keep all tools disabled for this reply.','Answer without invoking any tool.','Do not access a tool for this request.','Leave the available tools unused.','I do not permit tool calls for this answer.']
 for family in ['calculate','convert','get_weather','lookup_item','search_notes']:
  for i in range(40):
   a,b=rng.randint(2,39),rng.randint(2,19)
   if family=='calculate':
    op=['add','subtract','multiply','divide'][i%4];call={'name':'calculate','arguments':{'op':op,'a':a,'b':b}};v=execute(call)['result']
    question={'add':f'What is {a} plus {b}?','subtract':f'What is {a} minus {b}?','multiply':f'What is {a} times {b}?','divide':f'What is {a} divided by {b}?'}[op]
    answer=('Approximately ' if op=='divide' and Fraction(str(v))!=Fraction(a,b) else '')+f'{v}.'
   elif family=='convert':
    f,t=rng.sample(['cm','m','km'],2);v=execute({'name':'convert','arguments':{'value':a,'from_unit':f,'to_unit':t}})
    question=f'Express {a} {f} in {t}.';answer=f"{v['result']} {t}."
   elif family=='get_weather':
    city=f'Exampleville-{300+i}'
    if i%2:
     question=f'The forecast text I pasted says {city}: {a} degrees Celsius, cloudy. Summarize only that information.'
     answer=f'The supplied forecast says {city} is {a} degrees Celsius and cloudy.'
    else:
     question=f'Can you check the current weather for {city}? I have not supplied a forecast.'
     answer='I cannot check current weather without weather data. If you share a current forecast for that place, I can help interpret it.'
   elif family=='lookup_item':
    item=f'PART-N{400+i}'
    if i%2:
     question=f'The item card for {item} says price {a}, stock {b}. How many units are listed in stock?';answer=f'{b} units are listed in stock.'
    else:question=f'Could you retrieve the price for item {item}? I have not provided its record.';answer='I cannot retrieve the item record without using a tool. Please share the record if you want me to read its price.'
   else:
    query=f'club {500+i} minutes'
    if i%2:
     day=['Tuesday','Wednesday','Friday'][i%3];question=f'My pasted note says the {query} meeting is on {day}. Which day does it give?';answer=f'{day}.'
    else:question=f'Can you retrieve the note matching "{query}"? The note is not included here.';answer='I cannot retrieve that note without using a tool. Paste the note here and I can help read it.'
   prompt=prefixes[i%len(prefixes)]+' '+question;text=norm(prompt)
   if text in seen or any(difflib.SequenceMatcher(None,text,p,autojunk=False).ratio()>=.85 for p in protected):rejected+=1;continue
   names=list(SCHEMAS);rng.shuffle(names)
   messages=[{'role':'system','content':system(names)},{'role':'user','content':prompt},{'role':'assistant','content':answer},{'role':'user','content':'Did you invoke a tool for that answer?'},{'role':'assistant','content':'No. I did not call a tool.'}]
   assert encode_episode(tok,messages) is not None
   assert not any(m['role']=='tool' or '<|tool_call|>' in m['content'] for m in messages if m['role']!='system')
   rows.append({'id':f'permission-no-tool-{family}-{i:03d}','family':'explicit_tool_prohibition','training_group':'tool_boundaries','messages':messages,'provenance':{'kind':'deterministic_programmatic_permission_dialogue','generator':'scripts/prepare_goal_tool_permissions.py','seed':2026110392,'not_natural_authored_conversation':True}});seen.add(text)
 p=out/'records.jsonl';p.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
 result=audit([p]);assert not result['errors'];(out/'fixture-context-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 manifest={'state':'prepared_not_trained','records':len(rows),'protected_rejections':rejected,'protected_sha256':pins,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},'limitations':['Programmatic training episodes; no claim of independently authored natural conversations.','No actual tools are permitted in these dialogue trajectories. Offline arithmetic label construction is separate.','Prohibition does not force refusal when the answer is computable or supplied by the user.','Lexical protected screen is not semantic independence certification.']}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'records':len(rows),'protected_rejections':rejected}))
if __name__=='__main__':main()
