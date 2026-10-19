"""Terminal-only read-only audit of the actual full near-facet job."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import sqlite3
from slm.data.near_audit import require_terminal,verify_source_mappings,verify_feature_index,verify_prefix_counts,verify_near_pairs
from slm.data.stream_hash import sha

ROOT=Path('data/global-near-facets-v3');PLAN=Path('configs/global-near-facets-v3.json')

def main():
    report=require_terminal(ROOT)  # Refuse live jobs before database allocation.
    plan=json.loads(PLAN.read_text())
    if report['plan_sha256']!=sha(PLAN):raise ValueError('Near execution plan changed')
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Frozen near input changed')
    if sha(ROOT/'near.sqlite')!=report['database_sha256']:raise ValueError('Final near database changed')
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    near=sqlite3.connect('file:'+str((ROOT/'near.sqlite').resolve())+'?mode=ro',uri=True)
    near.execute('PRAGMA cache_size=-8192');near.execute('PRAGMA temp_store=FILE')
    try:
        if near.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('Near SQLite integrity failed')
        if near.execute('SELECT complete FROM status').fetchall()!=[(1,)]:raise ValueError('Near engine terminal marker missing')
        mappings=verify_source_mappings(source,near);features=verify_feature_index(near);prefixes=verify_prefix_counts(near);pairs=verify_near_pairs(near)
        for k,v in mappings.items():
            if report[k]!=v:raise ValueError('Reported source coverage differs')
        for k in ('unique_raw_facets','full_feature_occurrences'):
            if report[k]!=features[k]:raise ValueError('Reported full feature coverage differs')
        if mappings['records']!=plan['expected_records'] or prefixes!=features['unique_raw_facets']:raise ValueError('Incomplete source/prefix coverage')
        if pairs!=report['qualifying_facet_pairs'] or report['candidate_pairs_verified']>plan['max_pair_checks']:raise ValueError('Reported near pair accounting differs')
        result=dict(creator='Navneet Prabhakar',kind='actual-global-near-facet-check-v1',passed=True,
            report_sha256=sha(ROOT/'report.json'),checker_sha256=sha(__file__),audit_module_sha256=sha('src/slm/data/near_audit.py'),
            source_coverage=mappings,feature_checks=features,all_prefix_counts_checked=prefixes,all_reported_near_pairs_recomputed=pairs,
            training_approved=False,component_overlay_applied=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='All original eligible source mappings/raw facet identities, feature occurrence/frequency counts, prefix lengths and reported full reference pair thresholds verified. Shingle-content posting identities recomputed on128fixed-hash facets. Retrieval recall relies on complete frozen prefix engine and brute-force fixtures, not a global all-pairs replay. Inherited roots/witness flags must be consumed in a separate checked component overlay before splits/admission.')
        Path('reports/global-near-facets-check.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
    finally:source.close();near.close()

if __name__=='__main__':main()
