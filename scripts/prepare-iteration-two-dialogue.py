#!/usr/bin/env python3
"""Regroup actual dialogue candidates with all prior heldout references, then audit."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import time
from slm.data.build import read_source,verify
from slm.data.staging import stage,canonical
from slm.data.tokenized import sha
from slm.data.quality_audit import audit,LIMITS
from slm.data.review import training_examples


def main():
    candidates=Path('data/iteration-two-dialogue-candidates-v1')
    root=Path('data/iteration-two-dialogue-preparation-v1');root.mkdir()
    parent=Path('data/context-prose-candidates-v1/staged').resolve();verify(parent)
    candidate_report=json.loads((candidates/'report.json').read_text())
    if (candidate_report['candidates_sha256']!=sha(candidates/'candidates.jsonl')
        or candidate_report['implementation_sha256']!=sha('src/slm/data/dialogue_candidates.py')
        or candidate_report['training_eligible'] is not False):raise ValueError('Candidate binding differs')
    # Exact development prompts are quarantined; grouping subsequently propagates
    # their strongest partition to all related source paths. This is not semantic
    # scenario-family detection or a blanket ban on teaching names/arithmetic.
    assessment=Path('reports/milestone-forty-three-conversation.json')
    reserved={' '.join(t['user'].casefold().split()) for t in json.loads(assessment.read_text())['turns']}
    incoming=root/'input.jsonl';reserved_hits=0
    with incoming.open('w') as out:
        for line in (candidates/'candidates.jsonl').open():
            row=json.loads(line)
            if any(m['role']=='user' and ' '.join(m['content'].casefold().split()) in reserved for m in row['messages']):
                row['split']='test';reserved_hits+=1
            out.write(canonical(row)+'\n')
    descriptors={read_source(p).source_id:p.resolve() for p in Path('data/audit-v1').glob('*/source/source.json')}
    descriptors['databricks/databricks-dolly-15k']=Path('data/dolly-complete-v1/source.json').resolve()
    specs=[]
    for name,path in sorted(descriptors.items()):
        p=incoming if name=='OpenAssistant/oasst2' else root/(name.split('/')[-1]+'-empty.jsonl')
        if name!='OpenAssistant/oasst2':p.write_text('')
        specs.append(dict(path=str(p.resolve()),sha256=sha(p),source_record=str(path),adapter='canonical'))
    limits=dict(max_db_bytes=2*1024**3,max_input_bytes=256*1024**2,max_records=30000,
                max_record_bytes=1024**2,max_pair_checks=4000000,max_shingles=100000)
    spec=dict(inputs=specs,limits=limits,frozen_dataset=str(parent))
    (root/'staging-spec.json').write_text(canonical(spec)+'\n')
    started=time.monotonic();staged=stage(specs,root/'staged',limits=limits,frozen_dataset=parent)
    stage_seconds=time.monotonic()-started
    print(json.dumps(dict(phase='staged',rows=staged['retained_examples'],seconds=stage_seconds)),flush=True)
    quality_limits={**LIMITS,'max_input_bytes':256*1024**2,'max_records':30000,'max_windows':200000,
                    'max_db_bytes':1024**3,'detector_seconds':60}
    quality_spec=dict(dataset=str((root/'staged').resolve()),descriptor=str(Path('data/language-detector-v4/detector.json').resolve()),
                      limits=quality_limits,seed='iteration-two-dialogue-audit-20261019-v1',groups_per_stratum=2,window_characters=2048)
    (root/'quality-spec.json').write_text(canonical(quality_spec)+'\n')
    quality=audit(output=root/'quality',**quality_spec)
    before={}
    for split in ('validation','test'):
        for p in parent.glob(split+'-*.jsonl'):
            for line in p.open():
                row=json.loads(line);before[row['example_id']]=row
    retained={};splits=Counter();characters=Counter();train_nodes={};new=0
    for split in ('train','validation','test'):
        for p in (root/'staged').glob(split+'-*.jsonl'):
            for line in p.open():
                row=json.loads(line)
                if row['example_id'] in before:retained[row['example_id']]=row
                if row['validation_results'].get('dialogue_candidate'):
                    new+=1;splits[split]+=1;characters[split]+=sum(len(m['content']) for m in row['messages'])
                    if split=='train':
                        for node,m in zip(row['lineage'],row['messages']):
                            if node in train_nodes and train_nodes[node]!=m['content']:raise AssertionError('Shared message text changed')
                            train_nodes[node]=m['content']
    priority={'train':0,'validation':1,'test':2}
    for eid,original in before.items():
        current=retained[eid]
        if current['messages']!=original['messages'] or priority[current['split']]<priority[original['split']]:
            raise AssertionError('Frozen heldout text lost or demoted')
    verify(root/'staged')
    try:list(training_examples(root/'staged'))
    except ValueError as exc:refusal=str(exc)
    else:raise AssertionError('Unadmitted corpus accepted for training')
    result=dict(creator='Navneet Prabhakar',staging=staged,stage_seconds=stage_seconds,quality=quality,
        candidate_report_sha256=sha(candidates/'report.json'),assessment_sha256=sha(assessment),reserved_exact_prompt_hits=reserved_hits,
        staged_manifest_sha256=sha(root/'staged/manifest.json'),quality_manifest_sha256=sha(root/'quality/manifest.json'),
        parent_manifest_sha256=sha(parent/'manifest.json'),script_sha256=sha(__file__),
        frozen_heldout_rows_verified=len(before),new_candidate_rows_retained=new,new_candidate_splits=dict(splits),
        new_candidate_characters=dict(characters),distinct_train_candidate_nodes=len(train_nodes),
        distinct_train_candidate_node_characters=sum(map(len,train_nodes.values())),
        training_reader_refusal=refusal,training_eligible=False,new_neural_updates=0,new_teacher_calls=0,new_cloud_jobs=0,
        scope='Sample-only metadata candidates with exact/near grouping and non-admitting audit. No English/content/privacy quality certification, source approval or corpus admission. Exact development prompt checks do not establish semantic isolation.')
    (root/'preparation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    Path('reports/milestone-forty-four-dialogue-preparation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ('new_candidate_rows_retained','new_candidate_splits','frozen_heldout_rows_verified','training_reader_refusal')},indent=2),flush=True)


if __name__=='__main__':main()
