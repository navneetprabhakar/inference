"""Research admission is distinct from human review and cannot bypass run caps."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from dataclasses import asdict,replace
import json
from pathlib import Path
import pytest
from slm.data.schema import make_example,digest
from slm.data.context import derive,SOURCE
from slm.data.quality_audit import signals
from slm.data.research_admission import release,open_research,admitted
from slm.data.review import training_examples
from slm.data.review_stream import open_checked
from slm.data.tokenized import sha,build_shards
from slm.common.tokenizer import train_release,BPE
from slm.common.config import Config
from slm.common.training import Recipe
from slm.train import Inputs,run
from test_staging import setup


def dump(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')


def seal(root,prefix=''):
    path=root/(prefix+'manifest.json');m=json.loads(path.read_text())
    m['files']={name:sha(root/(prefix+name)) for name in m['files']};dump(path,m)
    return sha(path)


def snapshot(path,rows,sources,extra=None):
    path.mkdir();dump(path/'sources.json',sources)
    for split in ('train','validation','test'):
        (path/(split+'-00000.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows if r['split']==split))
    m={'version':1,'release':'sample_only','files':{p.name:sha(p) for p in path.iterdir()}}
    if extra:m.update(extra)
    dump(path/'manifest.json',m)


def fixture(tmp_path,limits_override=None):
    src=replace(setup(tmp_path),source_id=SOURCE,license_id='cc-by-sa-3.0');sources={SOURCE:asdict(src)}
    origin=[]
    for i,split in enumerate(['train','train','train','test']):
        text=(f'This is the history of the archive number {i}. The building has a collection of books and records. '
              'Visitors can read the documents in a room with a guide from the local library. '
              'These pages describe the town and its bridges. ')*3
        text=text.strip().removesuffix('.') if i==1 else text.strip()
        row=make_example(src,str(i),str(i),[dict(role='user',content='Describe it.\n\nContext:\n'+text),
            dict(role='assistant',content='Deliberately unreliable fixture answer, never train on this.')],
            split=split,official_split=split,validation_results={'split_group':digest(['group',i if i not in (1,2) else 1])}).to_dict()
        origin.append(row)
    snapshot(tmp_path/'origin',origin,sources)
    extraction=json.loads(Path('configs/context-prose-candidate-v1.json').read_text())
    extraction['parent_manifest_sha256']=sha(tmp_path/'origin/manifest.json');dump(tmp_path/'extraction.json',extraction)
    population=[]
    for parent in origin:
        row,reason=derive(parent,extraction);assert reason is None
        row['validation_results']['split_group']=parent['validation_results']['split_group'];population.append(row)
    population.append(origin[-1])  # Original frozen reference, not admitted.
    snapshot(tmp_path/'population',population,sources)
    audit=tmp_path/'audit';audit.mkdir();dump(audit/'sources.json',sources)
    with (audit/'signals.jsonl').open('w') as f:
        for r in population:
            s=signals(r);text=r['messages'][0]['content']
            s.update(attention=[],language_windows=[dict(message=0,start=start,end=min(len(text),start+2048),status='scored',
                top_scores=[dict(language='en',score=.99),dict(language='de',score=.001)]) for start in range(0,len(text),2048)])
            f.write(json.dumps(dict(example_id=r['example_id'],record_sha256=digest(r),split_group=r['validation_results']['split_group'],signals=s))+'\n')
    dump(audit/'manifest.json',dict(version=1,release='sample_only',parent_dataset_manifest_sha256=sha(tmp_path/'population/manifest.json'),
        files={p.name:sha(p) for p in audit.iterdir()}))
    review=dict(human_attestation=False,review_mode='delegated_expert',quality_manifest_sha256=sha(audit/'manifest.json'),
                purpose='Synthetic fixture evidence only; no actual public source approval.')
    dump(tmp_path/'review.json',review)
    p=json.loads(Path('configs/context-research-admission-v1.json').read_text())
    p.update(origin_manifest_sha256=sha(tmp_path/'origin/manifest.json'),population_manifest_sha256=sha(tmp_path/'population/manifest.json'),
        audit_manifest_sha256=sha(audit/'manifest.json'),extraction_file_sha256=sha(tmp_path/'extraction.json'),
        development_review_file_sha256=sha(tmp_path/'review.json'),source_evidence_decision='Synthetic fixture, not actual source clearance.')
    if limits_override:p['limits'].update(limits_override)
    dump(tmp_path/'policy.json',p)
    report=release(tmp_path/'origin',tmp_path/'population',audit,tmp_path/'extraction.json',tmp_path/'review.json',tmp_path/'policy.json',tmp_path/'release')
    return tmp_path/'release',report


def test_checked_research_release_quarantines_whole_group_and_never_yields_holdout(tmp_path):
    root,report=fixture(tmp_path)
    assert report['counts']['admitted_train']==1 and report['counts']['admitted_test']==1
    assert report['counts']['group_quarantined']==2
    rows=list(training_examples(root));assert len(rows)==1
    r=rows[0];assert r['messages'][0]['role']=='text' and 'unreliable fixture answer' not in r['messages'][0]['content']
    assert r['validation_results']['research_admission']['human_attestation'] is False
    assert 'human_review' not in r['validation_results'] and r['validation_results']['language_review']=='research_policy_assumed_en'
    with open_checked(root) as index:
        assert index.research_limits['processed_positions']==1048576
        with pytest.raises(KeyError):index[SOURCE+':3:context-prose-v1']


@pytest.mark.parametrize('defect',['text','missing','heldout','blocked','human','cap'])
def test_resealed_research_release_cannot_change_admission_or_escalate_scope(tmp_path,defect):
    root,_=fixture(tmp_path);path=root/'train-00000.jsonl';rows=[json.loads(l) for l in path.open()]
    if defect=='text':rows[0]['messages'][0]['content']+=' Injected unapproved content.'
    elif defect=='missing':rows=[]
    elif defect=='heldout':rows.append(json.loads((root/'test-00000.jsonl').read_text()))
    elif defect=='blocked':
        p=json.loads((root/'research-policy.json').read_text())
        r=next(json.loads(l) for l in (root/'population-train-00000.jsonl').open() if json.loads(l)['example_id'].endswith(':2:context-prose-v1'))
        rows.append(admitted(r,p))
    else:
        p=json.loads((root/'research-policy.json').read_text())
        if defect=='human':p['human_attestation']=True
        else:p['limits']['processed_positions']=1048577
        dump(root/'research-policy.json',p);m=json.loads((root/'manifest.json').read_text());m['research_policy_sha256']=digest(p);dump(root/'manifest.json',m)
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows));seal(root)
    with pytest.raises(ValueError):next(training_examples(root))


@pytest.mark.parametrize('defect',['missing_signal','window_gap'])
def test_even_rebound_audit_requires_complete_semantic_coverage(tmp_path,defect):
    root,_=fixture(tmp_path);path=root/'audit-signals.jsonl';rows=[json.loads(l) for l in path.open()]
    if defect=='missing_signal':rows.pop()
    else:rows[0]['signals']['language_windows'][0]['start']=1
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows));h=seal(root,'audit-')
    review=json.loads((root/'development-review.json').read_text());review['quality_manifest_sha256']=h;dump(root/'development-review.json',review)
    p=json.loads((root/'research-policy.json').read_text());p['audit_manifest_sha256']=h;p['development_review_file_sha256']=sha(root/'development-review.json');dump(root/'research-policy.json',p)
    m=json.loads((root/'manifest.json').read_text());m['research_policy_sha256']=digest(p);dump(root/'manifest.json',m);seal(root)
    with pytest.raises(ValueError):next(training_examples(root))


def pilot(tmp_path,limits_override=None):
    root,_=fixture(tmp_path,limits_override);tok=tmp_path/'tok';train_release(root,tok,512,min_frequency=1)
    report=build_shards(root,tok,tmp_path/'tokens','foundation',context_length=32,max_positions=10000)
    return dict(version=1,scope='language_pilot',config=Config(vocab_size=BPE.load(tok).vocab_size,max_seq_len=64).to_dict(),
        recipe=asdict(Recipe()),seed=19,tokenizer=str(tok),releases={sha(root/'manifest.json'):str(root)},
        data=dict(kind='tokens',path=str(tmp_path/'tokens'),fingerprint=report['dataset_hash']),
        limits=dict(updates=1,processed_positions=10000),checkpoint=dict(every_updates=1,keep=2))


@pytest.mark.parametrize('defect',['positions','updates','scope','cuda'])
def test_research_training_limits_are_enforced_before_any_student_update(tmp_path,defect):
    s=pilot(tmp_path)
    if defect=='positions':s['limits']['processed_positions']=1048577
    elif defect=='updates':s['limits']['updates']=2049
    elif defect=='scope':s['scope']='synthetic_mechanics'
    if defect=='cuda':
        with pytest.raises(ValueError,match='local MLX/CPU'):run(s,tmp_path/'out',device='cuda')
    else:
        with pytest.raises(ValueError,match='research'):Inputs(s)
    assert not (tmp_path/'out').exists()


def test_admitted_research_fixture_can_run_real_tiny_update_and_resume(tmp_path):
    s=pilot(tmp_path);s['limits']['updates']=2
    first=run(s,tmp_path/'first',max_new_updates=1)
    second=run(s,tmp_path/'second',resume=first['latest_checkpoint'])
    assert first['final']['step']==1 and second['final']['step']==2
    assert not second['production_accepted']


@pytest.mark.parametrize('cap',['parameters','passes'])
def test_narrower_research_caps_cannot_be_bypassed_by_valid_data(tmp_path,cap):
    s=pilot(tmp_path,{'max_parameters':1} if cap=='parameters' else {'max_passes':1})
    if cap=='passes':
        from slm.data.mixture import build_mixture
        mixed=build_mixture([dict(id='context',path=s['data']['path'],dataset_hash=s['data']['fingerprint'],weight=1,max_passes=2,max_positions=10000)],
            s['tokenizer'],tmp_path/'mixed',objective='foundation',budget=10000,minimum=1,group_cap=10000)
        s['data']=dict(kind='mixture',path=str(tmp_path/'mixed'),fingerprint=mixed['dataset_hash'],bindings={'context':str(tmp_path/'tokens')})
    with pytest.raises(ValueError,match='[Rr]esearch'):Inputs(s)
