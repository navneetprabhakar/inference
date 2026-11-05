"""Create a compact, provenance-labelled curriculum for the authorized run.

Arithmetic and tool fixture targets are computed locally; non-tool wording below
is deliberately short, reviewed seed text rather than claimed teacher output.
"""
import hashlib, json, random
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT, call_text, encode_episode, execute, result_answer, system

OUT=ROOT/'data/eight-hour-improvement-v1'
SEED=20261102

def add(rows, ident, family, messages, provenance):
    rows.append({'id':ident,'family':family,'messages':messages,'provenance':provenance})

def main():
    rng=random.Random(SEED); rows=[]
    # Exact targets are programmatic arithmetic, explicitly labelled as such.
    ops=[('add','plus',lambda a,b:a+b),('subtract','minus',lambda a,b:a-b),('multiply','times',lambda a,b:a*b)]
    for i in range(240):
        op,word,fn=ops[i%len(ops)];a=7+(i*13)%83;b=3+(i*17)%61;answer=fn(a,b)
        phr=[f'What is {a} {word} {b}?',f'Calculate {a} {op} {b}.',f'I have {a} and add {b}. What is the total?' if op=='add' else f'Compute {a} {word} {b}.'][i%3]
        add(rows,f'programmatic-math-{i:03d}','arithmetic',[{'role':'user','content':phr},{'role':'assistant','content':f'The answer is {answer}.'}],{'kind':'programmatic_exact_arithmetic','generator':'prepare_eight_hour_curriculum.py'})
    facts=[
      ('The library opens at 09:00 and closes at 17:00. Is it open at 08:30?','No. It opens at 09:00.'),
      ('The parcel note says delivery is Tuesday, not Monday. Which day is delivery?','Delivery is Tuesday.'),
      ('A recipe makes 8 muffins with 2 cups of flour. How much flour for 4 muffins?','You need 1 cup of flour.'),
      ('Mina has 12 stickers and gives away 5. How many remain?','7 stickers remain.'),
      ('The train leaves at 16:40 and takes 20 minutes. When does it arrive?','It arrives at 17:00.'),
      ('A 300 cm ribbon is how many metres?','300 cm is 3 metres.'),
      ('The museum is closed on Monday. Can you visit on Monday?','No. The museum is closed on Monday.'),
      ('A meeting has 18 people split equally across 3 tables. How many per table?','There are 6 people at each table.'),
    ]
    rewrites=[
      ('Rewrite politely in one sentence: Send the report now.','Could you please send the report now?'),
      ('Rewrite politely in one sentence: Fix this today.','Could you please fix this today?'),
      ('Rewrite clearly in one sentence: The thing is late.','The delivery is late.'),
    ]
    follow=[
      ('I want a vegetarian lunch.','Would you prefer something light, like a salad, or something more filling?'),
      ('Please schedule the meeting next week.','Which day, time, and time zone should I use?'),
      ('I forgot whether I took my medicine. Should I take another dose?','Do not take an extra dose until you check the label or ask a pharmacist or clinician.'),
      ('I need help choosing a book.','What kind of book are you in the mood for: fiction, nonfiction, or something else?'),
    ]
    for i in range(240):
        pool=(facts+rewrites+follow);q,a=pool[i%len(pool)]
        add(rows,f'reviewed-basic-{i:03d}','grounded_or_conversation',[{'role':'user','content':q},{'role':'assistant','content':a}],{'kind':'reviewed_seed_text_with_repetition','generator':'prepare_eight_hour_curriculum.py'})
    # Deterministic local-tool trajectories: call, actual fixture result, grounded final.
    for i in range(520):
        if i%2==0:
            op,word,_=ops[i%len(ops)];a=4+(i*7)%71;b=2+(i*11)%43
            call={'name':'calculate','arguments':{'op':op,'a':a,'b':b}};q=f'Use the calculator to find {a} {word} {b}.'
        else:
            value=1+(i*3)%90;pair=[('m','cm'),('cm','m'),('km','m')][i%3];call={'name':'convert','arguments':{'value':value,'from_unit':pair[0],'to_unit':pair[1]}};q=f'Convert {value} {pair[0]} to {pair[1]} using the conversion tool.'
        result=execute(call)
        add(rows,f'fixture-tool-{i:03d}','tool_trajectory',[{'role':'system','content':system(['calculate','convert'])},{'role':'user','content':q},{'role':'assistant','content':call_text(call)},{'role':'tool','content':json.dumps(result,separators=(',',':'))},{'role':'assistant','content':result_answer(call,result)}],{'kind':'programmatic_deterministic_fixture_trajectory','generator':'prepare_eight_hour_curriculum.py'})
    # Tool abstentions teach the system prompt boundary without fabricated calls.
    for i in range(80):
        q,a=follow[i%len(follow)]
        add(rows,f'tool-abstain-{i:03d}','tool_abstention',[{'role':'system','content':system(['calculate','convert'])},{'role':'user','content':q},{'role':'assistant','content':a}],{'kind':'reviewed_seed_text_with_tool_abstention','generator':'prepare_eight_hour_curriculum.py'})
    rng.shuffle(rows); OUT.mkdir(parents=True,exist_ok=True)
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json')); ids=[];masks=[];length=[];kept=[]
    for r in rows:
        x=encode_episode(tok,r['messages'])
        if x is None: raise RuntimeError('context overflow '+r['id'])
        a,b,n=x;ids.append(a);masks.append(b);length.append(n);kept.append(r)
    with (OUT/'records.jsonl').open('w') as f:
        for r in kept:f.write(json.dumps(r,separators=(',',':'))+'\n')
    np.savez_compressed(OUT/'episodes.npz',ids=np.stack(ids),mask=np.stack(masks),length=np.array(length,np.int32))
    # 10 shuffled curriculum passes, length-bucketed later by the trainer.
    order=[]
    for epoch in range(10):
        ix=list(range(len(kept)));random.Random(SEED+epoch).shuffle(ix);order += ix
    (OUT/'order.json').write_text(json.dumps({'seed':SEED,'order':order,'epochs':10})+'\n')
    h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    fam={};
    for r in kept:fam[r['family']]=fam.get(r['family'],0)+1
    (OUT/'manifest.json').write_text(json.dumps({'kind':'eight_hour_authorized_curriculum','records':len(kept),'families':fam,'tokenizer_sha256':h(ROOT/'data/sft-v3/tokenizer.json'),'records_sha256':h(OUT/'records.jsonl'),'episodes_sha256':h(OUT/'episodes.npz'),'order_sha256':h(OUT/'order.json'),'provenance':'Programmatic exact arithmetic and deterministic fixtures are labelled per record; reviewed seed text is not represented as natural teacher diversity.'},indent=2)+'\n')
if __name__=='__main__':main()
