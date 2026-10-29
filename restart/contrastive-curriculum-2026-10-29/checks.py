import sys,json,collections
from pathlib import Path
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent/'phase-a-2026-10-28'))
from build import serial,sp
from tasks import oracle

def read(n):return json.loads((P/n).read_text())
def main():
 v=[read(f'private/view-{i}.json') for i in [0,1]];dev=read('private/unscored-development-candidate.json');schedule=read('private/schedule.json');checks=0;overflows=[];maxima={};targets=[]
 def check(cond):
  nonlocal checks
  assert cond;checks+=1
 def independent(s):
  f=s['family']
  if f=='name':return [s['name']]
  if f=='location':return [s['place']]
  if f=='time':return [s['time']]
  if f=='missing':return [s['name'] if s['present'] else 'Unknown']
  if f=='state':return [s['color'],s['new_color'],s['new_color']]
  if f=='distractor':return [s['color']]
  if f=='format':return [f"The {s['item']} is {s['color']}." if s['sentence'] else s['color']]
  return ['What time is the meeting?' if s['slot']=='time' else 'Where is the meeting?',f"The meeting is at {s['time']}." if s['slot']=='time' else f"The meeting is in the {s['place']}."]
 for name,rows in [('view0',v[0]),('view1',v[1]),('dev',dev)]:
  check(len(rows)==(512 if name=='dev' else 4096));maxcontext=0
  for r in rows:
   expected=independent(r['scenario']);answers=[m['content'] for m in r['messages'] if m['role']=='assistant'];check(answers==expected)
   ids,mask=serial(r['messages']);check(ids==r['ids'] and mask==r['mask']);check(mask[0]==0);check(sum(mask)==sum(len(sp.encode(a))+1 for a in answers));check(all(len(sp.encode(a))+1<=32 for a in answers))
   history=[];prior=0
   for t in range(len(answers)):
    history.append(r['messages'][2*t]);worst=len(serial(history)[0])-prior+32*t+32;maxcontext=max(maxcontext,worst)
    if worst>256:overflows.append((name,r['id'],t,worst))
    history.append(r['messages'][2*t+1]);prior+=len(sp.encode(answers[t]))+1
  maxima[name]=maxcontext
  targets.append(sum(sum(r['mask']) for r in rows))
 for i,(a,b) in enumerate(zip(*v)):
  check(a['id']==b['id'] and a['scenario']==b['scenario']);check(a['style']!=b['style'] and a['scope']!=b['scope'] and a['wording']!=b['wording']);check(sum(a['mask'])==sum(b['mask']))
 for rows in v:
  for i in range(0,len(rows),2):
   a,b=rows[i:i+2];check(a['pair']==b['pair']);check(oracle(a['scenario'])!=oracle(b['scenario']));changed={k for k in a['scenario'] if a['scenario'][k]!=b['scenario'][k]};f=a['scenario']['family'];expected={'name':{'name'},'time':{'time'},'location':{'place'},'distractor':{'color'},'format':{'color'},'state':{'color','new_color'},'missing':{'present'},'clarification':{'time'} if a['scenario']['slot']=='time' else {'place'}}[f];check(changed==expected)
  for f in ['distractor','format','state','location']:
   key='place' if f=='location' else 'color';group=collections.defaultdict(collections.Counter)
   for r in rows:
    s=r['scenario']
    if s['family']==f:group[s['item']][s[key]]+=1
   check(all(len(c)==8 and set(c.values())=={8} for c in group.values()))
 seen=collections.Counter()
 for j,b in enumerate(schedule):
  rs=[v[b['view']][i] for i in b['indices']];check(len(rs)==8 and len({r['scenario']['family'] for r in rs})==8)
  for r in rs:seen[(b['view'],r['id'])]+=1
  if j%2==1:
   prior=schedule[j-1];check(prior['view']==b['view']);check(all(v[b['view']][a]['pair']==v[b['view']][z]['pair'] for a,z in zip(prior['indices'],b['indices'])))
 check(len(schedule)==1024 and len(seen)==8192 and set(seen.values())=={1})
 def users(r):return tuple(m['content'] for m in r['messages'] if m['role']=='user')
 trainkeys={users(r) for rows in v for r in rows};check(not trainkeys & {users(r) for r in dev})
 old=P.parent/'phase-a-2026-10-28/private/prepared-v2';overlap={}
 for name in ['matrix','counterfactual','canonical','diverse']:
  oldkeys={users(r) for r in json.loads((old/(name+'.json')).read_text())};overlap[name]=len(oldkeys & trainkeys)
 check(overlap['matrix']==0 and overlap['counterfactual']==0) # Prior training reuse is reported, not evaluation leakage.
 for rows in v:check(set(collections.Counter(r['scenario']['family'] for r in rows).values())=={512})
 check(set(collections.Counter(r['scenario']['family'] for r in dev).values())=={64})
 padded=sum(8*max(len(v[b['view']][i]['ids'])-1 for i in b['indices']) for b in schedule)
 check(not {r['scenario']['item'] for r in dev}&{r['scenario']['item'] for r in v[0]})
 result={'status':'PASS' if not overflows else 'CONTEXT_FAIL','assertions':checks,'old_unique_user_sequence_overlap':overlap,'scheduled_assistant_padded_input_positions':padded,'contexts':maxima,'overflows':overflows,'targets_per_view_and_dev':targets,'counts':{'semantic_training_records':4096,'paired_contrast_groups':2048,'presentation_views':2,'scheduled_batches':1024,'scheduled_conversation_exposures':8192,'development_candidates':512},'limitation':'Primary-authored structured oracle/render checks; not independent semantic review or a released final benchmark.'}
 (P/'checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='overflows'},indent=2));print('overflows',overflows[:8]);check(not overflows)
if __name__=='__main__':main()
