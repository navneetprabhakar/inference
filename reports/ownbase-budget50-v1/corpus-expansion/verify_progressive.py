"""Independent execution/oracles for fully inspected progressive cohort code."""
import ast,contextlib,copy,hashlib,io,itertools,json,re,unittest
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-04');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())};results=[]
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'copy','unittest'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 with contextlib.redirect_stdout(io.StringIO()):exec(compile(tree,'reviewed-corpus','exec'),ns)
for ident in ['b50-event-ledger','b50-tile-routes','b50-transcript-timing']:
 ns={'__name__':'reviewed_fixture'};blocks=0;checks=0
 for i,msg in enumerate(rows[ident]['messages']):
  if msg['role']!='assistant':continue
  for code in re.findall(r'```python\n(.*?)```',msg.get('content',''),re.S):
   if code.startswith('elif current is None'):
    assert ident=='b50-event-ledger' and i==13
    original=re.findall(r'```python\n(.*?)```',rows[ident]['messages'][11]['content'],re.S)[0]
    needle="        elif current is None and action == 'cancel':\n            result = 'unresolved'"
    code=original.replace(needle,'\n'.join('        '+line if line else '' for line in code.strip().splitlines()));assert code!=original
   execute(code,ns);blocks+=1
  if ident=='b50-event-ledger' and i in [11,13,15]:
   reducer=ns['reduce_ledger']
   def event(id,b,v,action,units=0):return dict(id=id,booking=b,version=v,action=action,units=units)
   inputs=[event('e1','a',1,'allocate',4),event('e2','b',1,'allocate',3),event('e3','a',2,'allocate',5),event('e4','b',2,'cancel'),event('e5','a',1,'allocate',2),event('e6','c',1,'allocate',4),event('e7','c',1,'allocate',3),event('e8','d',3,'cancel'),event('e9','d',2,'allocate',1)]
   b,free,outcomes=reducer(inputs)
   assert [r for _,r in outcomes[:7]]==['accepted','accepted','accepted','accepted','stale','accepted','conflict']
   assert outcomes[-2:]==([('e8','unresolved'),('e9','accepted')] if i==11 else [('e8','accepted'),('e9','stale')])
   assert free==(0 if i==11 else 1);checks+=3
   if i==15:ns['test_reducer']();checks+=1
  if ident=='b50-transcript-timing' and i in [6,10]:
   def oracle(cues):
    groups=[];pending=set(range(len(cues)))
    while pending:
     seed=min(pending);pending.remove(seed);group={seed};work=[seed]
     while work:
      k=work.pop();a=cues[k]
      if a['start']==a['end']:continue
      connected={j for j in pending if cues[j]['start']<cues[j]['end'] and max(a['start'],cues[j]['start'])<min(a['end'],cues[j]['end'])}
      group|=connected;pending-=connected;work.extend(connected)
     start=min(cues[k]['start'] for k in group);end=max(cues[k]['end'] for k in group)
     labels=list(dict.fromkeys(cues[k]['label'] for k in sorted(group)))
     tie=min(k for k in group if cues[k]['start']==start)
     groups.append((start,tie,dict(start=start,end=end,label=','.join(labels))))
    return [r for _,_,r in sorted(groups)]
   intervals=[(s,e) for s in range(4) for e in range(s,4)]
   for triple in itertools.product(intervals,repeat=3):
    cues=[dict(start=s,end=e,label='AB'[k%2]) for k,(s,e) in enumerate(triple)]
    if i==6:cues.sort(key=lambda x:x['start'])
    before=copy.deepcopy(cues);assert ns['merge'](cues)==oracle(cues),(i,cues,ns['merge'](cues),oracle(cues));assert cues==before;checks+=1
  if ident=='b50-transcript-timing' and i in [8,10]:
   suite=unittest.defaultTestLoader.loadTestsFromTestCase(ns['TestMerge']);result=unittest.TextTestRunner(stream=io.StringIO()).run(suite);assert result.wasSuccessful();checks+=result.testsRun
 if ident=='b50-tile-routes':ns['test_verify']();checks+=4
 results.append({'id':ident,'executed_blocks':blocks,'independent_checks_and_examples':checks,'semantic_admission_separate':True})
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'results':results};(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
