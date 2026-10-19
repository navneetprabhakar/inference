#!/usr/bin/env python3
"""Combine local full-source instruction and dialogue candidates; never admit."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import time
from slm.data.build import verify,read_source
from slm.data.schema import digest
from slm.data.staging import stage,canonical
from slm.data.tokenized import sha
from slm.data.quality_audit import audit,LIMITS
from slm.data.review import training_examples


def main():
    root=Path('data/iteration-two-foundation-candidates-v1');root.mkdir()
    parent=Path('data/iteration-two-dialogue-preparation-v1/staged').resolve()
    original=Path('data/complete-small-source-v1/staged').resolve()
    dialogue=Path('data/iteration-two-dialogue-screen-v2').resolve()
    for p in (parent,original,dialogue):verify(p)
    screen=json.loads((dialogue/'report.json').read_text())
    if (screen['policy_sha256']!=sha('configs/iteration-two-dialogue-screen-v2.json')
        or screen['implementation_sha256']!=sha('src/slm/data/dialogue_screen.py')
        or screen['language_implementation_sha256']!=sha('src/slm/data/dialogue_language.py')):raise ValueError('Current v2 screen binding differs')
    decisions_path=Path('data/delegated-source-review-v1/decisions.json');decisions=json.loads(decisions_path.read_text())
    if decisions['dataset_manifest_sha256']!=sha(original/'manifest.json') or decisions['human_attestation'] is not False:
        raise ValueError('Original delegated review binding differs')
    incoming=root/'dolly-candidates.jsonl';count=0;prior_counts=Counter()
    with incoming.open('w') as out:
        for split in ('train','validation','test'):
            for path in sorted(original.glob(split+'-*.jsonl')):
                for line in path.open():
                    row=json.loads(line)
                    if row['source']!='databricks/databricks-dolly-15k':continue
                    parent_hash=digest(row);prior=decisions['examples'].get(row['example_id'])
                    if prior and prior['record_sha256']!=parent_hash:raise ValueError('Prior row review binding differs')
                    proof=dict(method='complete-dolly-instruction-foundation-candidate-v1',parent_manifest_sha256=sha(original/'manifest.json'),
                        parent_record_sha256=parent_hash,parent_split=row['split'],
                        language_assessment='not_individually_verified',quality_assessment='not_individually_verified',training_eligible=False)
                    if prior:
                        proof['prior_review']=dict(review_file_sha256=sha(decisions_path),**prior['decision']);prior_counts[str(prior['decision']['approved'])]+=1
                    row['validation_results']['foundation_dialogue_candidate']=proof
                    out.write(canonical(row)+'\n');count+=1
    descriptors={read_source(p).source_id:p.resolve() for p in Path('data/audit-v1').glob('*/source/source.json')}
    descriptors['databricks/databricks-dolly-15k']=Path('data/dolly-complete-v1/source.json').resolve()
    specs=[]
    for source,path in sorted(descriptors.items()):
        p=incoming if source=='databricks/databricks-dolly-15k' else dialogue/'candidates.jsonl' if source=='OpenAssistant/oasst2' else root/(source.split('/')[-1]+'-empty.jsonl')
        if source not in ('databricks/databricks-dolly-15k','OpenAssistant/oasst2'):p.write_text('')
        specs.append(dict(path=str(p.resolve()),sha256=sha(p),source_record=str(path),adapter='canonical'))
    limits=dict(max_db_bytes=3*1024**3,max_input_bytes=256*1024**2,max_records=50000,
                max_record_bytes=1024**2,max_pair_checks=8000000,max_shingles=100000)
    spec=dict(inputs=specs,limits=limits,frozen_dataset=str(parent))
    (root/'staging-spec.json').write_text(canonical(spec)+'\n')
    started=time.monotonic();staged=stage(specs,root/'staged',limits=limits,frozen_dataset=parent)
    seconds=time.monotonic()-started;print(json.dumps(dict(phase='staged',rows=staged['retained_examples'],seconds=seconds)),flush=True)
    quality_spec=dict(dataset=str((root/'staged').resolve()),descriptor=str(Path('data/language-detector-v4/detector.json').resolve()),
        limits={**LIMITS,'max_input_bytes':256*1024**2,'max_records':50000,'max_windows':250000,'max_db_bytes':1024**3,'detector_seconds':60},
        seed='iteration-two-foundation-audit-20261019-v1',groups_per_stratum=2,window_characters=2048)
    (root/'quality-spec.json').write_text(canonical(quality_spec)+'\n');quality=audit(output=root/'quality',**quality_spec)
    frozen={};found={};candidate_counts=Counter()
    for split in ('validation','test'):
        for path in parent.glob(split+'-*.jsonl'):
            for line in path.open():
                row=json.loads(line);frozen[row['example_id']]=row
    priority={'train':0,'validation':1,'test':2}
    for split in ('train','validation','test'):
        for path in (root/'staged').glob(split+'-*.jsonl'):
            for line in path.open():
                row=json.loads(line)
                if row['example_id'] in frozen:
                    old=frozen[row['example_id']]
                    if row['messages']!=old['messages'] or priority[row['split']]<priority[old['split']]:raise AssertionError('Frozen heldout lost or demoted')
                    found[row['example_id']]=True
                if row['validation_results'].get('dialogue_candidate') or row['validation_results'].get('foundation_dialogue_candidate'):
                    candidate_counts[row['source']+'|'+split]+=1
    if set(found)!=set(frozen):raise AssertionError('Missing frozen heldouts')
    try:list(training_examples(root/'staged'))
    except ValueError as exc:refusal=str(exc)
    else:raise AssertionError('Candidate pool accepted by training reader')
    result=dict(creator='Navneet Prabhakar',training_eligible=False,release='sample_only',staging=staged,stage_seconds=seconds,quality=quality,
        original_dolly_rows=count,prior_dolly_judgment_counts=dict(prior_counts),candidate_rows_by_source_split=dict(candidate_counts),
        frozen_heldout_rows_verified=len(frozen),training_reader_refusal=refusal,
        staged_manifest_sha256=sha(root/'staged/manifest.json'),quality_manifest_sha256=sha(root/'quality/manifest.json'),
        original_manifest_sha256=sha(original/'manifest.json'),frozen_parent_manifest_sha256=sha(parent/'manifest.json'),
        dialogue_screen_manifest_sha256=sha(dialogue/'manifest.json'),script_sha256=sha(__file__),new_neural_updates=0,new_teacher_calls=0,new_cloud_jobs=0,
        scope='Broader local full-source foundation candidates only. Prior approvals/rejections are evidence, not inherited whole-corpus approval. No source/content/privacy/factual certification, tokenization fit or training admission.')
    (root/'preparation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    Path('reports/milestone-forty-six-foundation-preparation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ('original_dolly_rows','frozen_heldout_rows_verified','candidate_rows_by_source_split','training_reader_refusal')},indent=2),flush=True)


if __name__=='__main__':main()
