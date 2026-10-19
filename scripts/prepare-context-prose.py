#!/usr/bin/env python3
"""Prepare actual source-bound prose candidates and re-group before admission."""
# Creator: Navneet Prabhakar
from pathlib import Path
import json
import time
from slm.data.context import prepare
from slm.data.build import read_source,verify
from slm.data.staging import stage,canonical
from slm.data.quality_audit import audit,LIMITS as QUALITY_LIMITS
from slm.data.tokenized import sha
from slm.data.review import training_examples


def main():
    parent=Path('data/complete-small-source-v1/staged').resolve()
    root=Path('data/context-prose-candidates-v1').resolve()
    candidate=prepare(parent,'configs/context-prose-candidate-v1.json',root/'extracted')
    descriptors={read_source(p).source_id:p.resolve() for p in Path('data/audit-v1').glob('*/source/source.json')}
    descriptors['databricks/databricks-dolly-15k']=Path('data/dolly-complete-v1/source.json').resolve()
    specs=[]
    for name,path in sorted(descriptors.items()):
        incoming=root/'extracted/candidates.jsonl' if name=='databricks/databricks-dolly-15k' else root/(name.split('/')[-1]+'-empty.jsonl')
        if name!='databricks/databricks-dolly-15k':incoming.write_text('')
        specs.append(dict(path=str(incoming),sha256=sha(incoming),source_record=str(path),adapter='canonical'))
    limits=dict(max_db_bytes=1024*1024*1024,max_input_bytes=64*1024*1024,max_records=20000,
                max_record_bytes=1024*1024,max_pair_checks=2000000,max_shingles=100000)
    spec=dict(inputs=specs,limits=limits,frozen_dataset=str(parent))
    (root/'staging-spec.json').write_text(canonical(spec)+'\n')
    started=time.monotonic();grouped=stage(specs,root/'staged',limits=limits,frozen_dataset=parent);stage_seconds=time.monotonic()-started
    # Original frozen heldouts remain original records. Audit all; only derived
    # passages are candidates for later scoped admission, never these originals.
    quality_spec=dict(dataset=str(root/'staged'),descriptor=str(Path('data/language-detector-v4/detector.json').resolve()),
        limits=QUALITY_LIMITS,seed='context-prose-audit-20261019-v1',groups_per_stratum=3,window_characters=2048)
    (root/'quality-spec.json').write_text(canonical(quality_spec)+'\n')
    quality=audit(output=root/'quality',**quality_spec)
    split_counts={};chars={};derived=0;original_heldouts=0;protected=0
    for split in ('train','validation','test'):
        for p in (root/'staged').glob(split+'-*.jsonl'):
            for line in p.open():
                row=json.loads(line);proof=row['validation_results'].get('context_derivation')
                if proof:
                    derived+=1;split_counts[split]=split_counts.get(split,0)+1
                    chars[split]=chars.get(split,0)+len(row['messages'][0]['content'])
                    priority={'train':0,'validation':1,'test':2}
                    if priority[split]<priority[proof['parent_split']]:raise AssertionError('Derived heldout demoted')
                    if proof['parent_split']!='train':protected+=1
                    if [m['role'] for m in row['messages']]!=['text']:raise AssertionError('Answer target retained')
                else:
                    original_heldouts+=1
                    if split=='train':raise AssertionError('Frozen original admitted to train')
    verify(root/'staged')
    try:list(training_examples(root/'staged'))
    except ValueError as e:refusal=str(e)
    else:raise AssertionError('Candidate corpus accepted by training reader')
    report=dict(creator='Navneet Prabhakar',candidate_extraction=candidate,staging=grouped,quality=quality,
        stage_wall_seconds=stage_seconds,derived_retained=derived,derived_splits=split_counts,derived_characters=chars,
        frozen_original_heldout_rows=original_heldouts,retained_derived_heldouts_protected=protected,
        training_reader_refusal=refusal,parent_manifest_sha256=sha(parent/'manifest.json'),
        staged_manifest_sha256=sha(root/'staged/manifest.json'),policy_sha256=sha('configs/context-prose-candidate-v1.json'),
        implementation_sha256=sha('src/slm/data/context.py'),script_sha256=sha(__file__),
        actual_source_or_row_approvals=0,neural_updates=0,new_teacher_launches=0,cloud_jobs=0,
        limitation='Derived passages still sample-only; new grouping, detector observations and lexical screening do not establish training admission or corpus quality.')
    Path('reports/milestone-thirty-eight-context-candidates.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('derived_retained','derived_splits','derived_characters','frozen_original_heldout_rows','training_reader_refusal')},indent=2))


if __name__=='__main__':main()
