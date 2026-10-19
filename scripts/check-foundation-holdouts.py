#!/usr/bin/env python3
"""Check exact development prompts and complete reference contexts in train."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    root=Path('data/iteration-two-foundation-candidates-v1/staged')
    parent=Path('data/iteration-two-dialogue-preparation-v1/staged')
    assessment=Path('reports/milestone-forty-three-conversation.json')
    for p in (root,parent):verify(p)
    reserved={' '.join(r['user'].casefold().split()) for r in json.loads(assessment.read_text())['turns']}
    heldout_ids=set();heldout_groups=set();contexts=set()
    for split in ('validation','test'):
        for p in parent.glob(split+'-*.jsonl'):
            for line in p.open():
                r=json.loads(line);heldout_ids.add(r['example_id']);heldout_groups.add(r['parent_group_id'])
                if r['validation_results'].get('context_derivation'):
                    contexts.add(r['messages'][0]['content'])
    conflicts=[];seen=0
    for p in root.glob('train-*.jsonl'):
        for line in p.open():
            r=json.loads(line);seen+=1;reasons=[]
            if r['example_id'] in heldout_ids or r['parent_group_id'] in heldout_groups:reasons.append('frozen_identity_or_parent')
            for m in r['messages']:
                text=m['content']
                if m['role']=='user' and ' '.join(text.casefold().split()) in reserved:reasons.append('exact_development_prompt')
                if text in contexts:reasons.append('exact_complete_reference_message')
                if text.count('\n\nContext:\n')==1 and text.split('\n\nContext:\n',1)[1] in contexts:reasons.append('exact_complete_dolly_reference_context')
            text='\n'.join(m['content'] for m in r['messages'])
            if 'mira' in text.casefold() and 'tara' in text.casefold() and ('apple' in text.casefold() or 'meeting' in text.casefold()):
                reasons.append('development_name_pair_attention')
            if reasons:conflicts.append(dict(example_id=r['example_id'],record_sha256=digest(r),reasons=sorted(set(reasons))))
    report=dict(creator='Navneet Prabhakar',dataset_manifest_sha256=sha(root/'manifest.json'),frozen_parent_manifest_sha256=sha(parent/'manifest.json'),
        assessment_sha256=sha(assessment),script_sha256=sha(__file__),checked_train_rows=seen,frozen_ids=len(heldout_ids),
        frozen_parent_groups=len(heldout_groups),frozen_complete_contexts=len(contexts),conflicts=conflicts,passed=not conflicts,
        training_eligible=False,
        scope='Exact ID/parent, normalized complete development prompt and complete reference-message/Context-slice checks only. A name-pair cue is manual attention, not a semantic classifier. No arbitrary substring, paraphrase or global scenario-family contamination guarantee; no admission.')
    output=Path('reports/milestone-forty-six-holdout-check.json')
    with output.open('x') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
