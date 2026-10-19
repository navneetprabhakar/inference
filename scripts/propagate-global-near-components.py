"""Terminal-audited near links over immutable exact/containment roots."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import sqlite3
from slm.data.near_components import Components
from slm.data.near_audit import require_terminal
from slm.data.stream_hash import sha

OUT=Path('data/global-near-components-v1');NEAR=Path('data/global-near-facets-v3')
PROOF=Path('reports/global-near-facets-check.json')

def main():
    if not PROOF.is_file():raise ValueError('Actual terminal near audit required before component allocation')
    proof=json.loads(PROOF.read_text());report=require_terminal(NEAR)
    if (proof.get('passed') is not True or proof['report_sha256']!=sha(NEAR/'report.json')
            or proof['checker_sha256']!=sha('scripts/check-global-near-facets.py')
            or proof['audit_module_sha256']!=sha('src/slm/data/near_audit.py')):raise ValueError('Actual near-audit binding differs')
    plan=json.loads(Path('configs/global-near-facets-v3.json').read_text())
    if report['plan_sha256']!=sha('configs/global-near-facets-v3.json') or sha(NEAR/'near.sqlite')!=report['database_sha256']:raise ValueError('Near terminal bytes differ')
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Inherited source input changed')
    if OUT.exists():raise FileExistsError('Preserve existing component propagation attempt')
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    near=sqlite3.connect('file:'+str((NEAR/'near.sqlite').resolve())+'?mode=ro',uri=True)
    try:
        source.row_factory=sqlite3.Row
        records=[dict(r) for r in source.execute('SELECT sid,eid,candidate,fixed,blocked FROM records ORDER BY sid')]
        roots=[]
        with Path(plan['inherited_roots']).open() as inp:
            for sid,line in enumerate(inp):
                r=json.loads(line)
                if r['sid']!=sid:raise ValueError('Inherited root row identity differs')
                roots.append(r['root'])
        components=Components(records,roots)
        for facet_sid,source_sid in near.execute('SELECT sid,source_sid FROM facet_sources ORDER BY sid,source_sid'):components.register(facet_sid,source_sid)
        for a,b in near.execute('SELECT a,b FROM near_pairs ORDER BY a,b'):components.link(a,b)
        if components.links!=proof['all_reported_near_pairs_recomputed']:raise ValueError('All audited facet pairs must be consumed')
        output=components.result()
        inputs={p:sha(p) for p in ['scripts/propagate-global-near-components.py','src/slm/data/near_components.py',str(PROOF),str(NEAR/'report.json'),str(NEAR/'near.sqlite'),plan['source_database'],plan['inherited_roots']]}
        OUT.mkdir();(OUT/'inputs.json').write_text(json.dumps(inputs,indent=2,sort_keys=True)+'\n')
        with (OUT/'roots.jsonl').open('w') as stream:
            for sid,root in enumerate(output['roots']):stream.write(json.dumps(dict(sid=sid,root=root),sort_keys=True)+'\n')
        with (OUT/'components.jsonl').open('w') as stream:
            for r in output['components']:stream.write(json.dumps(r,sort_keys=True)+'\n')
        for p,h in inputs.items():
            if sha(p)!=h:raise ValueError('Propagation inputs changed')
        receipt=dict(creator='Navneet Prabhakar',kind='actual-global-near-component-propagation-v1',complete=True,records=len(records),components=len(output['components']),
            near_facet_links_consumed=output['near_facet_links_consumed'],candidate_withheld=output['candidate_withheld'],
            roots_sha256=sha(OUT/'roots.jsonl'),components_sha256=sha(OUT/'components.jsonl'),inputs_sha256=sha(OUT/'inputs.json'),
            training_approved=False,new_split_assignment=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='All audited near-facet pairs consumed over inherited exact+containment roots, raw-identical facet mappings verified and fixed/nonapproval flags propagated without changing original record labels. Independent component audit and finite source admission/splits remain required.')
        for p in [OUT/'report.json',Path('reports/global-near-components.json')]:p.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        print(json.dumps(receipt,indent=2))
    finally:source.close();near.close()

if __name__=='__main__':main()
