"""Independently traverse the full source graph after terminal near propagation."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import sqlite3
from slm.data.near_component_audit import reconstruct,verify
from slm.data.stream_hash import sha

ROOT=Path('data/global-near-components-v1')
PLAN=Path('configs/global-near-facets-v3.json')

def json_lines(path):
    with Path(path).open() as inp:
        for line in inp:yield json.loads(line)

def main():
    if not (ROOT/'report.json').is_file():raise ValueError('Actual terminal component propagation required before independent audit')
    receipt=json.loads((ROOT/'report.json').read_text())
    if receipt.get('complete') is not True or receipt.get('new_split_assignment') is not False:raise ValueError('Complete pre-split component receipt required')
    for name,field in [('roots.jsonl','roots_sha256'),('components.jsonl','components_sha256'),('inputs.json','inputs_sha256')]:
        if sha(ROOT/name)!=receipt[field]:raise ValueError('Component artifact differs from receipt')
    inputs=json.loads((ROOT/'inputs.json').read_text())
    for p,h in inputs.items():
        if sha(p)!=h:raise ValueError('Component source/proof input changed')
    plan=json.loads(PLAN.read_text());near_report=json.loads(Path('data/global-near-facets-v3/report.json').read_text())
    proof=json.loads(Path('reports/global-near-facets-check.json').read_text())
    if proof.get('passed') is not True or proof['report_sha256']!=sha('data/global-near-facets-v3/report.json'):raise ValueError('Near terminal proof differs')
    if near_report['plan_sha256']!=sha(PLAN):raise ValueError('Frozen near execution plan differs')
    if sha(plan['source_database'])!=plan['input_bindings'][plan['source_database']]:raise ValueError('Immutable source database changed')
    if sha('data/global-near-facets-v3/near.sqlite')!=near_report['database_sha256']:raise ValueError('Terminal near database changed')
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    near=sqlite3.connect('file:'+str(Path('data/global-near-facets-v3/near.sqlite').resolve())+'?mode=ro',uri=True)
    try:
        source.row_factory=sqlite3.Row
        records=[dict(r) for r in source.execute('SELECT sid,eid,candidate,fixed,blocked FROM records ORDER BY sid')]
        roots=[]
        for sid,r in enumerate(json_lines(plan['inherited_roots'])):
            if r['sid']!=sid:raise ValueError('Inherited root identities differ')
            roots.append(r['root'])
        expected=reconstruct(records,roots,near.execute('SELECT sid,source_sid FROM facet_sources ORDER BY sid,source_sid'),near.execute('SELECT a,b FROM near_pairs ORDER BY a,b'),max_edges=2000000)
        if expected['near_facet_links_consumed']!=proof['all_reported_near_pairs_recomputed']:raise ValueError('All terminal verified near links must be consumed')
        counts=verify(expected,json_lines(ROOT/'roots.jsonl'),json_lines(ROOT/'components.jsonl'),receipt)
        result=dict(creator='Navneet Prabhakar',kind='actual-global-near-component-independent-check-v1',passed=True,report_sha256=sha(ROOT/'report.json'),checker_sha256=sha(__file__),audit_module_sha256=sha('src/slm/data/near_component_audit.py'),**counts,
            training_approved=False,new_split_assignment=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='Independent breadth-first source graph reconstructs every component/root/group identity and heldout/nonapproval flag from inherited exact+containment roots, raw-facet mappings and all verified near links. Graph limited to2Munique source edges; reaching bound refuses full acceptance. Source record labels remain immutable; no new split or training admission claim.')
        Path('reports/global-near-components-check.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
    finally:source.close();near.close()

if __name__=='__main__':main()
