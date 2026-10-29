"""Prospective CPU-only revision: shared multi-attribute worlds across task questions.
Keeps frozen v1/inference artifacts unchanged; writes a separate candidate release.
"""
import json,copy
from pathlib import Path
from build import ROOT,PRIVATE,save,serial
from tasks import QUERIES,oracle
DEST=PRIVATE/'prepared-v2';DEST.mkdir(exist_ok=True)
FIELDS=['item','other','color','other_color','new_color','new_other_color','name','other_name','time','other_time','place','other_place']
def read(n):return json.loads((PRIVATE/(n+'.json')).read_text())
trainworld={int(r['scenario']['cluster'].rsplit('-',1)[1]):r['scenario'] for r in read('canonical') if r['scenario']['family']=='name'}
unseenworld={int(r['scenario']['cluster'].rsplit('-',1)[1]):r['scenario'] for r in read('matrix') if r['scenario']['family']=='name' and r['cell']=='B'}
def world(s):
 out=copy.deepcopy(s);i=int(s['cluster'].rsplit('-',1)[1]);w=trainworld[i] if s['pool']=='train' else unseenworld[i]
 for k in FIELDS:out[k]=w[k]
 # The clarification location holdout uses genuinely new supplied place names.
 if s['family']=='clarification' and s['slot']=='location' and s['pool']=='unseen':out['place']=s['place']
 out['world_id']=s['pool']+'-world-'+str(i);return out

def render(s,w,numeric=False):
 ctx=dict(s);ctx['style']='Answer with exactly one sentence: The ITEM is COLOR.' if s['sentence'] else 'Answer with the color word only.';q=QUERIES[s['family']][w].format(**ctx)
 if s['family']=='clarification':
  facts='Meeting time: not supplied. Meeting place: not supplied.'
 else:
  owner=s['name'] if s['family']!='missing' or s['present'] else 'not supplied'
  a=f"{s['item']}: {s['color']}; owner {owner}; on the {s['place']}."
  b=f"{s['other']}: {s['other_color']}; owner {s['other_name']}; on the {s['other_place']}."
  facts=' '.join([a,b] if s['target_first'] else [b,a])+f" Meeting: {s['time']}. Delivery: {s['other_time']}."
 user=q+' '+facts if s['question_first'] else facts+' '+q
 if numeric:user='Reference 7319. '+user
 users=[user]
 if s['family']=='state':users += [f"Correction: the {s['item']} is {s['new_color']}, not {s['color']}. "+q,f"The {s['other']} is now {s['new_other_color']}. "+q]
 if s['family']=='clarification':users += [f"The meeting is at {s['time']}. Now write the reminder." if s['slot']=='time' else f"The meeting is in the {s['place']}. Now write the reminder."]
 return [m for u,a in zip(users,oracle(s)) for m in [dict(role='user',content=u),dict(role='assistant',content=a)]]
def transform(r,s):
 out=copy.deepcopy(r);out['scenario']=s;out['messages']=render(s,r['wording'],r['numeric_id']);out['ids'],out['mask']=serial(out['messages']);out['preparation_version']=2;return out
for bank in ['canonical','diverse','matrix']:
 save(DEST/(bank+'.json'),[transform(r,world(r['scenario'])) for r in read(bank)])
# Preserve intervention itself after applying a common base world to each pair.
source=read('counterfactual');out=[]
for i in range(0,len(source),2):
 a,b=source[i:i+2];s=world(a['scenario']);t=copy.deepcopy(s);tag=a['intervention']
 if tag=='missingness':t['present']=not s['present']
 elif tag=='reversed_update':t['color'],t['new_color']=s['new_color'],s['color']
 elif tag=='value_substitution':
  f=s['family'];key='name' if f in ['name','missing'] else 'time' if f=='time' or (f=='clarification' and s['slot']=='time') else 'place' if f in ['location','clarification'] else 'color'
  value=b['scenario'][key]
  if value==s[key]:value={'name':'Oscar West','time':'23:59','place':'pantry','color':'orange'}[key]
  t[key]=value
 out += [transform(a,s),transform(b,t)]
save(DEST/'counterfactual.json',out)
for n in ['training-schedule','prospective-final-candidates']:(DEST/(n+'.json')).write_bytes((PRIVATE/(n+'.json')).read_bytes())
# Exact shared world facts across four attribute tasks (order ignored) are now guaranteed.
shared={}
for r in json.loads((DEST/'canonical.json').read_text()):
 s=r['scenario']
 if s['family'] in ['name','location','distractor','format']:
  key=s['world_id'];facts=tuple(s[k] for k in FIELDS);shared.setdefault(key,set()).add(facts)
assert len(shared)==400 and all(len(x)==1 for x in shared.values())
save(ROOT/'shared-world-check.json',dict(status='PASS',worlds=400,task_families=['name','location','distractor','format'],meaning='Identical multi-attribute world supports different queries; role order and output format balanced independently.',version=2,training_authorized=False))
print('Prepared separatev2 candidate release; v1 frozen evidence retained.')
