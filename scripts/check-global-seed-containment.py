"""Verify seed-link soundness and target coverage; sample independent recall."""
# Creator: Navneet Prabhakar
import hashlib
import heapq
import json
from pathlib import Path
import sqlite3
from slm.data.seed_containment import PrefixIndex,normalized_bytes
from slm.data.tokenized import sha

ROOT=Path('data/global-seed-containment-v1')

def main():
    plan=json.loads((ROOT/'plan.json').read_text());report=json.loads((ROOT/'report.json').read_text())
    assert report['complete'] and report['plan_sha256']==sha('configs/global-seed-containment-v1.json')
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    assert sha(ROOT/'links.sqlite')==report['output_database_sha256']
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    links=sqlite3.connect('file:'+str((ROOT/'links.sqlite').resolve())+'?mode=ro',uri=True)
    assert links.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
    assert links.execute('SELECT complete FROM status').fetchall()==[(1,)]
    patterns={};owners={};seed_facets=records=facets=total_bytes=0;sample=[]
    for sid,data,root in source.execute('SELECT sid,data,root FROM records ORDER BY sid'):
        r=json.loads(data);records+=1
        for facet,text in r['texts'].items():
            raw=normalized_bytes(text);facets+=1;total_bytes+=len(raw)
            assert len(raw)<=plan['max_facet_bytes']
            score=int(hashlib.sha256(('seed-recall-audit-20261019:'+str(sid)+':'+facet).encode()).hexdigest(),16)
            value=(-score,sid,facet,raw)
            if len(sample)<128:heapq.heappush(sample,value)
            elif value>sample[0]:heapq.heapreplace(sample,value)
            if facet=='seed':
                seed_facets+=1;key=hashlib.sha256(raw).hexdigest()
                assert len(raw)>=plan['anchor_width']
                if key in owners:assert patterns[key]==raw and owners[key][1]==root
                else:patterns[key]=raw;owners[key]=(sid,root)
    assert (seed_facets,records,facets,total_bytes)==tuple(report['counts'][k] for k in ('seed_facets','target_records','target_facets','normalized_target_bytes'))
    assert len(patterns)==report['distinct_normalized_seed_patterns']
    assert links.execute('SELECT count(*) FROM patterns').fetchone()[0]==len(patterns)
    for key,sid,root,h,n in links.execute('SELECT * FROM patterns'):
        assert (sid,root)==owners[key] and h==key and len(patterns[key])==n
    new=0;diagnostics=[]
    for key,seed_sid,target_sid,facet,start,end in links.execute('SELECT * FROM links ORDER BY pattern,target_sid,facet,start'):
        raw_data,root=source.execute('SELECT data,root FROM records WHERE sid=?',(target_sid,)).fetchone();target=json.loads(raw_data)
        raw=normalized_bytes(target['texts'][facet]);assert raw[start:end]==patterns[key]
        assert (seed_sid,owners[key][1])==owners[key] and owners[key][1]!=root
        assert end-start==len(patterns[key]);new+=1
        sample.append((0,target_sid,facet,raw))
        seed_data=json.loads(source.execute('SELECT data FROM records WHERE sid=?',(seed_sid,)).fetchone()[0])
        diagnostics.append(dict(seed_id=seed_data['id'],target_id=target['id'],target_ingredient=target['ingredient'],target_facet=facet,normalized_start=start,normalized_end=end,
            seed_component=owners[key][1],target_component=root))
    assert new==report['counts'].get('new_cross_component_occurrences',0)
    index=PrefixIndex(patterns,width=plan['anchor_width'],max_bytes=plan['max_facet_bytes']);sampled_matches=0
    for _,sid,facet,raw in sample:
        expected=[]
        for key,pattern in patterns.items():
            position=0
            while (position:=raw.find(pattern,position))>=0:
                expected.append((key,position));position+=1
        actual=list(index.matches(raw));assert sorted(actual)==sorted(expected)
        sampled_matches+=len(expected)
    result=dict(creator='Navneet Prabhakar',kind='actual-global-seed-containment-check-v1',passed=True,report_sha256=sha(ROOT/'report.json'),
        full_source_record_coverage=records,full_source_facet_coverage=facets,normalized_target_bytes=total_bytes,seed_facets=seed_facets,
        distinct_patterns_verified=len(patterns),all_new_links_verified=new,independent_brute_force_facets=len(sample),independent_brute_force_occurrences=sampled_matches,
        new_link_diagnostics=diagnostics,training_approved=False,near_grouping_complete=False,model_updates=0,teacher_calls=0,cloud_spend=0,
        scope='All pattern identities, source coverage totals and new normalized containment spans verified; candidate completeness independently brute-forced on128fixed-hash facets plus all new-link targets, not every target. Full scan evidence is the pinned executed worker and counters. No unique upstream-ID, latent-excerpt, near-family or admission claim.')
    Path('reports/global-seed-containment-check.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2));source.close();links.close()

if __name__=='__main__':main()
