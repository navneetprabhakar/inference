"""Deterministic fixture-grounding curriculum, explicitly not natural authored chats."""
import hashlib,json,random,sys
from pathlib import Path
from tokenizers import Tokenizer
from sft_common import ROOT,system,call_text,execute,result_answer,encode_episode

def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
    out=ROOT/'data/eight-hour-tool-grounding-v1';out.mkdir(parents=True,exist_ok=True)
    protected=set()
    ev=ROOT/'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2'
    for split in ['development','confirmation']:
        for line in (ev/(split+'.jsonl')).read_text().splitlines():
            for turn in json.loads(line)['turns']:
                for call in turn.get('expected_calls',[]):protected.add(digest(call))
    rng=random.Random(2026110301);tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
    rows=[];seen=set();rejected={'protected_call':0,'duplicate_call':0,'context':0}
    for family in ['calculate','convert','get_weather','lookup_item','search_notes']:
        made=0
        while made<80:
            if family=='calculate':
                op=rng.choice(['add','subtract','multiply','divide']);a,b=rng.randint(11,499),rng.randint(2,47)
                call={'name':family,'arguments':{'op':op,'a':a,'b':b}}
                prompt={'add':f'Use the calculator to add {a} and {b}.','subtract':f'Calculate {a} minus {b} using the tool.','multiply':f'Multiply {a} by {b} with the calculator.','divide':f'Use the calculator for {a} divided by {b}.'}[op]
            elif family=='convert':
                f,t=rng.sample(['m','km','cm'],2);v=rng.randint(21,999)/10
                call={'name':family,'arguments':{'value':v,'from_unit':f,'to_unit':t}}
                prompt=f'Use the conversion tool to change {v} {f} to {t}.'
            else:
                key={'get_weather':'city','lookup_item':'item_id','search_notes':'query'}[family]
                entity={'get_weather':f'Testville-{rng.randint(1000,9999)}','lookup_item':f'ITEM-{rng.randint(10000,99999)}','search_notes':f'project-{rng.randint(1000,9999)} review'}[family]
                call={'name':family,'arguments':{key:entity}}
                prompt={'get_weather':f'Check the test weather fixture for the fictional city {entity}.','lookup_item':f'Look up fixture item {entity}.','search_notes':f'Search the fixture notes for {entity}.'}[family]
            h=digest(call)
            if h in protected:rejected['protected_call']+=1;continue
            if h in seen:rejected['duplicate_call']+=1;continue
            value=execute(call)
            if family=='calculate': follow='Repeat only the numeric result returned by the calculator.';answer=str(value['result'])
            elif family=='convert':follow='Repeat only the converted value and unit from the result.';answer=f"{value['result']} {value['unit']}"
            elif family=='get_weather':follow='What temperature did that test fixture return?';answer=f"The test fixture returned {value['temperature_c']} degrees Celsius."
            elif family=='lookup_item':follow='How many units did the fixture say were in stock?';answer=f"{value['stock']} units."
            else:follow='Which weekday is named in the returned note?';answer=value['note'].rsplit(' ',1)[-1]
            messages=[{'role':'system','content':system([family])},{'role':'user','content':prompt},{'role':'assistant','content':call_text(call)},{'role':'tool','content':json.dumps(value,separators=(',',':'))},{'role':'assistant','content':result_answer(call,value)},{'role':'user','content':follow},{'role':'assistant','content':answer}]
            if encode_episode(tok,messages) is None:rejected['context']+=1;continue
            rows.append({'id':f'deterministic-grounding-{family}-{made:03d}','family':family,'messages':messages,'provenance':{'kind':'deterministic_programmatic_fixture_dialogue','generator':'scripts/prepare_goal_tool_grounding.py','not_natural_authored_conversation':True,'seed':2026110301}});seen.add(h);made+=1
    target=out/'batch-001.jsonl';target.write_text(''.join(json.dumps(r,separators=(',',':'),ensure_ascii=False)+'\n' for r in rows))
    manifest={'records':len(rows),'records_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'families':{x:80 for x in ['calculate','convert','get_weather','lookup_item','search_notes']},'rejected':rejected,'status':'prepared_not_trained','limitations':['Templated fixture curriculum, not 400 independently authored natural conversations.','Fictional entities and local deterministic results only.','Does not establish model quality.']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
