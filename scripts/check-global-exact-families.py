"""Read-only exact-edge/component and original-witness integrity audit."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import sqlite3
from slm.data.prose_screen import word_key
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/global-exact-families-v2')

def main():
    report=json.loads((ROOT/'report.json').read_text());plan=json.loads((ROOT/'plan.json').read_text())
    assert report['complete'] and report['plan_sha256']==sha('configs/global-exact-families-v2.json')
    assert sha(ROOT/'families.sqlite')==report['database_sha256']
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    db=sqlite3.connect('file:'+str((ROOT/'families.sqlite').resolve())+'?mode=ro',uri=True)
    assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
    assert db.execute('SELECT complete FROM status').fetchall()==[(1,)]
    count=db.execute('SELECT count(*) FROM records').fetchone()[0];assert count==report['records']<=plan['max_records']
    parent=list(range(count));anchors={};seen=Counter();frozen_seen=set();original_count=recovered=0
    def find(s):
        while parent[s]!=s:parent[s]=parent[parent[s]];s=parent[s]
        return s
    def union(a,b):
        a,b=find(a),find(b);parent[max(a,b)]=min(a,b)
    frozen=json.loads((Path(plan['ancestral_dataset'])/'heldout-groups.json').read_text())
    for sid,eid,data,ingredient,candidate,fixed,blocked,root in db.execute('SELECT * FROM records ORDER BY sid'):
        r=json.loads(data);assert r['id']==eid and r['ingredient']==ingredient
        assert r['training_approved'] is False and candidate==r['candidate'] and blocked==r['blocked']
        assert fixed=={None:0,'validation':1,'test':2}[r['fixed_partition']]
        seen[ingredient]+=1
        values={('family',f) for f in r['families']}
        for text in r['texts'].values():
            key=word_key(text)
            if len(key)>=16 and len(key.split())>=4:values.add(('text',digest(key)))
        for key in values:
            if key in anchors:union(sid,anchors[key])
            else:anchors[key]=sid
        if ingredient=='ancestral':
            raw=r['reference']['original'];assert r['fixed_partition']==raw['split']==frozen[raw['parent_group_id']]
            assert r['texts']=={str(i):m['content'] for i,m in enumerate(raw['messages'])}
            frozen_seen.add(raw['parent_group_id']);original_count+=1
        elif ingredient=='ancestral-recovered':
            ref=r['reference'];line=next(line for i,line in enumerate(Path(ref['path']).open()) if i==ref['line']);raw=json.loads(line)
            assert digest(raw)==ref['raw_record_sha256']
            assert r['families']==['databricks/databricks-dolly-15k:'+digest(raw)]
            assert r['texts']==dict(instruction=raw['instruction'],context=raw['context'],response=raw['response'])
            assert r['fixed_partition']==frozen[r['families'][0]];frozen_seen.add(r['families'][0]);recovered+=1
    assert dict(seen)==report['ingredient_records'] and frozen_seen==set(frozen)
    assert original_count==5797 and recovered==2 and len(frozen_seen)==2862
    # Independently regroup from original text/family keys; compare every root.
    for sid,root in db.execute('SELECT sid,root FROM records'):assert find(sid)==root
    assert db.execute('SELECT count(*) FROM anchors').fetchone()[0]==len(anchors)
    for kind,key,sid in db.execute('SELECT * FROM anchors'):assert anchors[(kind,key)]==sid
    edge_count=0
    for a,b,kind,key in db.execute('SELECT * FROM edges'):
        for sid in (a,b):
            r=json.loads(db.execute('SELECT data FROM records WHERE sid=?',(sid,)).fetchone()[0])
            if kind=='family':assert key in r['families']
            else:assert key in {digest(word_key(t)) for t in r['texts'].values() if len(word_key(t))>=16 and len(word_key(t).split())>=4}
        edge_count+=1
    assert edge_count==report['edges']
    components=0
    for root,group,fixed,blocked,members in db.execute('SELECT * FROM components'):
        rows=db.execute('SELECT eid,fixed,blocked FROM records WHERE root=? ORDER BY eid',(root,)).fetchall()
        assert (digest([r[0] for r in rows]),max(r[1] for r in rows),max(r[2] for r in rows),len(rows))==(group,fixed,blocked,members)
        components+=1
    assert components==report['components']
    result=dict(creator='Navneet Prabhakar',kind='actual-global-exact-family-check-v1',passed=True,
        report_sha256=sha(ROOT/'report.json'),database_sha256=report['database_sha256'],records_checked=count,exact_edges_checked=edge_count,
        components_checked=components,full_ancestral_shard_rows=original_count,recovered_ancestral_raw_rows=recovered,ancestral_families=len(frozen_seen),
        near_grouping_complete=False,substring_seed_linking_complete=False,training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
        scope='All consolidated text/family anchors independently regrouped; every edge/component, fixed witness label and original input hash verified. Full source-row consolidation generator is not independently replayed; near/containment/global split/admission remain required.')
    Path('reports/global-exact-families-check.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2));db.close()

if __name__=='__main__':main()
