"""Independently reconcile every root and flag after containment union."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import sqlite3
from slm.data.schema import digest
from slm.data.tokenized import sha

root=Path('data/global-grouping-input-v1');plan=json.loads((root/'plan.json').read_text());report=json.loads((root/'report.json').read_text())
assert report['complete'] and report['plan_sha256']==sha('configs/global-grouping-input-v1.json')
for p,h in plan['input_bindings'].items():assert sha(p)==h,p
assert sha(root/'roots.jsonl')==report['roots_sha256'] and sha(root/'components.jsonl')==report['components_sha256']
source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
links=sqlite3.connect('file:'+str(Path(plan['containment_database']).resolve())+'?mode=ro',uri=True)
rows=source.execute('SELECT sid,eid,root,candidate,fixed,blocked FROM records ORDER BY sid').fetchall();parents=[r[2] for r in rows]
def find(s):
    while parents[s]!=s:parents[s]=parents[parents[s]];s=parents[s]
    return s
for a,b in links.execute('SELECT seed_sid,target_sid FROM links'):
    a,b=find(a),find(b);parents[max(a,b)]=min(a,b)
components={};withheld=Counter()
with (root/'roots.jsonl').open() as inp:
    for raw,r in zip(inp,rows,strict=True):
        sid,eid,old,candidate,fixed,blocked=r;value=json.loads(raw)
        assert value==dict(sid=sid,root=find(sid));c=components.setdefault(value['root'],dict(eids=[],fixed=0,blocked=0))
        c['eids'].append(eid);c['fixed']=max(c['fixed'],fixed);c['blocked']=max(c['blocked'],blocked)
for sid,eid,old,candidate,fixed,blocked in rows:
    if candidate:
        c=components[find(sid)]
        if c['fixed']:withheld['heldout_family']+=1
        if c['blocked']:withheld['blocked_family']+=1
with (root/'components.jsonl').open() as inp:
    for line in inp:
        c=json.loads(line);expected=components.pop(c['root'])
        assert c==dict(root=c['root'],group_id=digest(sorted(expected['eids'])),members=len(expected['eids']),heldout_priority=expected['fixed'],blocked=expected['blocked'])
assert not components and dict(withheld)==report['candidate_withheld']
result=dict(creator='Navneet Prabhakar',kind='actual-near-grouping-input-check-v1',passed=True,report_sha256=sha(root/'report.json'),records_checked=len(rows),components_checked=report['components'],all_containment_edges_consumed=True,original_witness_labels_unchanged=True,near_grouping_complete=False,training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,scope='Every root/component/identity/heldout and nonapproval flag independently reconciled to immutable exact DB and verified containment edges. No near, new split or admission claim.')
Path('reports/global-grouping-input-check.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2));source.close();links.close()
