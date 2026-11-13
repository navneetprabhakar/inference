"""Freeze fully root-reviewed evaluation specs; never generate training targets."""
import copy,collections,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path('.').resolve()))
from tools import FixtureSession
R=Path('runs/ownbase-budget50-v1/eval-candidates');O=Path('reports/ownbase-budget50-v1');raw={};sources=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for p in sorted(R.glob('batch-*/output.json')):
 sources.append({'path':str(p),'sha256':sha(p)})
 for s in json.loads(p.read_text())['sessions']:assert s['id'] not in raw;raw[s['id']]=s
assert len(raw)==82
selected={
 'natural':['01-01','01-04','01-06','01-08','01-10','02-01','02-02','02-04']+[f'07-{i:02d}' for i in range(1,13)],
 'tool':['01-02','01-05','01-09','02-03','02-05','02-09','03-01','03-02','03-03','03-04','03-09']+[f'04-{i:02d}' for i in range(1,11) if i!=2],
 'code_state':['05-01','05-02','05-03','05-04','05-05','05-06','05-09','05-10','06-01','06-06']+[f'08-{i:02d}' for i in range(1,11)]}
sessions=[];edits=[]
for category,ids in selected.items():
 assert len(ids)==20
 for suffix in ids:
  s=copy.deepcopy(raw['b50-'+suffix]);s['category']=category
  if s['family'] in ['natural','tool','code_state']:s['family']=category+'-'+suffix
  sessions.append(s)
byid={s['id']:s for s in sessions}
def edit(id,turn,key,value,reason):
 t=byid[id]['turns'][turn];edits.append({'id':id,'turn':turn,'field':key,'before':t[key],'after':value,'reason':reason});t[key]=value
edit('b50-01-09',2,'rubric','Six original tubes still contain posters. Each began with eight and only three posters total were removed, so none can have been emptied. The five additional tubes are empty and do not change the occupied count. No tool call.','Original rubric contradicted itself, initially claiming insufficient information.')
edit('b50-07-04',0,'user',"For a workshop handout, include a diagram whenever the explanation has more than one step; otherwise a diagram is optional. The explanation is: 'Open the app and select Help.' What should the handout include?",'Only-if did not mean if; clarify the intended conditional to match the task and both downstream rubrics.')
edit('b50-07-08',1,'rubric','The later forecast supplies a low-likelihood description while retaining the possibility of rain. Do not infer a numeric probability or certainty. The original statement did not specify a likelihood, so do not claim a measured decrease from a known previous probability.','Unspecified prior likelihood does not establish a decrease.')
traces=[]
for s in sessions:
 broker=FixtureSession()
 assert len(s['turns'])==3
 for i,t in enumerate(s['turns']):
  broker.start_turn(permit_calls=t['permit_calls'],allowed_names=['calculate','convert'] if t['permit_calls'] else [])
  assert len(t['expected_calls'])<=2 and (t['permit_calls'] or not t['expected_calls'])
  for call in t['expected_calls']:
   rec=broker.propose(json.dumps(call),assistant_call_boundary=True);assert rec['ok'];traces.append({'session':s['id'],'turn':i,'call':call,'result':rec['data']['result']})
assert len({tuple(t['user'] for t in s['turns']) for s in sessions})==60
suite={'schema':1,'purpose':'frozen_synthetic_assessment_never_train','sessions':sessions,'scope':'60 short synthetic sessions,20 per category; no 4K/late-context coverage. Every model answer requires root semantic review; equivalent correct tool workflows are acceptable. Reused for at most two predefined candidate comparisons, so this is model-selection evidence, not a pristine post-selection benchmark.'}
p=O/'assessment.json';assert not p.exists();p.write_text(json.dumps(suite,indent=2,ensure_ascii=False)+'\n')
review={'schema':1,'reviewer':'root','raw_candidates_reviewed':82,'selected_sessions':60,'selected_turns':180,'categories':dict(collections.Counter(s['category'] for s in sessions)),'suite_sha256':sha(p),'raw_sources':sources,'edits':edits,'excluded':{k:'Not selected: redundant scenario/mechanism or category mix; this is not an error verdict.' for k in raw if k not in byid},'reference_tool_calls_replayed':len(traces),'reference_traces':traces,'review_notes':['All selected users and rubrics read in full before model outputs. All8batches reviewed; raw candidates preserved.','Three selected-spec corrections explicit above; unselected b50-03-10 has escaped-newline/scope ambiguity and is not used.','Commutative operands and valid alternate arithmetic sequences must be accepted in manual review; exact reference-call comparator is diagnostic only.','Code semantics checked independently in verify_assessment.py.','No claim of semantic independence from every historic training family; basic Python and arithmetic concepts intentionally overlap, scenarios newly authored.','No new training admission and no acceptance score inferred from corpus counts.']}
(O/'assessment-review.json').write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:review[k] for k in ['selected_sessions','selected_turns','reference_tool_calls_replayed','suite_sha256']}))
