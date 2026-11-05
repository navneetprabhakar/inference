"""Broader deterministic fixture curriculum. No model-generated labels or real tools."""
import hashlib,json,random,re,difflib
from pathlib import Path
from tokenizers import Tokenizer
from sft_common import ROOT,SCHEMAS,system,call_text,execute,result_answer,encode_episode
from audit_teacher_fixture_trajectories import audit

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def norm(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def main():
 out=ROOT/'data/eight-hour-tool-variants-v1';out.mkdir(exist_ok=False)
 ev=ROOT/'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2';protected=set();prompts=[];pins={}
 for split in ['development','confirmation']:
  p=ev/(split+'.jsonl');pins[split]=hashlib.sha256(p.read_bytes()).hexdigest()
  for line in p.read_text().splitlines():
   r=json.loads(line);prompts.append(norm(r['turns'][0]['user']))
   for turn in r['turns']:
    protected.update(digest(c) for c in turn.get('expected_calls',[]))
 rng=random.Random(2026110371);tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
 rows=[];seen=set();rejected={'protected':0,'duplicate':0,'context':0};counts={'calculate':500,'convert':200,'get_weather':100,'lookup_item':100,'search_notes':100}
 for family,target in counts.items():
  made=attempts=0
  while made<target:
   attempts+=1;assert attempts<10000,'bounded rejection limit'
   if family=='calculate':
    op=rng.choice(['add','subtract','multiply','divide']);a,b=rng.randint(0,100),rng.randint(1,40)
    call={'name':family,'arguments':{'op':op,'a':a,'b':b}}
    wording={'add':[f'Please find the sum of {a} and {b} with the calculation tool.',f'I need a tool calculation: {a} + {b}.',f'Use the available arithmetic tool for {a} plus {b}.'],
    'subtract':[f'With the arithmetic tool, take {b} away from {a}.',f'Please subtract {b} from {a} through the calculation tool.',f'I need a tool calculation: {a} - {b}.'],
    'multiply':[f'I need the product of {a} and {b}; please use the arithmetic tool.',f'Please get a tool result for {a} times {b}.',f'Use the available tool for this expression: {a} * {b}.'],
    'divide':[f'Please find the quotient of {a} and {b} with the arithmetic tool.',f'I need a tool result for {a} / {b}.',f'With the calculation tool, divide {a} by {b}.']}
    prompt=rng.choice(wording[op])
   elif family=='convert':
    f,t=rng.sample(['m','km','cm'],2);v=rng.choice([rng.randint(1,150),rng.randint(1,999)/10])
    call={'name':family,'arguments':{'value':v,'from_unit':f,'to_unit':t}}
    prompt=rng.choice([f'I have a measurement of {v} {f}. Convert it to {t} with the available tool.',f'Please use the unit converter: {v} {f} into {t}.',f'Get a tool conversion from {f} to {t} for the value {v}.'])
   else:
    if family=='get_weather':
     entity=rng.choice(['Alder','Birch','Cedar','Dune','Ember','Fern','Grove','Haven','Ivory','Juniper'])+rng.choice(['port','field','vale','ford','view','bay','hill','wick','ton','mere'])
     key='city';prompt=rng.choice([f'Please retrieve the local weather-fixture result for {entity}.',f'The city name is {entity}. Query its weather using the fixture tool.',f'Fetch the simulated weather for {entity}, please.'])
    elif family=='lookup_item':
     entity=rng.choice(['SKU','PART','ITEM'])+'-'+''.join(rng.choices('ABCDEFGHJKLMNPQRSTUVWXYZ',k=4))+str(rng.randint(1,9));key='item_id'
     prompt=rng.choice([f'Please fetch the item record for {entity} using the fixture.',f'I need the local tool result for item ID {entity}.',f'Query the item fixture with identifier {entity}.'])
    else:
     entity=rng.choice(['garden','music','robotics','reading','painting','volunteer','design','workshop','travel','writing'])+' '+rng.choice(['outline','ideas','checklist','summary','schedule','draft','planning','discussion','practice','budget']);key='query'
     prompt=rng.choice([f'Please run a notes search with the query "{entity}".',f'Query the local notes fixture for the words "{entity}".',f'Find the fixture note matching "{entity}".'])
    call={'name':family,'arguments':{key:entity}}
   h=digest(call)
   if h in seen:rejected['duplicate']+=1;continue
   text=norm(prompt)
   if h in protected or any(difflib.SequenceMatcher(None,text,p,autojunk=False).ratio()>=.85 for p in prompts):rejected['protected']+=1;continue
   value=execute(call)
   follow,answer={'calculate':('What number did that calculation produce?',str(value.get('result'))),
    'convert':('Give me the value and its unit again.',f"{value.get('result')} {value.get('unit')}"),
    'get_weather':('Which city was that result for?',str(value.get('city'))),
    'lookup_item':('Which item identifier did we just look up?',str(value.get('item_id'))),
    'search_notes':('What was the query in that search?',str(value.get('query')))}[family]
   names=list(SCHEMAS);rng.shuffle(names)
   if made%5==0:names=[family]
   messages=[{'role':'system','content':system(names)},{'role':'user','content':prompt},{'role':'assistant','content':call_text(call)},{'role':'tool','content':json.dumps(value,separators=(',',':'))},{'role':'assistant','content':result_answer(call,value)},{'role':'user','content':follow},{'role':'assistant','content':answer}]
   if encode_episode(tok,messages) is None:rejected['context']+=1;continue
   rows.append({'id':f'tool-variants-{family}-{made:04d}','family':family,'training_group':'positive_tools','messages':messages,'provenance':{'kind':'deterministic_programmatic_fixture_dialogue','seed':2026110371,'not_natural_authored_conversation':True}});seen.add(h);made+=1
 p=out/'records.jsonl';p.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
 result=audit([p]);assert not result['errors'],result['errors'];(out/'fixture-context-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 manifest={'records':len(rows),'families':counts,'rejected':rejected,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'protected_sha256':pins,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},'status':'prepared_not_trained','limitations':['Templated programmatic fixture conversations, not independently authored natural dialogues.','Exact call and near first-prompt protected screening; not a semantic independence guarantee.','All model training/evaluation decisions remain separate.']}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'records':len(rows),'rejected':rejected}))
if __name__=='__main__':main()
