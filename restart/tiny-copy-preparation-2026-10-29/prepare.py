"""CPU-only tiny-copy proposal; no model loading or optimizer execution."""
import json,random,sys,hashlib,collections,sqlite3
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(P.parent/'phase-a-2026-10-28'))
from build import serial,sp
FIRST=['Alicia','Boris','Cora','Derek','Elise','Farid','Greta','Hector']
LAST=['Abbott','Barker','Conrad','Dover','Easton','Farrow','Gibson','Holden']
NEW_FIRST=['Inez','Jovan','Kaia','Leif','Mira','Nico','Orla','Soren']
NEW_LAST=['Iverson','Jarvis','Keaton','Linden','Mercer','Norwood','Osborn','Perrin']
def read(p):return json.loads(p.read_text())
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pools():
 names=lambda fs,ls,offset:[fs[i%8]+' '+ls[(i%8+i//8+offset)%8] for i in range(16)]
 times=[f'{3*(i%8):02d}:{7*i%60:02d}' for i in range(16)];minutes=[int(t[3:]) for t in times];newmins=[i for i in range(60) if i not in minutes][:16]
 return {'name':{'fit':names(FIRST,LAST,0),'recombination':names(FIRST,LAST,2),'new_fields':names(NEW_FIRST,NEW_LAST,0)},'time':{'fit':times,'recombination':[f'{3*(i%8):02d}:{minutes[(i+3)%16]:02d}' for i in range(16)],'new_fields':[f'{3*(i%8)+1:02d}:{newmins[i]:02d}' for i in range(16)]}}
def make(f,split,values):
 rows=[]
 for pair in range(8):
  other=values[(pair+3)%8] # Constant across both interventions and always unequal to target.
  for scope in ['simple','distractor']:
   for side,index in [('before',pair),('after',8+(pair+5)%8)]:
    value=values[index]
    if f=='name':target=f'Parcel owner: {value}.';distractor=f'Crate owner: {other}.';q='What is the full name of the parcel owner? Reply with the full name only.'
    else:target=f'Meeting time: {value}.';distractor=f'Delivery time: {other}.';q='What time is the meeting? Reply with HH:MM only.'
    facts=target if scope=='simple' else ' '.join([target,distractor] if pair%2==0 else [distractor,target])
    messages=[{'role':'user','content':facts+' '+q},{'role':'assistant','content':value}];ids,mask=serial(messages)
    rows.append(dict(id=f'{f}-{split}-{pair}-{scope}-{side}',family=f,split=split,pair=f'{f}-{split}-{pair}',scope=scope,side=side,value=value,distractor_value=other,target_first=pair%2==0,messages=messages,ids=ids,mask=mask))
 return rows

def main():
 assert not (P/'freeze.json').exists()
 values=pools();fit=[];dev=[]
 for f in ['name','time']:
  for split,vs in values[f].items():
   assert len(vs)==len(set(vs))==16
   rs=make(f,split,vs);(fit if split=='fit' else dev).extend(rs)
  assert not set(values[f]['fit']) & (set(values[f]['recombination'])|set(values[f]['new_fields']))
  assert not set(values[f]['recombination'])&set(values[f]['new_fields'])
 schedules={}
 for f in ['name','time']:
  indices=[i for i,r in enumerate(fit) if r['family']==f];schedule=[]
  # Each update gets one member per scope and side; rotate independently within each category.
  groups=[[i for i in indices if fit[i]['scope']==scope and fit[i]['side']==side] for scope in ['simple','distractor'] for side in ['before','after']]
  for epoch in range(16):
   decks=[]
   for g,indices_g in enumerate(groups):
    deck=indices_g.copy();random.Random(291031+100*epoch+g).shuffle(deck);decks.append(deck)
   for j in range(8):schedule.append([d[j] for d in decks])
  schedules[f]=schedule
 save('private/fit.json',fit);save('private/transfer.json',dev);save('private/schedules.json',schedules);save('private/value-pools.json',values)
 replay=read(P.parent/'runner-readiness-2026-10-29/replay.json');save('private/replay-indices.json',replay['indices'][:128])
 checks=0;maxcontext=0
 for r in fit+dev:
  ids,mask=serial(r['messages']);assert ids==r['ids'] and mask==r['mask'];assert r['value']!=r['distractor_value'];assert sum(mask)==len(sp.encode(r['value']))+1<=32;assert r['value'] in r['messages'][0]['content'];n=len(serial(r['messages'][:1])[0]);assert n+32<=256;maxcontext=max(maxcontext,n+32);checks+=5
  # Independently extract the explicitly requested fact from the rendered text.
  marker='Parcel owner: ' if r['family']=='name' else 'Meeting time: ';extracted=r['messages'][0]['content'].split(marker)[1].split('.')[0];assert extracted==r['messages'][1]['content'];checks+=1
 for f,s in schedules.items():
  assert len(s)==128;counts=collections.Counter(i for b in s for i in b);assert len(counts)==32 and set(counts.values())=={16};checks+=2
  for b in s:assert len({(fit[i]['scope'],fit[i]['side']) for i in b})==4;checks+=1
 # Validate both-pair factual intervention and shared value across context variants.
 for f in ['name','time']:
  for split in ['fit','recombination','new_fields']:
   for pair in range(8):
    rs=[r for r in fit+dev if r['pair']==f'{f}-{split}-{pair}'];assert len(rs)==4
    for scope in ['simple','distractor']:
     a,b=[r for r in rs if r['scope']==scope];assert a['messages'][0]['content'].replace(a['value'],'TARGET')==b['messages'][0]['content'].replace(b['value'],'TARGET');checks+=1
 assert {r['value'] for r in dev if r['family']=='name' and r['split']=='recombination'}.isdisjoint(values['name']['fit'])
 key=lambda r:tuple(m['content'] for m in r['messages'] if m['role']=='user');assert not {key(r) for r in fit}&{key(r) for r in dev}
 old=read(P.parent/'paired-fit-execution-2026-10-29/result.json');ledger=P.parent/'paired-fit-execution-2026-10-29/private/study.sqlite';db=sqlite3.connect(f'file:{ledger}?mode=ro',uri=True);v=db.execute('SELECT SUM(positions),SUM(updates),SUM(assistant),SUM(narrative) FROM events').fetchone();sec,active=db.execute('SELECT seconds,active_start FROM timing').fetchone();db.close();assert active is None and dict(zip(old['charges'],v))==old['charges'] and abs(sec-old['seconds'])<1e-6
 save('carry-forward.json',dict(charges=old['charges'],seconds=sec,source=str(ledger.relative_to(ROOT)),source_sha256=sha(ledger),rule='Import this successor ledger once. It already includes calibration, retained screen and inference diagnosis; do not import ancestors again. Older campaigns remain separately recorded.'))
 def gen(rows):return sum(32*len(serial(r['messages'][:1])[0])+496 for r in rows)
 # source all fit+transfer; four arms own fit at64/128; selected two arms transfer once at128.
 generation_positions=gen(fit)+2*gen(dev)+4*gen(fit);generation_forwards=(len(fit)+2*len(dev)+4*len(fit))*32
 padded={f:sum(4*max(len(fit[i]['ids'])-1 for i in b) for b in s) for f,s in schedules.items()};targets={f:sum(sum(fit[i]['mask']) for b in s for i in b) for f,s in schedules.items()}
 # source per-task teacher evaluation + four arms at64/128 =>5 passes over fit.
 teacher_positions=5*sum(4*max(len(fit[i]['ids'])-1 for i in b) for s in schedules.values() for b in s[:8]);training_positions=2*sum(padded.values())+512*2048;native_positions=5*131072
 total=training_positions+teacher_positions+generation_positions+native_positions
 timing=read(P.parent/'lr-feasibility-2026-10-29/timing.json');cal=read(P.parent/'lr-feasibility-2026-10-29/result.json');p95=max(r['step_seconds']['p95'] for r in cal['results'] if r['replay']==.5)
 seconds=1.25*(512*p95+generation_forwards*max(r['seconds_per_forward'] for r in timing['samples'])+(320+80)*max(timing['narrative_batch_seconds'])+120)
 assert total<6000000 and seconds<900
 save('budget.json',dict(authorized=False,new_update_cap=512,new_active_seconds_cap=900,new_position_cap=6000000,new_assistant_target_cap=2*sum(targets.values()),new_narrative_target_cap=1048576,new_artifact_bytes_cap=1073741824,projection_seconds=seconds,positions_upper_bound=total,training_positions=training_positions,teacher_positions=teacher_positions,generation_positions=generation_positions,generation_forwards=generation_forwards,native_positions=native_positions,aggregate_update_cap=old['charges']['updates']+512,aggregate_seconds_cap=sec+900,aggregate_position_cap=old['charges']['positions']+6000000))
 save('checks.json',dict(status='PASS',assertions=checks,fit_presentations=len(fit),fit_values_per_task=16,fit_pairs_per_task=8,transfer_presentations=len(dev),transfer_pairs_per_task_stratum=8,max_context=maxcontext,training_updates=0,model_loaded=False,targets_per_single_task_arm=targets,padded_positions_per_single_task_arm=padded))
 print(read(P/'budget.json'));print(read(P/'checks.json'))
if __name__=='__main__':main()
