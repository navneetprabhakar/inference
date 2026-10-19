"""Foundation-only corpus decisions preserve exclusions and checked train scope."""
# Creator: Navneet Prabhakar
from dataclasses import asdict,replace
import json
import pytest
from slm.data.foundation_research import RULE,release,checked
from slm.data.review_stream import open_checked
from slm.data.schema import digest,make_example
from slm.data.quality_audit import signals
from slm.data.tokenized import sha
from test_staging import setup
from test_research_admission import dump,snapshot,seal


def fixture(tmp_path):
    source=replace(setup(tmp_path),source_id='databricks/databricks-dolly-15k',license_id='cc-by-sa-3.0')
    sources={source.source_id:asdict(source)};population=[]
    for i in range(8):
        messages=[dict(role='user',content=f'Describe the library room {i}.'),
                  dict(role='assistant',content='The library has books and a quiet reading room. Visitors can read there.')]
        if i==3:messages[1]['content']='Contact [EMAIL] for more information.'
        if i==6:messages[1]['content']='A claim about blood pressure needs separate review.'
        row=make_example(source,str(i),str(i),messages,split='test' if i==7 else 'train',
            official_split='test' if i==7 else 'train',validation_results=dict(split_group=digest(['group',1 if i==2 else i]),
                foundation_dialogue_candidate=dict(method='complete-dolly-instruction-foundation-candidate-v1',
                    training_eligible=False,parent_manifest_sha256='a'*64,parent_record_sha256='b'*64,
                    parent_split='test' if i==7 else 'train'))).to_dict()
        population.append(row)
    # A source-specific candidate marker cannot be substituted by another source's marker.
    population[5]['validation_results'].pop('foundation_dialogue_candidate')
    population[5]['validation_results']['dialogue_candidate']={'not_a_dolly_receipt':True}
    snapshot(tmp_path/'population',population,sources)
    p=tmp_path/'population'
    (p/'card.txt').write_bytes((tmp_path/'card').read_bytes());(p/'license.txt').write_bytes((tmp_path/'license').read_bytes())
    dump(p/'evidence.json',{source.source_id:dict(card='card.txt',license='license.txt')})
    m=json.loads((p/'manifest.json').read_text());m['files']={x.name:sha(x) for x in p.iterdir() if x.name!='manifest.json'};dump(p/'manifest.json',m)
    audit=tmp_path/'audit';audit.mkdir();sample=[];audits=[]
    for row in population:
        evidence=signals(row);evidence['language_windows']=[dict(message=i,start=0,end=len(message['content']),status='scored',
            top_scores=[dict(language='en',score=.99),dict(language='de',score=.001)]) for i,message in enumerate(row['messages'])]
        audits.append(dict(example_id=row['example_id'],record_sha256=digest(row),split_group=row['validation_results']['split_group'],signals=evidence))
        if row['split']=='train':sample.append(dict(record=row,record_sha256=digest(row)))
    for name,values in [('signals',audits),('sample',sample)]:
        (audit/(name+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in values))
    dump(audit/'manifest.json',dict(version=1,release='sample_only',parent_dataset_manifest_sha256=sha(p/'manifest.json'),files={x.name:sha(x) for x in audit.iterdir()}))
    decisions=[dict(example_id=r['example_id'],record_sha256=digest(r),split_group=r['validation_results']['split_group'],full_text_read=True,
        foundation_decision='exclude' if i==4 else 'consider',conversation_sft_certified=False,training_approved=False) for i,r in enumerate(population[:7])]
    dump(tmp_path/'review.json',dict(human_attestation=False,review_mode='delegated_expert',population_manifest_sha256=sha(p/'manifest.json'),
        audit_manifest_sha256=sha(audit/'manifest.json'),sample_sha256=sha(audit/'sample.jsonl'),decisions=decisions))
    r=population[1]
    dump(tmp_path/'legacy.json',dict(human_attestation=False,examples={r['example_id']:dict(record=r,record_sha256=digest(r),decision={'quality_verified':False})}))
    (tmp_path/'recent-sample.jsonl').write_text('')
    dump(tmp_path/'recent.json',dict(human_attestation=False,sample_sha256=sha(tmp_path/'recent-sample.jsonl'),decisions=[]))
    policy=dict(version=1,kind='two-source-foundation-research-v1',status='accepted_for_bounded_research',scope='local_foundation_pilot',
        authorized_by='Navneet Prabhakar',authorization_instruction='Synthetic fixture research only.',review_mode='delegated_expert',human_attestation=False,
        population_manifest_sha256=sha(p/'manifest.json'),audit_manifest_sha256=sha(audit/'manifest.json'),development_review_sha256=sha(tmp_path/'review.json'),
        legacy_review_sha256=sha(tmp_path/'legacy.json'),recent_review_sha256=sha(tmp_path/'recent.json'),recent_sample_sha256=sha(tmp_path/'recent-sample.jsonl'),
        eligibility_rule_sha256=digest(RULE),source_bindings={source.source_id:digest(asdict(source))},source_decisions={source.source_id:'Synthetic fixture evidence only.'},
        research_assumptions='Not factual or SFT certification.',risk_acceptance='No human attestation or production approval.',
        limits=dict(processed_positions=10485760,updates=12288,max_passes=2,max_parameters=100000000))
    dump(tmp_path/'policy.json',policy)
    report=release(p,audit,tmp_path/'review.json',tmp_path/'legacy.json',tmp_path/'recent.json',tmp_path/'recent-sample.jsonl',tmp_path/'policy.json',tmp_path/'release')
    return tmp_path/'release',report


