"""Package completed source evidence without replaying an unavailable supplement."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sqlite3
from slm.data.schema import Source
from slm.data.tokenized import sha

OLD=Path('data/tinystories-source-preparation-v1')
ROOT=Path('data/tinystories-source-ready-v1')


def main():
    if ROOT.exists():raise FileExistsError('Source evidence already packaged')
    plan=json.loads((OLD/'plan.json').read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Original source-preparation input changed')
    failure=json.loads((OLD/'failure.json').read_text());attempts={r['key']:r for r in failure['ledger']['attempts']}
    required=['dataset-info.json','card.txt','inventory.json','license.txt']
    for name in required:
        if attempts[name]['state']!='complete' or sha(OLD/name)!=attempts[name]['body_sha256']:
            raise ValueError('Required completed metadata evidence differs')
    if attempts['official-license.html']['state']!='pending':raise ValueError('Retained supplement state differs')
    info=json.loads((OLD/'dataset-info.json').read_text());revision=info['sha'];card=(OLD/'card.txt').read_text()
    if 'license: cdla-sharing-1.0' not in card or not (OLD/'license.txt').read_text().startswith('Community Data License Agreement'):
        raise ValueError('Published source/license evidence differs')
    ROOT.mkdir()
    for name in required:shutil.copyfile(OLD/name,ROOT/name)
    source=Source('roneneldan/TinyStories',revision,'https://huggingface.co/datasets/roneneldan/TinyStories',
        'cdla-sharing-1.0',sha(ROOT/'license.txt'),sha(ROOT/'card.txt'),
        ('Synthetic GPT-3.5/GPT-4 stories, as declared by pinned source card',),'sample_only')
    record=asdict(source);record['evidence_files']=dict(card='card.txt',license='license.txt',license_url='https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/CDLA-Sharing-1.0.txt')
    (ROOT/'source.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    inventory=json.loads((ROOT/'inventory.json').read_text());files={r['path']:r for r in inventory if r['type']=='file'}
    expected=['TinyStoriesV2-GPT4-train.txt','TinyStoriesV2-GPT4-valid.txt','TinyStories-valid.txt','Evaluation prompts.yaml']
    if not set(expected)<=set(files):raise ValueError('Narrative source/holdout file identities missing')
    report=dict(creator='Navneet Prabhakar',kind='actual-tinystories-source-evidence-finalization-v1',complete=True,
        revision=revision,source_sha256=sha(ROOT/'source.json'),card_sha256=sha(ROOT/'card.txt'),
        license_sha256=sha(ROOT/'license.txt'),inventory_sha256=sha(ROOT/'inventory.json'),
        parent_preparation_plan_sha256=sha(OLD/'plan.json'),parent_failure_sha256=sha(OLD/'failure.json'),
        finalizer_sha256=sha(__file__),required_artifacts_verified=required,
        target_and_holdout_metadata={k:files[k] for k in expected},
        supplementary_official_license=dict(status='transfer_check_failed_not_retained_or_retried',declared_url='https://cdla.dev/sharing-1-0/',substitute_claimed=False),
        parent_reserved=failure['ledger']['reserved'],parent_completed_requests=4,parent_pending_requests=1,
        new_network_requests=0,new_data_rows=0,training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
        next_requirements=['Fetch and protect both original and GPT4 official validation texts plus published evaluation prompts before any narrative training admission','Bound sparse original train ranges; preserve byte identities and complete story delimiters without text repair','Review actual narrative rows, language/privacy/exclusion signals, exact/near family grouping and finite source/corpus admission'],
        scope='Completed pinned card/inventory/SPDXlicense evidence recovered without repeating unavailable official HTML supplement. Sample-only source, no story data, trained weights, dataset admission or legal certification of downstream distribution.')
    raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode();(ROOT/'report.json').write_bytes(raw)
    Path('reports/tinystories-source-preparation.json').write_bytes(raw)
    print(json.dumps(dict(revision=revision,source_status='sample_only',new_requests=0,target_bytes=files[expected[0]]['size'],official_validation_bytes=files[expected[1]]['size']+files[expected[2]]['size']),indent=2))


if __name__=='__main__':main()
