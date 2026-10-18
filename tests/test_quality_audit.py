"""Signal preservation, whole-group sampling and offline detector failure boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest
from slm.data.quality_audit import audit,signals,top_scores,LIMITS
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.data.review import training_examples
from test_review import fixture_snapshot


def detector(tmp_path,mode='normal'):
    model=tmp_path/'model';model.write_text('Synthetic detector transport fixture; no language accuracy claim.')
    binary=tmp_path/'detector'
    code=f'''#!{sys.executable}
import sys,time
from pathlib import Path
mode={mode!r}
if mode=='fail':sys.exit(3)
if mode=='timeout':time.sleep(5)
lines=Path(sys.argv[3]).read_text().splitlines()
for i,line in enumerate(lines):
 if mode=='missing' and i==0:continue
 if mode=='none':print('');continue
 if mode=='single':print('__label__en 0.9');continue
 print('__label__en nan __label__fr 0.1' if mode=='nan' else '__label__en 0.9 __label__fr 0.1')
if mode=='extra':print('__label__en 0.9 __label__fr 0.1')
'''
    binary.write_text(code);binary.chmod(0o700)
    descriptor=tmp_path/'descriptor.json';descriptor.write_text(json.dumps(dict(version=1,kind='offline-fasttext-lid-v1',binary=str(binary),binary_sha256=sha(binary),model=str(model),model_sha256=sha(model))))
    return descriptor


def read(path):return [json.loads(line) for line in path.read_text().splitlines()]


def reseal(root):
    m=json.loads((root/'manifest.json').read_text());m['files']={p.name:sha(p) for p in root.iterdir() if p.name!='manifest.json'}
    (root/'manifest.json').write_text(json.dumps(m))


def run(tmp_path,mode='normal',**kw):
    data=tmp_path/'data';fixture_snapshot(data);desc=detector(tmp_path,mode)
    return audit(data,desc,tmp_path/'out',limits=LIMITS,seed='fixture-audit-v1',**kw)


def test_signals_preserve_slang_quantities_and_only_report_candidate_offsets(tmp_path):
    rows=fixture_snapshot(tmp_path/'data');row=rows[0].to_dict()
    text="yo don't spend over $100, need 2. email test@example.org; phone: +91 98765 43210; account number: 1234; 192.0.2.1"
    row['messages'][0]['content']=text;before=deepcopy(row);result=signals(row)
    assert row==before and row['messages'][0]['content']==text
    assert {'email','contextual_phone','identity_or_address_context','ipv4_literal_candidate'}<=set(result['privacy_findings'])
    assert 'test@example.org' not in json.dumps(result) and '98765' not in json.dumps(result)
    assert result['privacy_assessment']==result['quality_assessment']=='unverified'
    assert result['structural_or_cleaner_attention'] is None


def test_full_window_coverage_and_no_training_approval(tmp_path):
    r=run(tmp_path,groups_per_stratum=100,window_characters=32)
    rows=read(tmp_path/'out/sample.jsonl');assert len(rows)==r['records']==30
    assert r['human_approvals']==0 and r['training_eligible'] is False
    for row in rows:
        assert row['approved'] is None and all(v is None for v in row['judgments'].values())
        for i,message in enumerate(row['record']['messages']):
            windows=[w for w in row['signals']['language_windows'] if w['message']==i]
            assert windows[0]['start']==0 and windows[-1]['end']==len(message['content'])
            assert sum(w['end']-w['start'] for w in windows)==len(message['content'])
    with pytest.raises(ValueError,match='sample-only'):list(training_examples(tmp_path/'out'))


def test_group_sampling_probabilities_and_order_independence(tmp_path):
    data=tmp_path/'data';original=fixture_snapshot(data);desc=detector(tmp_path)
    a=audit(data,desc,tmp_path/'a',limits=LIMITS,seed='fixed',groups_per_stratum=1)
    selected=read(tmp_path/'a/sample.jsonl');by_group={}
    for row in selected:
        gid=row['record']['validation_results']['split_group'];by_group.setdefault(gid,set()).add(row['record']['example_id'])
        s=row['selection'];assert s['inclusion_probability']==s['sampled_groups']/s['population_groups']
    for gid,ids in by_group.items():assert ids=={e.example_id for e in original if e.validation_results['split_group']==gid}
    for path in data.glob('*.jsonl'):path.write_text('\n'.join(reversed(path.read_text().splitlines()))+'\n')
    reseal(data);audit(data,desc,tmp_path/'b',limits=LIMITS,seed='fixed',groups_per_stratum=1)
    assert (tmp_path/'a/sample.jsonl').read_bytes()==(tmp_path/'b/sample.jsonl').read_bytes()
    assert a['sampled_groups']==sum(s['sampled_groups'] for s in a['strata'])


@pytest.mark.parametrize('mode',['fail','timeout','missing','extra','nan'])
def test_detector_failure_never_publishes_partial_audit(tmp_path,mode):
    data=tmp_path/'data';fixture_snapshot(data);desc=detector(tmp_path,mode)
    with pytest.raises(ValueError):audit(data,desc,tmp_path/'out',limits={**LIMITS,'detector_seconds':1},seed='fixed')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.quality-audit-*'))


@pytest.mark.parametrize('field,value',[('max_records',1),('max_record_bytes',20),('max_input_bytes',100),('max_windows',1),('max_sample_records',1),('max_strata',1),('max_detector_output_bytes',1)])
def test_limits_abort_without_partial_sample(tmp_path,field,value):
    data=tmp_path/'data';fixture_snapshot(data);desc=detector(tmp_path)
    with pytest.raises(ValueError):audit(data,desc,tmp_path/'out',limits={**LIMITS,field:value},seed='fixed',groups_per_stratum=100)
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.quality-audit-*'))


def test_artifact_pin_and_input_mutation_refused(tmp_path,monkeypatch):
    import slm.data.quality_audit as module
    data=tmp_path/'data';fixture_snapshot(data);desc=detector(tmp_path)
    model=tmp_path/'model';model.write_text('changed')
    with pytest.raises(ValueError,match='checksum'):audit(data,desc,tmp_path/'out',limits=LIMITS,seed='fixed')
    raw=json.loads(desc.read_text());raw['model_sha256']=sha(model);desc.write_text(json.dumps(raw));original=module.predict
    def mutate(*args):
        original(*args)
        with next(data.glob('*.jsonl')).open('a') as f:f.write('\n')
    monkeypatch.setattr(module,'predict',mutate)
    with pytest.raises(ValueError,match='changed'):audit(data,desc,tmp_path/'out',limits=LIMITS,seed='fixed')
    assert not (tmp_path/'out').exists()


def test_cross_partition_group_is_not_sampled(tmp_path):
    data=tmp_path/'data';fixture_snapshot(data);desc=detector(tmp_path)
    test_path=next(data.glob('test-*.jsonl'));test_rows=read(test_path)
    train_path=next(data.glob('train-*.jsonl'));train_rows=read(train_path)
    train_rows[0]['validation_results']['split_group']=test_rows[0]['validation_results']['split_group']
    train_path.write_text(''.join(json.dumps(row)+'\n' for row in train_rows));reseal(data)
    with pytest.raises(ValueError,match='cross partitions'):audit(data,desc,tmp_path/'out',limits=LIMITS,seed='fixed')


def test_score_parser_preserves_small_upstream_roundoff_and_rejects_bad_values():
    assert top_scores('__label__en 1.00001 __label__fr 0.0')[0]['score']==1.00001
    for line in ('__label__en inf __label__fr 0','__label__en 1.2 __label__fr 0','__label__en 0.2 __label__en 0.1','__label__en 0.2 __label__fr 0.9'):
        with pytest.raises(ValueError):top_scores(line)


def test_database_budget_cleans_up_incomplete_work(tmp_path):
    import sqlite3
    data=tmp_path/'data';fixture_snapshot(data,kind='prose',repeat_words=7000);desc=detector(tmp_path)
    with pytest.raises(sqlite3.DatabaseError):audit(data,desc,tmp_path/'out',limits={**LIMITS,'max_db_bytes':1024*1024},seed='fixed')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.quality-audit-*'))


def test_non_alphabetic_windows_are_explicitly_unscored(tmp_path):
    data=tmp_path/'data';fixture_snapshot(data);desc=detector(tmp_path)
    path=next(data.glob('train-*.jsonl'));rows=read(path);rows[0]['messages'][0]['content']='123 + 456 🦄'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows));reseal(data)
    audit(data,desc,tmp_path/'out',limits=LIMITS,seed='fixed')
    result=next(r for r in read(tmp_path/'out/signals.jsonl') if r['example_id']==rows[0]['example_id'])
    assert 'unscored_window' in result['signals']['attention']
    assert result['signals']['language_windows'][0]['top_scores'] is None


def test_official_cli_may_return_fewer_than_requested_labels():
    assert top_scores('__label__en 0.9')==[dict(language='en',score=.9)]
    assert top_scores('')==[]


@pytest.mark.parametrize('mode',['single','none'])
def test_incomplete_predictions_stay_unverified_and_receive_attention(tmp_path,mode):
    run(tmp_path,mode)
    results=read(tmp_path/'out/signals.jsonl')
    assert results and all('incomplete_top_k' in row['signals']['attention'] for row in results)
    assert all(row['signals']['language_assessment']=='unverified' and not row['training_eligible'] for row in results)
    if mode=='none':assert all('unscored_window' in row['signals']['attention'] for row in results)