def test_actual_admission_replays_prior_new_and_screen_exclusions_by_group(tmp_path):
    root,report=fixture(tmp_path)
    assert report['counts']['admitted_train']==1 and report['counts']['admitted_test']==1
    assert report['counts']['quarantined']==5
    with open_checked(root) as index:
        assert len(index)==1 and index.research_limits['max_passes']==2
        row=next(index.values());assert row['example_id'].endswith(':0')
        assert row['validation_results']['quality_review']=='research_language_only_not_factual_or_sft'
        assert row['validation_results']['research_admission']['human_attestation'] is False
        with pytest.raises(KeyError):index[row['source']+':7']


@pytest.mark.parametrize('defect',['text','missing','heldout','card','policy','review','signals'])
def test_resealed_release_cannot_bypass_checked_evidence(tmp_path,defect):
    root,_=fixture(tmp_path)
    if defect in ('text','missing','heldout'):
        p=root/'train-00000.jsonl';values=[json.loads(x) for x in p.read_text().splitlines()]
        if defect=='text':values[0]['messages'][1]['content']+=' Injected.'
        elif defect=='missing':values=[]
        else:values.append(json.loads((root/'test-00000.jsonl').read_text()))
        p.write_text(''.join(json.dumps(x)+'\n' for x in values))
    elif defect=='card':(root/'population-card.txt').write_text('Changed source evidence.')
    elif defect=='review':
        r=json.loads((root/'development-review.json').read_text());r['decisions'].pop();dump(root/'development-review.json',r)
    elif defect=='signals':(root/'audit-signals.jsonl').write_text('')
    else:
        p=json.loads((root/'research-policy.json').read_text());p['limits']['max_passes']=3;dump(root/'research-policy.json',p)
        m=json.loads((root/'manifest.json').read_text());m['research_policy_sha256']=digest(p);dump(root/'manifest.json',m)
    seal(root)
    with pytest.raises(ValueError):
        with open_checked(root):pass


@pytest.mark.parametrize('cap',['processed_positions','updates','max_passes','max_parameters'])
def test_caps_cannot_expand_and_human_attestation_cannot_be_claimed(tmp_path,cap):
    fixture(tmp_path);p=json.loads((tmp_path/'policy.json').read_text());p['limits'][cap]+=1
    with pytest.raises(ValueError):checked(p)
    p=json.loads((tmp_path/'policy.json').read_text());p['human_attestation']=True
    with pytest.raises(ValueError):checked(p)


@pytest.mark.parametrize('defect',['scope','positions','updates','sft','cuda'])
def test_foundation_release_cannot_escalate_training_scope(tmp_path,defect):
    from slm.common.tokenizer import train_release,BPE
    from slm.data.tokenized import build_shards
    from slm.common.config import Config
    from slm.common.training import Recipe
    from slm.train import Inputs,run
    root,_=fixture(tmp_path);tok=tmp_path/'tok';train_release(root,tok,512,min_frequency=1)
    tokens=tmp_path/'tokens';report=build_shards(root,tok,tokens,'sft' if defect=='sft' else 'foundation',context_length=32,max_positions=10000)
    spec=dict(version=1,scope='language_pilot',config=Config(vocab_size=BPE.load(tok).vocab_size,max_seq_len=64).to_dict(),
        recipe=asdict(Recipe()),seed=19,tokenizer=str(tok),releases={sha(root/'manifest.json'):str(root)},
        data=dict(kind='tokens',path=str(tokens),fingerprint=report['dataset_hash']),
        limits=dict(updates=1,processed_positions=10000),checkpoint=dict(every_updates=1,keep=2))
    if defect=='scope':spec['scope']='synthetic_mechanics'
    elif defect=='positions':spec['limits']['processed_positions']=10485761
    elif defect=='updates':spec['limits']['updates']=12289
    if defect=='cuda':
        with pytest.raises(ValueError,match='local MLX/CPU'):run(spec,tmp_path/'out',device='cuda')
    else:
        with pytest.raises(ValueError,match='[Rr]esearch'):Inputs(spec)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('defect',['card','review_coverage','window_gap'])
def test_rebound_nested_checksums_still_require_semantic_evidence(tmp_path,defect):
    root,_=fixture(tmp_path);policy=json.loads((root/'research-policy.json').read_text())
    review=json.loads((root/'development-review.json').read_text())
    if defect=='card':
        (root/'population-card.txt').write_text('Changed source card.')
        policy['population_manifest_sha256']=seal(root,'population-')
        audit=json.loads((root/'audit-manifest.json').read_text());audit['parent_dataset_manifest_sha256']=policy['population_manifest_sha256'];dump(root/'audit-manifest.json',audit)
        review['population_manifest_sha256']=policy['population_manifest_sha256']
    elif defect=='review_coverage':review['decisions'].pop()
    else:
        path=root/'audit-signals.jsonl';values=[json.loads(x) for x in path.read_text().splitlines()]
        values[0]['signals']['language_windows'][0]['start']=1
        path.write_text(''.join(json.dumps(x)+'\n' for x in values))
    policy['audit_manifest_sha256']=seal(root,'audit-');review['audit_manifest_sha256']=policy['audit_manifest_sha256']
    dump(root/'development-review.json',review);policy['development_review_sha256']=sha(root/'development-review.json')
    dump(root/'research-policy.json',policy)
    manifest=json.loads((root/'manifest.json').read_text());manifest['research_policy_sha256']=digest(policy);dump(root/'manifest.json',manifest);seal(root)
    with pytest.raises(ValueError):
        with open_checked(root):pass
