"""Parent-only revalidation of known lexical/family leakage evidence.

Uses pinned audit outputs and the exact admitted subset. This does not certify
unknown upstream ancestry, factual accuracy, or semantic paraphrase separation.
"""
import csv,json
from pathlib import Path
from . import evaluation_snapshot,numerical_prerequisites
from .evaluation_snapshot import _file
from .numerical_prerequisites import digest

AUDIT_RECEIPT='96babb3ea5c410e6f8ebd2a987d036059eeebe57825a52c7cd836337ca00265e'


def audit_rows(accepted,mechanical,edges,protected):
    source={row['audit_id']:row for row in mechanical};selected={};hashes=set();families={}
    fields=('source','split','family_id','normalized_sha256','original_text_sha256')
    for row in accepted:
        key=row['audit_id']
        if key in selected or key not in source or any(row[field]!=source[key][field] for field in fields):
            raise ValueError('Admitted release is not an unchanged unique audited subset')
        if row['normalized_sha256'] in hashes:raise ValueError('Admitted exact duplicate')
        if row['family_id'] in families and families[row['family_id']]!=row['split']:raise ValueError('Cross-split family overlap')
        hashes.add(row['normalized_sha256']);families[row['family_id']]=row['split'];selected[key]=row
    if not selected:raise ValueError('Empty admitted release')
    parents={}
    def root(node):
        parents.setdefault(node,node)
        while parents[node]!=node:
            parents[node]=parents[parents[node]];node=parents[node]
        return node
    for a,b in edges:
        x,y=root(a),root(b)
        if x!=y:parents[x]=y
    components=set()
    for key in selected:
        component=root(key)
        if component in components:raise ValueError('Multiple admitted members of known exact/near component')
        components.add(component)
    if set(protected)&set(selected):raise ValueError('Known protected text retained')
    return selected


def verify(project):
    project=Path(project).resolve(strict=True);execution=project/'restart/execution-v1';audit=project/'restart/corpus-audit-v1'
    numerical_prerequisites.verify(project)
    manifest=json.loads(_file(execution/'evaluation-frozen-v1','manifest.json').read_bytes())
    receipt_path=_file(audit,'receipt.json')
    if digest(receipt_path)!=AUDIT_RECEIPT:raise ValueError('Changed source audit receipt')
    receipt=json.loads(receipt_path.read_bytes());pins={entry['name']:entry['sha256'] for entry in receipt['outputs']}
    needed=('accepted-manifest.csv','near-pairs.tsv','containment-hits.tsv','results.json')
    for name in needed:
        if digest(_file(audit,name))!=pins[name]:raise ValueError('Changed source audit evidence: '+name)
    result=json.loads((audit/'results.json').read_bytes())
    required=('zero_known_cross_split_family_overlap','zero_normalized_exact_duplicates','one_representative_per_verified_near_component','zero_known_protected_family_members')
    if any(result['validation'].get(key) is not True for key in required) or result['rejected_hash_false_positive_edges']!=0:
        raise ValueError('Source audit has unresolved exclusions')
    source_path=_file(project,'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv')
    if digest(source_path)!=manifest['source_manifest_sha256']:raise ValueError('Changed admitted release')
    with source_path.open(newline='') as f:accepted=list(csv.DictReader(f))
    with (audit/'accepted-manifest.csv').open(newline='') as f:mechanical=list(csv.DictReader(f))
    with (audit/'near-pairs.tsv').open() as f:edges=[tuple(line.rstrip('\n').split('\t')[:2]) for line in f]
    with (audit/'containment-hits.tsv').open() as f:protected={line.split('\t',1)[0] for line in f}
    selected=audit_rows(accepted,mechanical,edges,protected)
    seen_ids=set();seen_families=set();streams={}
    for folder,split in (('data-train','train'),('data-dev','development'),('data-final','test')):
        rows=[json.loads(line) for line in (execution/folder/'index.jsonl').read_bytes().splitlines()]
        ids={r['audit_id'] for r in rows};families={r['family_id'] for r in rows}
        if len(ids)!=len(rows) or ids&seen_ids or families&seen_families:raise ValueError('Loss streams overlap')
        for row in rows:
            original=selected.get(row['audit_id'])
            if original is None or row['split']!=split or any(row[k]!=original[k] for k in ('split','family_id','normalized_sha256','original_text_sha256')):
                raise ValueError('Loss row differs from admitted source')
        seen_ids|=ids;seen_families|=families;streams[folder]={'documents':len(rows),'families':len(families),'targets':sum(r['targets'] for r in rows)}
    draft=execution/'evaluation-draft';combined=json.loads((draft/'combined-audit.json').read_bytes())
    if combined['hits'] or combined['cross_split_source_family_collisions']:raise ValueError('Combined diagnostics contain known overlaps')
    for relative in ('grammar-v2-screen.json','grounded-v3-verification.json','authored-narratives-v2/verification.json','copy-probes-v2/verification.json'):
        evidence=json.loads(_file(draft,relative).read_bytes())
        if evidence['hits'] or evidence.get('unexpected_match_count',0)!=0:raise ValueError('Known diagnostic overlap')
    return {'status':'KNOWN_LEAKAGE_RECHECK_PASS','admitted_documents':len(selected),'loss_streams':streams,
        'known_cross_split_exact_matches':0,'known_cross_split_family_matches':0,'known_retained_near_component_pairs':0,
        'known_unexpected_diagnostic_matches':0,'source_manifest_sha256':manifest['source_manifest_sha256'],
        'evaluation_manifest_sha256':evaluation_snapshot.MANIFEST_SHA256,'audit_receipt_sha256':AUDIT_RECEIPT,
        'rechecked_audit_files':{name:pins[name] for name in needed},
        'limitations':result['limits']+combined['limitations'],'scope':'Known audited lexical/family exclusions only; no unknown semantic ancestry certification'}
