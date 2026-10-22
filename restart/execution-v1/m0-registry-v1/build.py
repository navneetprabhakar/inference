"""Materialize existing split/protection identities; never authors evaluation text."""
import collections,csv,datetime,hashlib,json,sqlite3
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[3];BASE=PROJECT/'restart/execution-v1';ROOT=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def build():
    out=ROOT/'artifacts';out.mkdir()
    audit=PROJECT/'restart/corpus-audit-v1';receipt=json.loads((audit/'receipt.json').read_bytes())
    database=audit/'audit.sqlite';expected=next(r['sha256'] for r in receipt['outputs'] if r['name']=='audit.sqlite')
    if sha(database)!=expected:raise ValueError('Historical audit database changed')
    leakage=json.loads((BASE/'known-leakage-recheck-v1.json').read_bytes())
    accepted=PROJECT/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
    if sha(accepted)!=leakage['source_manifest_sha256']:raise ValueError('Admitted source manifest changed')
    inputs={str(p.relative_to(PROJECT)):sha(p) for p in (database,audit/'receipt.json',accepted,BASE/'known-leakage-recheck-v1.json',BASE/'M0_CONTRACT.md',BASE/'disk-budget.json')}
    ids={};families={};split_counts=collections.Counter()
    with accepted.open(newline='') as f,(out/'admitted-documents.jsonl').open('x') as dest:
        for row in csv.DictReader(f):
            key=row['audit_id'];family=row['family_id'];split=row['split']
            if key in ids or family in families and families[family]!=split:raise ValueError('Duplicated identity or cross-split family')
            ids[key]=row;families[family]=split;split_counts[split]+=1
            dest.write(json.dumps(dict(audit_id=key,source=row['source'],split=split,family_id=family,normalized_sha256=row['normalized_sha256'],original_text_sha256=row['original_text_sha256'],source_reference=row['original_reference']),sort_keys=True)+'\n')
    loss_streams={};seen=set()
    with (out/'m1-loss-assignments.jsonl').open('x') as dest:
        for folder,split in [('data-train','train'),('data-dev','development'),('data-final','test')]:
            directory=BASE/folder;manifest=json.loads((directory/'manifest.json').read_bytes())
            inputs[str((directory/'manifest.json').relative_to(PROJECT))]=sha(directory/'manifest.json')
            for filename,pin in manifest['files'].items():
                if sha(directory/filename)!=pin:raise ValueError('Loss stream file changed')
            count=targets=0
            with (directory/'index.jsonl').open() as f:
                for line in f:
                    item=json.loads(line);key=item['audit_id'];source=ids[key]
                    if key in seen or item['split']!=split or source['split']!=split or any(item[k]!=source[k] for k in ('family_id','normalized_sha256','original_text_sha256')):
                        raise ValueError('Loss stream identity/split mismatch')
                    seen.add(key);count+=1;targets+=item['targets']
                    dest.write(json.dumps(dict(stream=folder,**{k:item[k] for k in ('audit_id','family_id','targets','full_document_targets','partial')}),sort_keys=True)+'\n')
            if count!=manifest['documents'] or targets!=manifest['targets']:raise ValueError('Loss stream counts differ')
            loss_streams[folder]=dict(documents=count,targets=targets,families=manifest['families'],role='training' if folder=='data-train' else 'development-only' if folder=='data-dev' else 'sealed final loss')
    db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True);held_counts=collections.Counter()
    try:
        with (out/'historical-heldout.jsonl').open('x') as dest:
            for key,source,normalized_sha,family,reference in db.execute('SELECT id,source,sha,families,reference FROM docs WHERE held=1 ORDER BY id'):
                if str(key) in ids:raise ValueError('Historical heldout identity admitted')
                held_counts[source]+=1
                dest.write(json.dumps(dict(audit_id=key,source=source,normalized_sha256=normalized_sha,family_metadata=json.loads(family),reference=reference,role='protected-never-training'),sort_keys=True)+'\n')
        legacy_ids={str(row[0]) for row in db.execute('SELECT id FROM protections')}
    finally:db.close()
    overlap=BASE/'m2-intake/individual-salvage-v1/overlap-v1'
    protection_ids=json.loads((overlap/'protection-identities.json').read_bytes())
    if len(protection_ids)!=len(set(protection_ids)):raise ValueError('Duplicate protection identity')
    if {v.split(':',1)[1] for v in protection_ids if v.startswith('legacy:')}!=legacy_ids:raise ValueError('Legacy protection omitted')
    protection_counts=collections.Counter();count=0
    with (overlap/'protections.tsv').open() as f,(out/'protected-text-units.jsonl').open('x') as dest:
        for line in f:
            number,text=line.rstrip('\n').split('\t',1)
            if int(number)!=count:raise ValueError('Protection ordinal changed')
            identity=protection_ids[count];group='legacy' if identity.startswith('legacy:') else ':'.join(identity.split(':')[:2]);protection_counts[group]+=1
            dest.write(json.dumps(dict(ordinal=count,identity=identity,normalized_text_sha256=hashlib.sha256(text.encode()).hexdigest(),origin_group=group,role='protected-never-added-to-training'),sort_keys=True)+'\n');count+=1
    if count!=len(protection_ids) or count!=8841:raise ValueError('Protection coverage changed')
    for name in ('protection-identities.json','protections.tsv','verified-summary.json','result.json','containment-independent-verification.json'):
        p=overlap/name;inputs[str(p.relative_to(PROJECT))]=sha(p)
    summary=json.loads((overlap/'verified-summary.json').read_bytes())
    for name,pin in summary['required_evidence_sha256'].items():
        if sha(overlap/name)!=pin:raise ValueError('Overlap evidence changed')
    evaluation=BASE/'evaluation-frozen-v1';manifest=json.loads((evaluation/'manifest.json').read_bytes())
    if sha(evaluation/'manifest.json')!=leakage['evaluation_manifest_sha256']:raise ValueError('Evaluation manifest changed')
    inputs[str((evaluation/'manifest.json').relative_to(PROJECT))]=sha(evaluation/'manifest.json')
    combined=BASE/'evaluation-draft/combined-audit.json'
    if sha(combined)!=manifest['combined_audit_sha256']:raise ValueError('Combined audit changed')
    counts=json.loads(combined.read_bytes())['counts'];diagnostics=[]
    for rel,pin in manifest['files_sha256'].items():
        if sha(evaluation/rel)!=pin:raise ValueError('Frozen diagnostic changed')
        split,filename=rel.split('/');kind=filename.removesuffix('.jsonl')
        diagnostics.append(dict(path=str((evaluation/rel).relative_to(PROJECT)),sha256=pin,split=split,kind=kind,items=counts[split+':'+kind],role='development-only' if split=='development' else 'sealed final research',denominator='matched pairs' if kind=='copy' else 'items',independent_human_certification=False))
    (out/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    result=dict(schema=1,status='M0_EXISTING_EVIDENCE_REGISTRY_VERIFIED',created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        admitted_split_documents=dict(split_counts),admitted_families=len(families),loss_streams=loss_streams,historical_heldout_records=dict(held_counts),
        protected_text_units=dict(protection_counts),diagnostic_files=len(diagnostics),input_sha256=inputs,
        files={p.name:sha(p) for p in sorted(out.iterdir())},
        boundary='Identity/hash registry of already-authorized artifacts; does not admit data, author new tests, reopen a candidate or certify semantic ancestry.',
        remaining_M0=['Freeze concrete M3 probe budgets once source/tokenizer inputs are nominated','Future conversation/template/tool-workflow registries must be materialized before their respective training; these payloads do not yet exist'],
        later_release_prerequisites=['Two independent blind human graders and adjudication; assistant research proxy does not satisfy release grading'],
        notes=['Historical audit database verified against original receipt; original raw source files were not all reread in this registry build','Protected unit counts include variants and repeated content; they are not independent evaluation scenarios','Full admitted split counts differ from M1 loss-evaluation subset counts','No historical record or protected unit was removed; unresolved near/semantic ancestry limitations remain'])
    (ROOT/'registry.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    result=build();print(json.dumps({k:result[k] for k in ('status','admitted_split_documents','loss_streams','historical_heldout_records','protected_text_units')},indent=2))
