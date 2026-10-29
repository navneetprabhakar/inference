import json,hashlib,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[2];OLD=ROOT/'restart/coherence-g0-2026-10-29/benchmarks'
sys.path.insert(0,str(ROOT/'restart/phase-a-2026-10-28'));from build import sp,serial
changes=[]
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
g=json.loads((OLD/'grounded_choices.json').read_text())
def encode(prefix,suffixes):
 ids=[1]+sp.encode(prefix);full=[[1]+sp.encode(prefix+s) for s in suffixes]
 assert all(a[:len(ids)]==ids for a in full)
 return dict(prefix_ids=ids,full_ids=full,suffix_start=len(ids),verified_exact_prefix=True,score='sum_log_probability_of_joint_encoded_suffix')
for r in g:
 if r['id'] not in ['ground-15-2','ground-20-2']:continue
 old=json.loads(json.dumps(r));i,word=(0,'midnight') if r['id']=='ground-15-2' else (3,'late evening')
 r['options'][i]=word;r['suffixes'][i]=' '+word+'.';r['joint_encoding']=encode(r['prefix'],r['suffixes'])
 for k in ['empty_passage_prefix','shuffled_passage_prefix']:r['controls'][k+'_joint_encoding']=encode(r['controls'][k],r['suffixes'])
 changes.append(dict(id=r['id'],before={k:old[k] for k in ['passage','question','options','correct_index']},after={k:r[k] for k in ['passage','question','options','correct_index']}))
d=json.loads((OLD/'development.json').read_text());replies={'dev-explanation-02':'Members can reserve on Monday; walk-ins must wait until Tuesday.','dev-explanation-06':'The main van is loading at bay two; the spare van is waiting.','dev-explanation-07':'Mira checks tickets first; the driver closes the doors afterward.','dev-explanation-08':'The local bus leaves earlier because noon comes before dusk.','dev-explanation-11':'The curtain falls last, after the bell that follows the blackout.','dev-explanation-19':'The drains: the note places the leaf pile away from them.','dev-instructions-00':'No. The east fountain is off, while the west fountain is running.'}
for r in d:
 if r['id'] in replies:
  before=json.loads(json.dumps(r['turns']));index=1 if r['id']=='dev-instructions-00' else 0
  r['turns'][index]['reference']=replies[r['id']];r['turns'][index]['required_semantics']=replies[r['id']]
  if r['id']=='dev-explanation-08':r['turns'][0]['user']='On the same day, '+r['turns'][0]['user'][0].lower()+r['turns'][0]['user'][1:]
  changes.append(dict(id=r['id'],before=before,after=r['turns']))
 history=[];oldtargets=0
 for i,t in enumerate(r['turns']):
  history.append(dict(role='user',content=t['user']));prefix=len(serial(history)[0])-oldtargets+32*i
  t['worst_prefix_tokens']=prefix;t['reference_tokens_including_eos']=len(sp.encode(t['reference']))+1
  assert t['reference_tokens_including_eos']<=32 and prefix+32<=256
  oldtargets+=t['reference_tokens_including_eos'];history.append(dict(role='assistant',content=t['reference']))
 r['worst_history_tokens_including_last_reply']=max(t['worst_prefix_tokens']+32 for t in r['turns'])
for r in g:
 for e in [r['joint_encoding']]+[r['controls'][k+'_joint_encoding'] for k in ['empty_passage_prefix','shuffled_passage_prefix']]:
  assert e['prefix_ids'][0]==1 and all(x[:e['suffix_start']]==e['prefix_ids'] for x in e['full_ids'])
save('grounded_choices.json',g);save('development.json',d);save('repair-review-packet.json',changes)
save('repair-receipt.json',dict(status='REPAIRED_PENDING_INDEPENDENT_RECHECK_NOT_ADMITTED',collected_prelaunch_repair_batch=1,changed_records=len(changes),all_ground_sequences_checked=1440,max_development_context=max(r['worst_history_tokens_including_last_reply'] for r in d),old_files_unchanged=True,files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in P.glob('*.json') if f.name!='repair-receipt.json'}))
print('Repaired9items; joint encoding/context checks pass; pending independent recheck.')
