"""Synthetic evaluator controls; oracle replay is never student capability evidence."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from slm.data.schema import digest
from slm.data.holdout import check_training_context
from slm.eval.cases import candidate_suite
from slm.eval.conversation import (validate_suite,suite_review_packet,evaluate,score,output_review_packet,
    write_new,interval,check_results)
from slm.eval.stage import assess


def policy():return json.loads((Path(__file__).parents[1]/'configs/stage-screen-proposal-v1.json').read_text())


class OracleReplay:
    def __init__(self,suite):
        self.answers={digest(c['messages']):c['reference'] for c in suite['cases']};self.seen=[]
        self.identity={'architecture':{'vocab_size':512},'tokenizer_manifest_sha256':'a'*64,'model_manifest_sha256':'b'*64,
            'decoding':'raw-cached-greedy-v1','embedding_implementation':'native-gather-v1','inference_sha256':'c'*64,'scope':'TEST ORACLE REPLAY'}
    def generate(self,messages,max_new_tokens):
        self.seen.append(deepcopy(messages))
        return {'text':self.answers[digest(messages)],'token_ids':[10,3],'stop_reason':'message_end','prompt_tokens':20,
            'generated_tokens':2,'content_tokens':1,'ttft_seconds':.001,'seconds':.002,'max_new_tokens':max_new_tokens}
    def reference_loss(self,messages,reference):
        return {'nll_sum':.1,'content_targets':1,'utf8_bytes':len(reference.encode()),'scope':'TEST ORACLE REPLAY'}


def reviewed(suite,result):
    packet=suite_review_packet(suite);packet['human_attestation']=True
    for item in packet['cases'].values():item.update(approved=True,notes='Synthetic fixture approval; not a real review')
    outputs=output_review_packet(suite,result);outputs['human_attestation']=True
    for item in outputs['cases'].values():item.update(grades={k:True for k in item['grades']},notes='Synthetic fixture grades; not a real review')
    return packet,outputs


def test_candidate_counts_family_denominators_and_no_implicit_reviews():
    suite=candidate_suite();validate_suite(suite);assert suite==candidate_suite()
    model=OracleReplay(suite);results=evaluate(suite,model,16);report=score(suite,results)
    row=report['overall']
    assert (row['cases'],row['scenarios'],row['template_families'])==(500,100,10)
    assert (row['exact_cases'],row['exact_passes'],row['human_cases'],row['human_pending'])==(400,400,100,100)
    assert row['approved_cases']==0 and all(v is None for v in row['human_rubric_rates'].values())
    assert len(model.seen)==500 and model.seen[0]==suite['cases'][0]['messages']
    assert all(set(m)=={'role','content'} for msgs in model.seen for m in msgs)
    assert interval(0,0) is None and interval(0,100)[0]==0
    assert interval(100,100)[1]==1
    assert row['exact_case_wilson95_descriptive'][0]<1


def test_stage_proposal_missing_baseline_and_reviews_can_never_pass():
    suite=candidate_suite();result=evaluate(suite,OracleReplay(suite),16)
    r=assess(suite,result,policy())
    assert r['decision']=='insufficient_evidence' and r['production_accepted'] is False
    assert set(r['missing_evidence'])=={'stage_policy_not_accepted','suite_cases_not_all_human_approved','human_output_grades_pending','pre_stage_baseline_required'}
    sr,hr=reviewed(suite,result);p=policy();p['status']='accepted'
    positive=assess(suite,result,p,suite_review=sr,output_review=hr,baseline=result,baseline_review=hr)
    assert positive['decision']=='screen_passed' and positive['production_accepted'] is False


@pytest.mark.parametrize('defect',['wrong','extra_text','length','structural','generation_error','missing_row','duplicate_row','stale_case','invalid_stop'])
def test_free_generation_failures_are_retained_and_exact_answers_are_not_keyword_scores(defect):
    suite=candidate_suite();result=evaluate(suite,OracleReplay(suite),16);row=result['records'][0]
    if defect=='wrong':row['response']['text']='wrong'
    elif defect=='extra_text':row['response']['text']='The answer is '+row['response']['text']+'.'
    elif defect=='length':row['response'].update(stop_reason='length',token_ids=[10]*16,generated_tokens=16,content_tokens=16)
    elif defect=='structural':row['response'].update(stop_reason='invalid_structural',token_ids=[10,4])
    elif defect=='generation_error':row.update(response=None,generation_error={'type':'ValueError','message':'over context'})
    elif defect=='missing_row':result['records'].pop()
    elif defect=='duplicate_row':result['records'][1]=deepcopy(row)
    elif defect=='stale_case':row['case_hash']='0'*64
    else:row['response']['token_ids'][-1]=4
    if defect in ('missing_row','duplicate_row','stale_case','invalid_stop'):
        with pytest.raises(ValueError):score(suite,result)
    else:
        report=score(suite,result);assert report['overall']['exact_passes']==399
        assert report['overall']['cases']==500
        if defect=='generation_error':assert report['overall']['generation_errors']==1


def test_human_reviews_are_bound_to_exact_suite_and_outputs_and_require_attestation():
    suite=candidate_suite();result=evaluate(suite,OracleReplay(suite),16);sr,hr=reviewed(suite,result)
    assert score(suite,result,suite_review=sr,output_review=hr)['overall']['human_all_rubrics_passes']==100
    sr['human_attestation']=False
    with pytest.raises(ValueError,match='attestation'):score(suite,result,suite_review=sr)
    sr['human_attestation']=True;hr['human_attestation']=False
    with pytest.raises(ValueError,match='attestation'):score(suite,result,suite_review=sr,output_review=hr)
    hr['human_attestation']=True;result['records'][-1]['response']['text']='changed output'
    with pytest.raises(ValueError,match='Bound'):score(suite,result,output_review=hr)


def test_per_slice_failure_and_regression_can_reject_good_aggregate():
    suite=candidate_suite();before=evaluate(suite,OracleReplay(suite),16);after=deepcopy(before)
    for r in after['records'][:6]:r['response']['text']='wrong'
    sr,old=reviewed(suite,before);_,new=reviewed(suite,after);p=policy();p['status']='accepted'
    decision=assess(suite,after,p,suite_review=sr,output_review=new,baseline=before,baseline_review=old)
    assert decision['score']['overall']['exact_rate']>.95
    assert decision['decision']=='reject'
    assert 'exact_below_target:slices:reference' in decision['failed_checks']
    assert 'exact_regression:slices:reference' in decision['failed_checks']
    after=deepcopy(before)
    for r in after['records']:r['reference_loss']['nll_sum']*=1.2
    _,new=reviewed(suite,after)
    assert 'reference_nll_regression' in assess(suite,after,p,suite_review=sr,output_review=new,baseline=before,baseline_review=old)['failed_checks']


def test_missing_human_slice_and_incompatible_baseline_cannot_be_hidden():
    suite=candidate_suite();before=evaluate(suite,OracleReplay(suite),16);after=deepcopy(before)
    after['identity']['tokenizer_manifest_sha256']='0'*64
    with pytest.raises(ValueError,match='conventions'):assess(suite,after,policy(),baseline=before)
    p=policy();p['required_styles'].append('missing');p['required_slices'].append('missing')
    report=assess(suite,before,p)
    assert 'missing_styles:missing' in report['missing_evidence'] and 'missing_slices:missing' in report['missing_evidence']


def test_atomic_results_do_not_overwrite_and_cleanup(tmp_path,monkeypatch):
    write_new(tmp_path/'report.json',{'a':1})
    with pytest.raises(FileExistsError):write_new(tmp_path/'report.json',{'a':2})
    import slm.eval.conversation as module
    def fail(*args):raise OSError('synthetic publication failure')
    monkeypatch.setattr(module.os,'link',fail)
    with pytest.raises(OSError):write_new(tmp_path/'new.json',{'a':3})
    assert not (tmp_path/'new.json').exists() and not list(tmp_path.glob('.evaluation-*'))


def test_candidate_holdouts_are_rejected_by_training_and_teacher_even_if_relabeled_train():
    pytest.importorskip('jsonschema')
    context=candidate_suite()['cases'][0]['messages']
    with pytest.raises(ValueError,match='held-out'):check_training_context([*context,{'role':'assistant','content':'B0'}])
    with pytest.raises(ValueError,match='Reserved'):check_training_context([{'role':'user','content':'different'}],('fixture:eval-v1/reference',))
    from slm.teacher.scenarios import fixture_scenario
    from slm.teacher.workflow import check_scenario
    scenario=fixture_scenario('conversation');scenario['context']=context
    with pytest.raises(ValueError,match='held-out'):check_scenario(scenario)
    scenario=fixture_scenario('conversation');scenario['family_id']='eval-v1/reference'
    with pytest.raises(ValueError,match='Reserved'):check_scenario(scenario)


def test_generation_and_reference_errors_remain_in_the_denominator():
    suite=candidate_suite()
    class Failing(OracleReplay):
        def generate(self,*args):raise ValueError('No context room')
        def reference_loss(self,*args):raise ValueError('Reference too long')
    result=evaluate(suite,Failing(suite),16);report=score(suite,result)
    assert report['overall']['cases']==500 and report['overall']['generation_errors']==500
    assert report['overall']['exact_passes']==0 and report['reference_loss']['failed_cases']==500
    assert report['reference_loss']['mean_content_nll'] is None
    assert assess(suite,result,policy())['decision']=='reject'


def test_reviewed_release_and_reader_refuse_exact_eval_history(tmp_path,monkeypatch):
    pytest.importorskip('tokenizers')
    import slm.data.review as module
    from slm.data.tokenized import sha
    from test_review import fixture_snapshot,approved_packet
    fixture_snapshot(tmp_path/'raw')
    file=tmp_path/'raw/train-00000.jsonl';records=[json.loads(v) for v in file.read_text().splitlines()]
    records[0]['messages']=[*candidate_suite()['cases'][0]['messages'],{'role':'assistant','content':'B0'}]
    file.write_text(''.join(json.dumps(r)+'\n' for r in records))
    p=tmp_path/'raw/manifest.json';m=json.loads(p.read_text());m['files'][file.name]=sha(file);p.write_text(json.dumps(m))
    module.prepare(tmp_path/'raw',tmp_path/'review',30);approved_packet(tmp_path/'review')
    with pytest.raises(ValueError,match='held-out'):module.release(tmp_path/'raw',tmp_path/'review',tmp_path/'blocked')
    assert not (tmp_path/'blocked').exists()
    # Simulate a pre-guard reviewed artifact; the consumer must independently reject it.
    import slm.data.holdout as holdout
    with monkeypatch.context() as context:
        context.setattr(holdout,'check_training_context',lambda *args:None)
        module.release(tmp_path/'raw',tmp_path/'review',tmp_path/'historical')
    with pytest.raises(ValueError,match='held-out'):list(module.training_examples(tmp_path/'historical'))


def test_cli_candidate_creation_scoring_and_stage_reporting(tmp_path):
    import subprocess
    import sys
    subprocess.run([sys.executable,'-m','slm.eval.language','candidates','--output',str(tmp_path/'suite.json'),
        '--review',str(tmp_path/'review.json')],check=True,capture_output=True)
    suite=json.loads((tmp_path/'suite.json').read_text());result=evaluate(suite,OracleReplay(suite),16)
    write_new(tmp_path/'results.json',result)
    for command in ('score','stage','review-outputs'):
        args=[sys.executable,'-m','slm.eval.language',command,'--suite',str(tmp_path/'suite.json'),'--results',str(tmp_path/'results.json'),
            '--output',str(tmp_path/(command+'.json'))]
        if command=='stage':args.extend(['--policy',str(Path(__file__).parents[1]/'configs/stage-screen-proposal-v1.json')])
        subprocess.run(args,check=True,capture_output=True)
    assert json.loads((tmp_path/'stage.json').read_text())['decision']=='insufficient_evidence'
    assert json.loads((tmp_path/'review.json').read_text())['human_attestation'] is False


def test_invalid_global_generation_budget_fails_before_model_calls():
    suite=candidate_suite();model=OracleReplay(suite)
    for budget in (True,0,513):
        with pytest.raises(ValueError,match='budget'):evaluate(suite,model,budget)
    assert model.seen==[]
