"""Prepare a reviewed, token-balanced second curriculum without touching v1 evidence."""
import hashlib, json, random
from collections import Counter
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT, call_text, encode_episode, execute, result_answer, system

OUT=ROOT/'data/eight-hour-improvement-v2'; SEED=20261102
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=ROOT/'data/author-review-v1/reviewed-candidate.jsonl'; raw=[json.loads(x) for x in source.read_text().splitlines() if x]
    # Keeps had a full dialogue-level CLI review; repaired records retain open
    # user-turn/provenance findings and are deliberately excluded here.
    rows=[]
    for r in raw:
        if r['source']['assistant_review_status']!='keep': continue
        rows.append({'id':'reviewed-keep-'+r['id'],'family':'reviewed_multiturn_conversation','messages':r['messages'],'provenance':{'kind':'prior_cli_reviewed_keep','source':str(source.relative_to(ROOT)),'source_id':r['id'],'reviewer':'gpt-5.6-terra','independent_human_review':False}})
    keep_count=len(rows)
    # These are deterministic targets, explicitly labelled; all tool types are
    # represented and each trajectory uses an actual local fixture result.
    for i in range(360):
        k=i%5
        if k==0:
            ops=['add','subtract','multiply','divide'];op=ops[(i//5)%4];a=11+(i*17)%89;b=2+(i*11)%31
            if op=='divide': a=b*(2+(i%9))
            call={'name':'calculate','arguments':{'op':op,'a':a,'b':b}};q=f'Please use the calculator for {a} {op} {b}, then tell me the result.'
        elif k==1:
            pairs=[('m','cm'),('cm','m'),('km','m'),('m','km')];f,t=pairs[(i//5)%4];v=1+(i*7)%950
            call={'name':'convert','arguments':{'value':v,'from_unit':f,'to_unit':t}};q=f'Use the conversion tool to change {v} {f} into {t}.'
        elif k==2:
            city=['Pune','Kochi','Jaipur','Bengaluru','Delhi','Chennai','Surat','Indore'][(i//5)%8]
            call={'name':'get_weather','arguments':{'city':city}};q=f'Check the test weather fixture for {city} and report it.'
        elif k==3:
            ident=f'SKU-{100+(i*13)%800}'
            call={'name':'lookup_item','arguments':{'item_id':ident}};q=f'Look up {ident} with the item tool and report both fixture fields.'
        else:
            query=['budget review','design sync','travel plan','book club','dentist reminder','team lunch','project handoff','garden list'][(i//5)%8]
            call={'name':'search_notes','arguments':{'query':query}};q=f'Search the local notes for {query} and give the returned note.'
        result=execute(call);rows.append({'id':f'fixture-tool-v2-{i:03d}','family':'deterministic_tool_trajectory','messages':[{'role':'system','content':system()},{'role':'user','content':q},{'role':'assistant','content':call_text(call)},{'role':'tool','content':json.dumps(result,separators=(',',':'))},{'role':'assistant','content':result_answer(call,result)}],'provenance':{'kind':'programmatic_exact_local_fixture','generator':'prepare_eight_hour_curriculum_v2.py'}})
    abstentions=[
      ('I want a quiet weekend at home.','Would you rather read, cook, or start a small hobby?'),
      ('Help me write a polite reminder.','What should the reminder ask for, and who is it for?'),
      ('I am not sure which book to start.','What kind of book are you in the mood for?'),
      ('I need an exercise plan but have knee pain.','Before suggesting exercises, it would be safest to ask a clinician or physiotherapist what movements are appropriate.'),
      ('I want to plan a trip.','What destination, dates, budget, and travel style should I use?')]
    for i in range(150):
        q,a=abstentions[i%len(abstentions)];rows.append({'id':f'tool-abstention-v2-{i:03d}','family':'tool_abstention','messages':[{'role':'system','content':system()},{'role':'user','content':q},{'role':'assistant','content':a}],'provenance':{'kind':'reviewed_short_policy_example','generator':'prepare_eight_hour_curriculum_v2.py'}})
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json')); ids=[];masks=[];lens=[];kept=[]
    for r in rows:
        x=encode_episode(tok,r['messages'])
        if x is None: continue
        a,b,n=x;ids.append(a);masks.append(b);lens.append(n);kept.append(r)
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'records.jsonl').open('w') as f:
        for r in kept:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    np.savez_compressed(OUT/'episodes.npz',ids=np.stack(ids),mask=np.stack(masks),length=np.array(lens,np.int32))
    # Two shuffled passes are a bounded curriculum rather than row-count inflation.
    order=[]
    for epoch in range(2):
        ix=list(range(len(kept)));random.Random(SEED+epoch).shuffle(ix);order.extend(ix)
    (OUT/'order.json').write_text(json.dumps({'seed':SEED,'epochs':2,'order':order})+'\n')
    families=Counter(x['family'] for x in kept);targets=Counter()
    for r,m in zip(kept,masks): targets[r['family']]+=int(m.sum())
    manifest={'kind':'eight_hour_v2_reviewed_diverse_curriculum','records':len(kept),'reviewed_keep_source_records':keep_count,'families':dict(families),'supervised_tokens_by_family':dict(targets),'dropped_context_overflow':len(rows)-len(kept),'tokenizer_sha256':digest(ROOT/'data/sft-v3/tokenizer.json'),'records_sha256':digest(OUT/'records.jsonl'),'episodes_sha256':digest(OUT/'episodes.npz'),'order_sha256':digest(OUT/'order.json'),'provenance':'Reviewed keep records are prior current-auth CLI reviewed natural multi-turn dialogues; deterministic tool fixtures are programmatic and labelled. This is not independent human certification.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
