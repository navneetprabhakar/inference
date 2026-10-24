"""Read-only diagnosis of a rejected checkpoint; cannot change selection or continue training."""
import importlib.util,time,json
from pathlib import Path
R=Path(__file__).resolve().parent;P=R.parents[1]
spec=importlib.util.spec_from_file_location('rejected_broad_readonly',R/'run.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
result=r.read(R/'result.json');assert result['stop']=='FACTUAL_RETENTION_GUARD' and result['selected'] is None
assert not (R/'rejected-assessment.json').exists(),'NO_AUTOMATIC_ASSESSMENT_RETRY'
r.started=r.read(R/'started.json')['epoch'];r.s.started=r.started;r.positions=result['total_positions'];r.updates_total=result['updates_consumed'];r.sft_total=result['sft_targets_consumed'];r.replay_total=result['replay_targets_consumed'];r.active_arm='read-only-rejected-checkpoint'
rejected=result['history'][-1];prior=P/'restart/short-answer-transfer-v1/private/test-encoded.json'
r.save(R/'rejected-assessment-freeze.json',dict(script_sha256=r.s.sha(Path(__file__)),checkpoint_sha256=rejected['checkpoint_sha256'],fresh_bank_sha256=r.s.sha(R/'private/test-encoded.json'),previously_exposed_bank_sha256=r.s.sha(prior),purpose='Rejected checkpoint inference only, never eligible for selection or promotion. Fresh bank already measured twice on unchanged parent by main; this is the only rejected-child evaluation.',original_started_epoch=r.started,maximum_additional_positions=1000000))
r.frozen();assert r.s.sha(P/rejected['checkpoint'])==rejected['checkpoint_sha256'];e,c=r.s.load()
import torch
state=torch.load(P/rejected['checkpoint'],map_location='cpu',weights_only=False);e.params={new:e.mx.array(state['model'][old].numpy(),e.mx.float32) for old,new in c.mapping().items()};e.mx.eval(e.params);del state
from sentencepiece import SentencePieceProcessor
sp=SentencePieceProcessor(model_file=str(r.s.TOK));fresh=r.generate(e,c,r.read(R/'private/test-encoded.json'),sp,'rejected-fresh-test');broader=r.generate(e,c,r.read(prior),sp,'rejected-prior-broader')
rows=r.read(R/'private/rejected-fresh-test-responses.json');lookup={x['id']:x for x in r.read(R/'private/test-encoded.json')};by_family={}
for family in r.read(R/'data-receipt.json')['families']:
 a=[x for x in rows if lookup[x['id']]['family']==family];by_family[family]=dict(turns=len(a),correct_and_eos=sum(x['correct'] and x['eos'] for x in a))
strata={}
for label,t in [('familiar',0),('novel',3)]:
 a=[x for x in rows if lookup[x['id']]['template']==t];strata[label]=dict(turns=len(a),correct_and_eos=sum(x['correct'] and x['eos'] for x in a))
subskills={}
for label,selected in [('delayed_final_query',[x for x in rows if lookup[x['id']]['family']=='delayed_update' and x['turn']==2]),('answer_present',[x for x in rows if lookup[x['id']]['family']=='answerability' and lookup[x['id']]['answer_present']]),('answer_absent',[x for x in rows if lookup[x['id']]['family']=='answerability' and not lookup[x['id']]['answer_present']])]:subskills[label]=dict(turns=len(selected),correct_and_eos=sum(x['correct'] and x['eos'] for x in selected))
assert r.positions-result['total_positions']<=1000000
r.save(R/'rejected-assessment.json',dict(status='REJECTED_CHECKPOINT_INFERENCE_ONLY',checkpoint=rejected['checkpoint'],fresh_test=fresh,by_family=by_family,strata=strata,subskills=subskills,previously_exposed_broader=broader,retention=rejected['retention'],foundation_nll=rejected['foundation_nll'],foundation_regression_fraction=rejected['foundation_regression_fraction'],additional_positions=r.positions-result['total_positions'],aggregate_positions=r.positions,aggregate_elapsed_seconds=time.time()-r.started,new_updates=0,selection_changed=False,promoted=False,parent_unchanged=r.s.sha(r.s.SOURCE)==r.s.SOURCE_SHA,original_foundation_unchanged=r.s.sha(r.ORIGINAL)==r.ORIGINAL_SHA))
print(json.dumps(r.read(R/'rejected-assessment.json'),indent=2))
