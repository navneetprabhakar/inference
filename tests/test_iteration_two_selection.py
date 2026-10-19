"""Optimizer selection preserves cached score/state identities and physical limits."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import pytest
from slm.eval.iteration_two import SOURCES,summarize
from slm.eval import iteration_two_results
from slm.eval.iteration_two_selection import select_from_results
from slm.data.tokenized import sha
from slm.data.schema import digest


def write(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')


def fixture(root):
    root.mkdir();groups=[dict(source=s) for s in SOURCES for _ in range(32)];score_files={};specs={}
    for trial in ('lr-0003','lr-0010'):
        p=root/(trial+'.json');write(p,{});specs[trial]=dict(spec_file_sha256=sha(p))
    protocol=dict(groups=groups,groups_sha256=digest(groups),source_sha256={},specs=specs,plan_hashes={t:t for t in specs},
        exposure=dict(planned_selected_chain_positions=10223491,cumulative_physical_position_ceiling=10485760),optimizer_choice='Frozen selection fixture.')
    write(root/'protocol.json',protocol);write(root/'freeze.json',dict(protocol_sha256=sha(root/'protocol.json')))
    for trial in specs:
        run=root/'runs'/trial;cp=run/'checkpoints/cp';(cp/'state/model').mkdir(parents=True)
        for name in ('model/config.json','model/model.safetensors','model/manifest.json','optimizer.safetensors','state.json'):
            (cp/'state'/name).write_text('Synthetic byte-identity fixture; not a model checkpoint.')
        write(cp/'state/manifest.json',{n:sha(cp/'state'/n) for n in ('model/config.json','model/model.safetensors','model/manifest.json','optimizer.safetensors','state.json')})
        write(cp/'binding.json',{});write(cp/'manifest.json',{n:sha(cp/n) for n in ('binding.json','state/manifest.json')})
        (run/'events.jsonl').write_text('Synthetic event binding fixture.\n')
        expected=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144)
        report=dict(final=expected,status='invocation_update_limit',initial=dict(step=0,cursor=0,tokens=0,supervised_tokens=0),
            latest_checkpoint=str(cp.resolve()),latest_manifest_sha256=sha(cp/'manifest.json'),plan_hash=trial,events_sha256=sha(run/'events.jsonl'))
        write(run/'report.json',report);write(run/'run.json',dict(plan_hash=trial,resume_manifest_sha256=None))
        score=dict(trial=trial,protocol_sha256=sha(root/'protocol.json'),plan_hash=trial,training_final=expected,
            scorer_sha256=sha(iteration_two_results.__file__),run_report_sha256=sha(run/'report.json'),checkpoint_manifest_sha256=sha(cp/'manifest.json'),
            metrics=summarize(groups,[6.8 if trial=='lr-0003' else 6.7]*64,[6.9]*64))
        p=root/(trial+'-score.json');write(p,score);score_files[trial]=p
    return root/'freeze.json',score_files


def test_verified_two_screen_choice_keeps_discarded_work_in_budget(tmp_path):
    root=tmp_path/'experiment';freeze,scores=fixture(root)
    r=select_from_results(root,freeze,scores)
    assert r['selected_trial']=='lr-0010'
    assert r['continuation_reserved_positions']==9961347
    assert r['physical_positions_already_executed']+r['continuation_reserved_positions']==10485635
    assert r['maximum_physical_positions_after_continuation']<=10485760


@pytest.mark.parametrize('defect',['partial','resumed','events','payload','aggregation','missing_trial','budget'])
def test_changed_or_partial_cached_evidence_cannot_choose_student_resume(tmp_path,defect):
    root=tmp_path/'experiment';freeze,scores=fixture(root);trial='lr-0010';run=root/'runs'/trial
    if defect=='partial':
        p=run/'report.json';r=json.loads(p.read_text());r['final']['step']=255;write(p,r)
    elif defect=='resumed':write(run/'run.json',dict(plan_hash=trial,resume_manifest_sha256='unexpected'))
    elif defect=='events':(run/'events.jsonl').write_text('Changed events.')
    elif defect=='payload':(run/'checkpoints/cp/state/optimizer.safetensors').write_text('Changed bytes.')
    elif defect=='aggregation':
        p=scores[trial];r=json.loads(p.read_text());r['metrics']['source_balanced_foundation_nll']=0.;write(p,r)
    elif defect=='missing_trial':scores.pop(trial)
    else:
        p=root/'protocol.json';r=json.loads(p.read_text());r['exposure']['cumulative_physical_position_ceiling']=1;write(p,r)
        write(freeze,dict(protocol_sha256=sha(p)))
        for file in scores.values():
            r=json.loads(file.read_text());r['protocol_sha256']=sha(p);write(file,r)
    with pytest.raises(ValueError):select_from_results(root,freeze,scores)
