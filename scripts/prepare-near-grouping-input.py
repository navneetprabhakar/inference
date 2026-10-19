"""Consume verified containment links into the immutable next grouping input."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import sqlite3
from slm.data.schema import digest
from slm.data.tokenized import sha

OUT=Path('data/global-grouping-input-v1')
PLAN=Path('configs/global-grouping-input-v1.json')

def main():
    if OUT.exists():raise FileExistsError('Grouping input already prepared')
    plan=json.loads(PLAN.read_text())
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    links=sqlite3.connect('file:'+str(Path(plan['containment_database']).resolve())+'?mode=ro',uri=True)
    rows=source.execute('SELECT sid,eid,root,candidate,fixed,blocked,ingredient FROM records ORDER BY sid').fetchall()
    assert len(rows)==235779
    parent=[r[2] for r in rows]
    def find(s):
        while parent[s]!=s:parent[s]=parent[parent[s]];s=parent[s]
        return s
    consumed=0
    for a,b in links.execute('SELECT seed_sid,target_sid FROM links'):
        a,b=find(a),find(b);parent[max(a,b)]=min(a,b);consumed+=1
    members={};flags={};withheld=Counter()
    for sid,eid,oldroot,candidate,fixed,blocked,ingredient in rows:
        root=find(sid);members.setdefault(root,[]).append(eid)
        f=flags.setdefault(root,[0,0]);f[0]=max(f[0],fixed);f[1]=max(f[1],blocked)
    OUT.mkdir();(OUT/'plan.json').write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n')
    with (OUT/'roots.jsonl').open('w') as out:
        for sid,eid,oldroot,candidate,fixed,blocked,ingredient in rows:
            root=find(sid)
            out.write(json.dumps(dict(sid=sid,root=root),sort_keys=True)+'\n')
            if candidate:
                if flags[root][0]:withheld['heldout_family']+=1
                if flags[root][1]:withheld['blocked_family']+=1
    with (OUT/'components.jsonl').open('w') as out:
        for root in sorted(members):
            out.write(json.dumps(dict(root=root,group_id=digest(sorted(members[root])),members=len(members[root]),heldout_priority=flags[root][0],blocked=flags[root][1]),sort_keys=True)+'\n')
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    report=dict(creator='Navneet Prabhakar',kind='actual-near-grouping-input-v1',complete=True,plan_sha256=sha(PLAN),
        records=len(rows),components=len(members),containment_occurrences_consumed=consumed,candidate_withheld=dict(withheld),
        roots_sha256=sha(OUT/'roots.jsonl'),components_sha256=sha(OUT/'components.jsonl'),training_approved=False,
        new_split_assignment=False,near_grouping_complete=False,model_updates=0,teacher_calls=0,cloud_spend=0,
        scope='Exact baseline components plus every verified seed-containment edge; original per-record fixed labels remain in immutable source DB. Near-shingle grouping, new split assignment and admission remain required.')
    (OUT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    Path('reports/global-grouping-input.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2));source.close();links.close()

if __name__=='__main__':main()
