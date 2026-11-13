"""Execute supplied reducer tests and compare both revisions with a table oracle."""
import hashlib,itertools,json,re
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-08')
r=next(json.loads(l) for l in (root/'candidates.jsonl').read_text().splitlines() if json.loads(l)['id']=='b50-queue-protocol')
blocks=lambda i:re.findall(r'```python\n(.*?)```',r['messages'][i]['content'],re.S)
original=blocks(13)[0];ns={};exec(original,ns)
patched=original.replace('    version: int\n','    version: int\n    conflict: bool = False\n',1).replace('            raise ValueError("command ID reused with different request")','            return job, Result(False, job.state, job.version, conflict=True)')
patched=patched[:patched.index('try:\n    reduce_job')]+blocks(15)[1]
ns2={};exec(patched,ns2)
table={('queued','start'):'running',('queued','cancel'):'cancelled',('running','pause'):'paused',('running','complete'):'completed',('running','cancel'):'cancelled',('paused','resume'):'running',('paused','cancel'):'cancelled',('paused','retry'):'queued'}
requests=[('a',c,()) for c in ['start','pause','resume','retry','complete','cancel','unknown']]+[('b','start',()),('b','pause',()),('a','start',('other',))]
checks=0
for namespace,conflicts in [(ns,False),(ns2,True)]:
 for seq in itertools.product(requests,repeat=4):
  job=namespace['Job']();state='queued';version=0;history={}
  for cid,cmd,payload in seq:
   before=(job.state,job.version,dict(job.history));conflict=False
   if cid in history:
    prior_cmd,prior_payload,result=history[cid]
    conflict=(cmd,payload)!=(prior_cmd,prior_payload)
    if conflict:result=(False,state,version)
   else:
    new=table.get((state,cmd));accepted=new is not None
    if accepted:state=new;version+=1
    result=(accepted,state,version);history[cid]=(cmd,payload,result)
   if conflict and not conflicts:
    try:namespace['reduce_job'](job,cid,cmd,payload)
    except ValueError:pass
    else:raise AssertionError('missing conflict exception')
   else:
    old=job;job,actual=namespace['reduce_job'](job,cid,cmd,payload)
    assert (actual.accepted,actual.state,actual.version)==result
    if conflicts:assert actual.conflict==conflict
    assert (old.state,old.version,old.history)==before
    assert (job.state,job.version)==(state,version)
   checks+=1
report={'candidate':'b50-queue-protocol','source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'supplied_tests':'Both original and documented patched implementation executed','independent_oracle_sequences':20000,'command_checks':checks,'passed':True,'scope':'Immutable tuple payloads as explicitly scoped in the example; original state, version and history preserved.'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
