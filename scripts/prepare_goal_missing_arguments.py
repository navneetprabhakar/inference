"""Missing arguments for four fixture tools, with real executed continuation labels."""
import hashlib,json,random,re,difflib
from pathlib import Path
from tokenizers import Tokenizer
from sft_common import ROOT,SCHEMAS,system,execute,result_answer,call_text,encode_episode
from audit_teacher_fixture_trajectories import audit

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def norm(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def main():
 out=ROOT/'data/eight-hour-missing-arguments-v1';out.mkdir(exist_ok=False);rng=random.Random(2026110393);tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));rows=[];protected=set();prompts=[];pins={}
 ev=ROOT/'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2'
 for split in ['development','confirmation']:
  p=ev/(split+'.jsonl');pins[split]=hashlib.sha256(p.read_bytes()).hexdigest()
  for line in p.read_text().splitlines():
   r=json.loads(line);prompts.append(norm(r['turns'][0]['user']))
   for t in r['turns']:protected.update(digest(c) for c in t.get('expected_calls',[]))
 for family in ['get_weather','lookup_item','search_notes','convert']:
  for i in range(30):
   if family=='get_weather':
    city=['Alder','Birch','Cedar','Dune','Elm','Fern'][i%6]+['port','field','haven','glen','ridge'][i//6]
    q=['I want to use the weather fixture, but I have not named a city.','Please check a city with the weather tool. Which detail do you need first?','Could you fetch a test weather report? I still need to tell you the place.'][i%3]
    ask='Which city should I use?';follow='Use '+city+'.';call={'name':family,'arguments':{'city':city}}
   elif family=='lookup_item':
    ident='PART-M'+str(700+i);q=['I want an item lookup, but I have not given an item ID.','Could you retrieve an item record? I have not specified which item.','Please use the item fixture after I give you its identifier.'][i%3]
    ask='What is the item ID?';follow='The item ID is '+ident+'.';call={'name':family,'arguments':{'item_id':ident}}
   elif family=='search_notes':
    query=['club','garden','music','design','robotics','reading'][i%6]+' '+['outline','planning','ideas','discussion','summary'][i//6]
    q=['I need a notes search, but I have not said what to search for.','Could you find a note once I tell you the search words?','Please search the notes fixture; I still need to provide the query.'][i%3]
    ask='What words should I search for?';follow='Search for '+query+'.';call={'name':family,'arguments':{'query':query}}
   else:
    original,target=rng.sample(['m','cm','km'],2);value=20+i
    q=f'Convert {value} into {target} using the tool. I have not given the original unit yet.';ask='What is the original unit?';follow='The original unit is '+original+'.';call={'name':family,'arguments':{'value':value,'from_unit':original,'to_unit':target}}
   assert digest(call) not in protected
   assert not any(difflib.SequenceMatcher(None,norm(q),p,autojunk=False).ratio()>=.85 for p in prompts)
   value=execute(call);names=list(SCHEMAS);rng.shuffle(names)
   messages=[{'role':'system','content':system(names)},{'role':'user','content':q},{'role':'assistant','content':ask},{'role':'user','content':follow},{'role':'assistant','content':call_text(call)},{'role':'tool','content':json.dumps(value,separators=(',',':'))},{'role':'assistant','content':result_answer(call,value)}]
   assert encode_episode(tok,messages) is not None
   rows.append({'id':f'missing-argument-{family}-{i:03d}','family':'missing_tool_argument','training_group':'tool_boundaries','messages':messages,'provenance':{'kind':'deterministic_programmatic_fixture_dialogue','seed':2026110393,'not_natural_authored_conversation':True}})
 p=out/'records.jsonl';p.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));result=audit([p]);assert not result['errors'];(out/'fixture-context-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 manifest={'state':'prepared_not_trained','records':len(rows),'protected_sha256':pins,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},'limitations':['Programmatic templates, not independently authored natural conversations.','First-turn prompts intentionally repeat with different supplied arguments on follow-up.','Protected call and near first-prompt checks are not semantic independence certification.']}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'records':len(rows),'fixture_results':result['fixture_results_checked']}))
if __name__=='__main__':main()
