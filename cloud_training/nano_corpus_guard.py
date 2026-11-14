"""Read-only frozen-corpus custody checks used before data admission/evaluation."""
import hashlib,json
from pathlib import Path

def verify_freeze(root):
    root=Path(root).resolve()
    if (root/'release-use.json').exists():raise ValueError('Release already claimed; do not reuse for model selection')
    freeze=json.loads((root/'freeze.json').read_text())
    if freeze.get('schema')!=1 or freeze.get('release_model_exposures')!=0:raise ValueError('Release is absent or already exposed; it cannot be reused as pristine acceptance')
    files=freeze.get('files',{})
    required={'candidate-4k/manifest.json','candidate-4k/train.jsonl','candidate-4k/validation.jsonl','candidate-4k/admission.json','release-suite.json','semantic-review.json','quality-contract.json'}
    if not required<=set(files):raise ValueError('Missing required frozen artifacts')
    for name,wanted in files.items():
        path=(root/name).resolve()
        if root not in path.parents or not path.is_file():raise ValueError('Invalid frozen artifact path: '+name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=wanted:raise ValueError('Frozen artifact changed: '+name)
    return {'status':'verified_not_training_authorization','files':len(files),'release_model_exposures':0}

def source_groups(rows):
    result=set()
    for row in rows:
        p=row.get('provenance',{});group=p.get('source_group',p.get('group'))
        if not isinstance(group,str) or not group:raise ValueError('Missing source group')
        result.add(group)
    return result

def reject_split_leakage(train,development,release):
    groups=[source_groups(train),source_groups(development),{s.get('source_group') for s in release['sessions']}]
    if None in groups[2] or '' in groups[2]:raise ValueError('Missing release source group')
    if any(groups[i]&groups[j] for i in range(3) for j in range(i)):raise ValueError('Source group crosses split boundary')
    norm=lambda text:' '.join(text.casefold().split())
    # Whole ordered user sequences avoid mistaking a generic follow-up for a leaked scenario.
    sequences=[{tuple(norm(m['content']) for m in r['messages'] if m['role']=='user') for r in rows} for rows in [train,development]]
    sequences.append({tuple(norm(t['user']) for t in s['turns']) for s in release['sessions']})
    if any(sequences[i]&sequences[j] for i in range(3) for j in range(i)):raise ValueError('User scenario crosses split boundary')
    release_prompts={norm(t['user']) for s in release['sessions'] for t in s['turns']}
    for rows in [train,development]:
        if any(norm(m['content']) in release_prompts for r in rows for m in r['messages'] if m['role']=='user'):raise ValueError('Release prompt leaked into training/development')
    return {'source_group_overlap':0,'scenario_overlap':0,'release_prompt_overlap':0}


def claim_release(root, *, checkpoint_sha256, suite_sha256, output):
    import datetime,re
    root=Path(root).resolve();verify_freeze(root)
    if any(not isinstance(s,str) or not re.fullmatch('[0-9a-f]{64}',s) for s in [checkpoint_sha256,suite_sha256]):raise ValueError('Invalid release identity')
    actual=hashlib.sha256((root/'release-suite.json').read_bytes()).hexdigest()
    if actual!=suite_sha256:raise ValueError('Release suite differs from frozen packet')
    claim={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checkpoint_manifest_sha256':checkpoint_sha256,'suite_sha256':suite_sha256,'output':str(output),'policy':'One selected candidate only. An incomplete attempt remains claimed; no automatic reuse or tuning on release outputs.'}
    with (root/'release-use.json').open('x') as stream:json.dump(claim,stream,indent=2);stream.write('\n')
    return claim
