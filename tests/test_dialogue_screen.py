"""Proposed screening cannot admit rows or split a quarantined family."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from dataclasses import asdict
import json
import pytest
from slm.data import dialogue_screen as module
from slm.data.dialogue_candidates import extract
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.data.review import training_examples
from test_dialogue_candidates import fixture,projection


def record():
    tree,source=fixture();r=extract(tree,source,projection(tree),'d'*64)[0][0]
    r['split']='train';r['validation_results']['split_group']='e'*64
    return r


def audit(r):
    stats=module.signals(r);stats['attention']=[]
    stats['language_windows']=[dict(message=i,start=0,end=len(m['content']),status='scored',
        top_scores=[dict(language='en',score=.95),dict(language='fr',score=.04)]) for i,m in enumerate(r['messages'])]
    return dict(example_id=r['example_id'],record_sha256=digest(r),split_group=r['validation_results']['split_group'],signals=stats)


def test_unchanged_nonattended_candidate_has_no_screen_reasons():
    r=record();assert module.reasons(r,audit(r),.8)==set()


@pytest.mark.parametrize('text,reason',[
    ('Describe medical dosage.','bounded_scope_attention'),
    ('Hello Prompter!','source_identity_or_role_artifact'),
    ('Fill in [TARGETLANGUAGE].','unfilled_template_attention'),
    ('```python\nprint(1)\n```','unverified_code_attention')])
def test_declared_attention_is_not_mislabeled_as_a_truth_or_mature_content_classifier(text,reason):
    r=record();r['messages'][1]['content']=text
    r['validation_results']['dialogue_candidate']['raw_nodes'][1]['text_sha256']=digest(text)
    assert reason in module.reasons(r,audit(r),.8)
    assert r['content_category']=='unreviewed'


def test_changed_raw_text_is_quarantined_without_repair():
    r=record();r['messages'][1]['content']='New text.'
    assert 'text_transformed_after_raw_extraction' in module.reasons(r,audit(r),.8)


@pytest.mark.parametrize('defect',['hash','signal','gap','missing_window','node_identity'])
def test_forged_or_incomplete_evidence_fails(defect):
    r=record();a=audit(r)
    if defect=='hash':a['record_sha256']='0'*64
    elif defect=='signal':a['signals']['characters']+=1
    elif defect=='gap':a['signals']['language_windows'][0]['start']=1
    elif defect=='missing_window':a['signals']['language_windows'].pop()
    else:
        r['validation_results']['dialogue_candidate']['raw_nodes'][0]['message_id']='wrong';a=audit(r)
    with pytest.raises(ValueError):module.reasons(r,a,.8)


def test_short_unscored_or_low_scoring_windows_remain_explicit_attention():
    r=record();a=audit(r);a['signals']['language_windows'][0]['top_scores'][0]['score']=.2
    assert 'language_score_attention' in module.reasons(r,a,.8)
    a=audit(r);a['signals']['language_windows'][0].update(status='no_alphabetic_content',top_scores=None)
    assert 'language_unscored_or_incomplete' in module.reasons(r,a,.8)


def snapshot(tmp_path):
    dataset=tmp_path/'dataset';dataset.mkdir();quality=tmp_path/'quality';quality.mkdir()
    rows=[record() for _ in range(3)]
    for i,r in enumerate(rows):
        key='answer'+str(i);r['example_id']='OpenAssistant/oasst2:'+key;r['lineage'][1]=key
        r['validation_results']['dialogue_candidate']['raw_nodes'][1]['message_id']=key
    rows[2]['validation_results']['split_group']='f'*64
    rows[1]['messages'][1]['content']='Discuss dosage.'
    rows[1]['validation_results']['dialogue_candidate']['raw_nodes'][1]['text_sha256']=digest('Discuss dosage.')
    (dataset/'train-00000.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    source=fixture()[1];(dataset/'sources.json').write_text(json.dumps({source.source_id:asdict(source)}))
    def manifest(root,extra=None):
        value=dict(version=1,release='sample_only',files={p.name:sha(p) for p in root.iterdir()})
        value.update(extra or {});(root/'manifest.json').write_text(json.dumps(value))
    manifest(dataset)
    (quality/'signals.jsonl').write_text(''.join(json.dumps(audit(r))+'\n' for r in rows))
    manifest(quality,dict(parent_dataset_manifest_sha256=sha(dataset/'manifest.json')))
    review=tmp_path/'review.json';review.write_text(json.dumps(dict(audit_manifest_sha256=sha(quality/'manifest.json'),
        human_attestation=False,training_eligible=False,decisions=[])))
    policy=tmp_path/'policy.json';policy.write_text(json.dumps(dict(version=1,kind='oasst-research-screen-v1',status='proposed_not_admitted',
        source='OpenAssistant/oasst2',population_manifest_sha256=sha(dataset/'manifest.json'),audit_manifest_sha256=sha(quality/'manifest.json'),
        review_sha256=sha(review),minimum_english_top_score=.8,screen_only=True,scope='Fixture',limitations='Not real data or admission')))
    return dataset,quality,review,policy


def test_whole_group_quarantine_keeps_partitions_labels_and_training_refusal(tmp_path):
    args=snapshot(tmp_path);out=tmp_path/'out';result=module.screen(*args,out)
    assert result['counts']=={'quarantined_train':2,'remaining_train':1}
    kept=json.loads((out/'candidates.jsonl').read_text());assert kept['split']=='train' and kept['content_category']=='unreviewed'
    assert (out/'train-00000.jsonl').read_bytes()==(out/'candidates.jsonl').read_bytes()
    assert result['release']=='sample_only' and result['training_eligible'] is False
    with pytest.raises(ValueError,match='Reviewed training release required'):list(training_examples(out))
    with pytest.raises(FileExistsError):module.screen(*args,out)


def test_changed_population_is_refused_without_publishing(tmp_path):
    args=snapshot(tmp_path);(args[0]/'train-00000.jsonl').write_text('{}\n')
    with pytest.raises(ValueError):module.screen(*args,tmp_path/'out')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.dialogue-screen-*'))


def test_policy_cannot_claim_admission(tmp_path):
    args=snapshot(tmp_path);p=json.loads(args[3].read_text());p['status']='accepted_for_training';args[3].write_text(json.dumps(p))
    with pytest.raises(ValueError):module.screen(*args,tmp_path/'out')
