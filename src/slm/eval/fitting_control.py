"""Finite reviewed-data fitting control with explicit repeats and source lineage."""
# Creator: Navneet Prabhakar
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import numpy as np
from slm.common import checkpoint
from slm.common.tokenizer import BPE
from slm.common.training import Batches,Trainer
from slm.data.review_stream import open_checked
from slm.data.schema import digest
from slm.data.tokenized import sha,stamp
from slm.eval.iteration_two_assessment import validate_and_score
from slm.eval.iteration_two_interview import converse
from slm.eval.iteration_two_selection import checked_checkpoint
from slm.eval.fresh_session import validate_response
from slm.inference.greedy import GreedyModel
from slm.stage_transition import StageInputs,POLICY,COUNTERS
from slm.train import save_checkpoint,verify_checkpoint,synchronize

ROOT=Path('data/iteration-four-fitting-control-v2').resolve()
PRIOR=Path('data/iteration-four-fitting-control-v1').resolve()
DATA=Path('data/iteration-three-sft-review-v2').resolve()
STAGE=Path('data/iteration-three-sft-stage-v2').resolve()
REASON='Separate reviewed-data fitting control from the verified foundation checkpoint; explicit fresh AdamW objective transition, retaining prior branch exposure.'


def read(path):return json.loads(Path(path).read_text())
def publish(path,value):
    with Path(path).open('x') as out:out.write(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
def append(stream,value):
    stream.write(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


class ReviewedReplay(Batches):
    """Materialize an explicit bounded stream using the existing portable Batches."""
    def __init__(self,base,passes):
        if type(passes) is not int or not 1<=passes<=8 or not 1<=len(base)<=16:
            raise ValueError('Control supports at most16 reviewed batches and eight explicit passes')
        super().__init__([base[i] for _ in range(passes) for i in range(len(base))],base.vocab_size)
        self.tokenizer_hash=base.tokenizer_hash
        self.max_length=base.max_length
        self.schedule=[dict(pass_number=p+1,source_batch=i) for p in range(passes) for i in range(len(base))]
        self.parent_fingerprint=base.fingerprint


class ControlInputs:
    """Compose the unchanged checked stage transition with an explicit repeat plan."""
    def __init__(self,spec,origin,source,report,passes=8):
        self.base=StageInputs(spec,origin,source,report,POLICY,REASON)
        try:
            if self.base.research_limits is not None or spec['data']['kind']!='tokens':
                raise ValueError('Individually approved token release required; no broad research-policy reuse')
            self.data=ReviewedReplay(self.base.data,passes)
            self.config,self.recipe=self.base.config,self.base.recipe
            self.origin,self.source_model=self.base.origin,self.base.source_model
            if self.recipe.accumulation_steps!=1 or spec['limits']!={'updates':len(self.data.items),'processed_positions':self.data.counts(len(self.data.items))[0]}:
                raise ValueError('Exact finite accumulation-one repeat limits required')
            if len(self.data.items)>128 or self.data.counts(len(self.data.items))[0]>65536 or self.data.max_length>256:
                raise ValueError('Fitting-control ceilings exceeded')
            self.plan=deepcopy(self.base.plan)
            self.plan.update(data_kind='explicit-reviewed-control-repeat-v1',data_hash=self.data.fingerprint,
                control_repeat=dict(passes=passes,source_token_hash=self.data.parent_fingerprint,schedule=self.data.schedule,
                    scope='Explicit small fitting control; does not extend the earlier risk-admitted corpus budget.'))
            self.plan['reference_sources']['eval/fitting_control.py']=sha(__file__)
            self.base.guards[Path(__file__).resolve()]=stamp(Path(__file__))
            self.identity=digest(self.plan);self.check()
        except BaseException:self.base.close();raise
    def check(self):self.base.check();self.data.counts(0)
    def close(self):self.base.close()


def actual_inputs():
    p=read(ROOT/'protocol.json')
    return ControlInputs(read(ROOT/'spec.json'),read(STAGE/'origin-spec.json'),p['source_checkpoint'],p['source_report'])


def freeze():
    if ROOT.exists():raise FileExistsError(ROOT)
    old=read(STAGE/'preparation.json');spec=deepcopy(read(STAGE/'origin-spec.json'))
    spec['data']=dict(kind='tokens',path=str(DATA/'tokens'),fingerprint=sha(DATA/'tokens/manifest.json'))
    spec['releases']={sha(DATA/'release/manifest.json'):str(DATA/'release')}
    spec['limits']=dict(updates=96,processed_positions=11336)
    spec['checkpoint']=dict(every_updates=32,keep=2)
    spec['recipe'].update(lr=3e-4,accumulation_steps=1,warmup_tokens=1024)
    inp=ControlInputs(spec,read(STAGE/'origin-spec.json'),old['source_checkpoint'],old['source_report'])
    try:
        with open_checked(DATA/'release') as index:
            train=list(index.values())
            validation=[json.loads(v) for v, in index.db.execute('SELECT data FROM approved WHERE split="validation" ORDER BY eid')]
        if len(train)!=12 or len(validation)!=4 or inp.data.counts(96)!=(11336,6808):raise ValueError('Exact existing reviewed control required')
        first=Path('configs/iteration-one-conversation-assessment-v1.json');interview=read(first)
        interview['first_iteration_protocol_sha256']=sha(first)
        from slm.eval.iteration_two_interview import protocol_checked
        protocol_checked(interview)
        ROOT.mkdir();publish(ROOT/'spec.json',spec)
        protocol=dict(creator='Navneet Prabhakar',version=1,kind='reviewed-data-fitting-control-v1',
            source_checkpoint=old['source_checkpoint'],source_report=old['source_report'],
            source_model_sha256=sha(inp.source_model/'manifest.json'),plan=inp.plan,plan_hash=inp.identity,
            spec_sha256=sha(ROOT/'spec.json'),train=train,validation=validation,conversation=interview,
            criteria=dict(maximum_masked_train_nll=.5,minimum_exact_final_references=10,minimum_learned_stops=10,generation_budget=256),
            exposure=dict(physical_positions=11336,optimizer_updates=96,group_passes=8,assistant_targets=6808),
            execution_root=str(ROOT/'training'),prior_physical_evidence={str(p):sha(p) for p in map(Path,[
                'reports/milestone-sixty-four-actual-sft-evidence.json','reports/milestone-sixty-five-fresh-session-assessment.json'])},
            source_sha256={str(p):sha(p) for p in map(Path,[__file__,'src/slm/stage_transition.py','src/slm/inference/greedy.py',
                'src/slm/eval/iteration_two_interview.py','src/slm/eval/iteration_two_assessment.py','src/slm/eval/fresh_session.py'])},
            full_step_resource_evidence={str(STAGE/('preflight-'+t+'.json')):sha(STAGE/('preflight-'+t+'.json')) for t in ('lr-00001','lr-00005')},
            scope='Separate foundation branch; not a resume of the completed noisy SFT checkpoint. Twelve reviewed train references test fitting only. Four validation groups are diagnostic, test rows unused. Whole attempt reserved once; no restart or parameter sweep. Prior charges remain unchanged and linked.')
        protocol['adoptable_prior_baseline']={str(PRIOR/name):sha(PRIOR/name) for name in
            ('protocol.json','freeze.json','executed-source.py','baseline/report.json','baseline/responses.jsonl','baseline/reservations.jsonl','superseded.json')}
        publish(ROOT/'protocol.json',protocol);publish(ROOT/'freeze.json',dict(creator='Navneet Prabhakar',protocol_sha256=sha(ROOT/'protocol.json')))
        inp.check()
    finally:inp.close()
    print(json.dumps(dict(status='frozen',updates=96,positions=11336)),flush=True)


def checked():
    p=read(ROOT/'protocol.json');f=read(ROOT/'freeze.json')
    if p['execution_root']!=str((ROOT/'training').resolve()):
        raise ValueError('Frozen absolute execution location differs; copying cannot reset the attempt')
    if sha(ROOT/'protocol.json')!=f['protocol_sha256'] or sha(ROOT/'spec.json')!=p['spec_sha256']:
        raise ValueError('Frozen fitting plan changed')
    for name,want in {**p['source_sha256'],**p['prior_physical_evidence'],**p['full_step_resource_evidence'],**p['adoptable_prior_baseline']}.items():
        if sha(name)!=want:raise ValueError('Frozen implementation/prior/resource evidence changed')
    return p


def adopt_baseline():
    p=checked();old=read(PRIOR/'protocol.json');report=read(PRIOR/'baseline/report.json')
    if (sha(PRIOR/'protocol.json')!=read(PRIOR/'freeze.json')['protocol_sha256']
        or sha(PRIOR/'executed-source.py')!=old['source_sha256'][str(Path(__file__).resolve())]
        or old['train']!=p['train'] or old['validation']!=p['validation']
        or old['source_model_sha256']!=p['source_model_sha256'] or old['plan']['recipe']!=p['plan']['recipe']
        or report['protocol_sha256']!=sha(PRIOR/'protocol.json')
        or report['student']['model_manifest_sha256']!=p['source_model_sha256']
        or report['responses_sha256']!=sha(PRIOR/'baseline/responses.jsonl')
        or report['reservations_sha256']!=sha(PRIOR/'baseline/reservations.jsonl')
        or read(PRIOR/'superseded.json')['optimizer_updates']!=0):
        raise ValueError('Prior baseline must match exact source/reference/recipe and preserved implementation')
    rows=[json.loads(x) for x in (PRIOR/'baseline/responses.jsonl').read_text().splitlines()]
    reserves=[json.loads(x) for x in (PRIOR/'baseline/reservations.jsonl').read_text().splitlines()]
    if len(rows)!=12 or len(reserves)!=12:raise ValueError('Complete prior baseline required')
    bpe=BPE.load(read(ROOT/'spec.json')['tokenizer'])
    for i,(case,row,reserve) in enumerate(zip(p['train'],rows,reserves)):
        if (row['example_id']!=case['example_id'] or row['reference']!=case['messages'][-1]['content']
            or row['history_sha256']!=digest(case['messages'][:-1])
            or reserve!=dict(sequence=i+1,example_id=case['example_id'],maximum_tokens=256,protocol_sha256=sha(PRIOR/'protocol.json'))):
            raise ValueError('Prior baseline reference/order/reservation differs')
        validate_response(dict(messages=case['messages'][:-1]),row['response'],bpe,256)
    target=ROOT/'baseline';target.mkdir()
    for name in ('responses.jsonl','reservations.jsonl'):shutil.copyfile(PRIOR/'baseline'/name,target/name)
    result=deepcopy(report)
    result.update(protocol_sha256=sha(ROOT/'protocol.json'),adopted_from=dict(
        protocol_sha256=sha(PRIOR/'protocol.json'),report_sha256=sha(PRIOR/'baseline/report.json'),
        reason='Same source model, reference contexts/targets and recipe; only the untrained controller location check changed. No generation replay.'))
    publish(target/'report.json',result)
    print(json.dumps(dict(status='baseline_adopted_without_replay',train_nll=report['metrics']['train']['masked_token_weighted_nll'])),flush=True)


def verified_terminal():
    p=checked();r=read(ROOT/'training/report.json');path=Path(r['latest_checkpoint'])
    checked_checkpoint(path,r['latest_manifest_sha256'])
    binding=read(path/'binding.json');state=read(path/'state/state.json')
    expected=dict(step=96,cursor=96,tokens=11336,supervised_tokens=6808)
    if (r['status']!='update_target_reached' or r['final']!=expected or r['plan_hash']!=p['plan_hash']
        or binding['plan']!=p['plan'] or binding['plan_hash']!=p['plan_hash']
        or any(state[k]!=v for k,v in expected.items()) or state['dataset_hash']!=p['plan']['data_hash']
        or state['recipe']!=p['plan']['recipe'] or state['tokenizer_hash']!=p['plan']['tokenizer_hash']
        or sha(ROOT/'training/events.jsonl')!=r['events_sha256'] or read(ROOT/'attempt-reservation.json')['protocol_sha256']!=sha(ROOT/'protocol.json')):
        raise ValueError('Complete frozen fitting endpoint required')
    events=[json.loads(x) for x in (ROOT/'training/events.jsonl').read_text().splitlines()]
    if [r['step'] for r in events]!=list(range(1,97)):raise ValueError('Actual update coverage differs')
    return path


def evaluate(terminal=False):
    if not terminal:
        adopt_baseline();return
    p=checked();phase='terminal' if terminal else 'baseline';target=ROOT/phase
    if target.exists():raise FileExistsError(target)
    model_path=verified_terminal()/'state/model' if terminal else Path(p['source_checkpoint'])/'state/model'
    if not terminal:checked_checkpoint(Path(p['source_checkpoint']),p['plan']['initialization']['source_checkpoint_sha256'])
    target.mkdir();spec=read(ROOT/'spec.json')
    model=GreedyModel(model_path,spec['tokenizer'],'mlx','default',expected_tokenizer_hash=p['plan']['tokenizer_hash'],embedding_implementation=p['plan']['recipe']['embedding_implementation'])
    bpe=model.tokenizer;groups={};outputs=[]
    for split in ('train','validation'):
        losses=[];total=targets=0
        for row in p[split]:
            x,y,m=bpe.serialize(row['messages']);n=sum(m)
            with model.context():
                loss=float(model.impl.loss(model.params,model.config,model.array([x]),model.array([y]),model.array([m]),
                    loss_implementation=p['plan']['recipe']['loss_implementation'],embedding_implementation=model.embedding_implementation))
            if not np.isfinite(loss):raise ValueError('Nonfinite masked reference loss')
            losses.append(dict(example_id=row['example_id'],nll=loss,targets=n));total+=loss*n;targets+=n
        groups[split]=dict(masked_token_weighted_nll=total/targets,targets=targets,rows=losses)
    with (target/'responses.jsonl').open('x') as out,(target/'reservations.jsonl').open('x') as journal:
        for i,row in enumerate(p['train']):
            history=row['messages'][:-1];reference=row['messages'][-1]['content']
            append(journal,dict(sequence=i+1,example_id=row['example_id'],maximum_tokens=256,protocol_sha256=sha(ROOT/'protocol.json')))
            response=model.generate(deepcopy(history),256)
            validate_response(dict(messages=history),response,bpe,256)
            value=dict(example_id=row['example_id'],history_sha256=digest(history),reference=reference,response=response,
                exact_reference=response['text']==reference,learned_stop=response['stop_reason'] in ('message_end','eos'))
            append(out,value);outputs.append(value)
            print(json.dumps(dict(phase=phase,example_id=row['example_id'],exact_reference=value['exact_reference'],learned_stop=value['learned_stop'],text=response['text']),ensure_ascii=False),flush=True)
    checked();criteria=p['criteria'];exact=sum(r['exact_reference'] for r in outputs);stops=sum(r['learned_stop'] for r in outputs)
    result=dict(creator='Navneet Prabhakar',phase=phase,protocol_sha256=sha(ROOT/'protocol.json'),student=model.identity,metrics=groups,
        exact_final_references=exact,learned_stops=stops,generated_tokens=sum(r['response']['generated_tokens'] for r in outputs),
        responses_sha256=sha(target/'responses.jsonl'),reservations_sha256=sha(target/'reservations.jsonl'),
        fitting_criterion_passed=bool(groups['train']['masked_token_weighted_nll']<=criteria['maximum_masked_train_nll'] and exact>=criteria['minimum_exact_final_references'] and stops>=criteria['minimum_learned_stops']),
        actual_conversation_assessment_pending=terminal,production_accepted=False,
        scope='Memorization/control assay on source references with supplied earlier assistant context where present. Validation NLL is separate; no conversation score or broad correctness inferred.')
    publish(target/'report.json',result);print(json.dumps(dict(phase=phase,train_nll=groups['train']['masked_token_weighted_nll'],exact=exact,stops=stops,fitting_passed=result['fitting_criterion_passed'])),flush=True)


def train():
    p=checked()
    if not (ROOT/'baseline/report.json').exists():raise ValueError('Complete frozen baseline required')
    baseline=read(ROOT/'baseline/report.json')
    if (baseline['protocol_sha256']!=sha(ROOT/'protocol.json') or baseline['phase']!='baseline'
        or baseline['student']['model_manifest_sha256']!=p['source_model_sha256']
        or baseline['responses_sha256']!=sha(ROOT/'baseline/responses.jsonl')):
        raise ValueError('Exact completed source baseline required')
    if (ROOT/'attempt-reservation.json').exists() or (ROOT/'training').exists():raise FileExistsError('Fitting attempt already reserved; no automatic replay')
    inp=actual_inputs()
    try:
        if inp.identity!=p['plan_hash'] or inp.plan!=p['plan']:raise ValueError('Actual control plan changed')
        cfg,weights=checkpoint.load(inp.source_model)
        trainer=Trainer(cfg,weights,inp.data,'mlx','default',inp.recipe,inp.data.tokenizer_hash)
        exported=trainer.impl.export(trainer.params)
        if trainer.moments or any(getattr(trainer,k) for k in COUNTERS) or any(not np.array_equal(exported[k].view(np.uint32),v.view(np.uint32)) for k,v in weights.items()):
            raise ValueError('Exact foundation import/fresh optimizer failed')
        del weights,exported
        initialization=ROOT/'initialization';initialization.mkdir();initial=save_checkpoint(initialization,trainer,inp,{})
        publish(initialization/'report.json',dict(creator='Navneet Prabhakar',status='initialized_only',checkpoint=str(initial),checkpoint_sha256=sha(initial/'manifest.json'),source_model_sha256=p['source_model_sha256'],weight_bits_exact=True,optimizer_updates=0))
        publish(ROOT/'attempt-reservation.json',dict(creator='Navneet Prabhakar',protocol_sha256=sha(ROOT/'protocol.json'),
            exposure=p['exposure'],scope='Entire finite attempt conservatively precharged; failed/uncertain work is not automatically replayable. Prior physical evidence remains linked by the protocol.'))
        output=ROOT/'training';output.mkdir()
        publish(output/'run.json',dict(creator='Navneet Prabhakar',logical_plan=inp.plan,plan_hash=inp.identity,source_import=str(initial),protocol_sha256=sha(ROOT/'protocol.json')))
        with (output/'events.jsonl').open('x') as out:
            while trainer.step<96:
                inp.check();checked();value=trainer.update();synchronize('mlx','default');append(out,value)
                if trainer.step%32==0:latest=save_checkpoint(output,trainer,inp,{})
        inp.check();latest=save_checkpoint(output,trainer,inp,{})
        result=dict(creator='Navneet Prabhakar',status='update_target_reached',plan_hash=inp.identity,
            final={k:getattr(trainer,k) for k in COUNTERS},latest_checkpoint=str(latest),latest_manifest_sha256=sha(latest/'manifest.json'),
            events_sha256=sha(output/'events.jsonl'),conservatively_reserved=p['exposure'],source_model_sha256=p['source_model_sha256'],
            scope='Separate finite reviewed-data foundation branch. Prior noisy SFT endpoint remains unchanged; no generalization acceptance.')
        publish(output/'report.json',result);verified_terminal();print(json.dumps(result),flush=True)
    finally:inp.close()


def conversation_binding():
    path=verified_terminal();p=checked();score=read(ROOT/'terminal/report.json')
    if score['protocol_sha256']!=sha(ROOT/'protocol.json') or score['student']['model_manifest_sha256']!=sha(path/'state/model/manifest.json'):
        raise ValueError('Terminal fitting assay required before interview')
    spec=read(ROOT/'spec.json')
    return dict(model_path=str(path/'state/model'),model_manifest_sha256=sha(path/'state/model/manifest.json'),
        tokenizer_path=spec['tokenizer'],tokenizer_manifest_sha256=p['plan']['tokenizer_hash'],
        embedding_implementation=p['plan']['recipe']['embedding_implementation'],plan_hash=p['plan_hash'],
        terminal_report_sha256=sha(ROOT/'training/report.json'),terminal_assay_sha256=sha(ROOT/'terminal/report.json'))


def interview():
    p=checked();binding=conversation_binding();protocol=p['conversation']
    model=GreedyModel(binding['model_path'],binding['tokenizer_path'],'mlx','default',expected_tokenizer_hash=binding['tokenizer_manifest_sha256'],embedding_implementation=binding['embedding_implementation'])
    header=dict(creator='Navneet Prabhakar',protocol_sha256=sha(ROOT/'protocol.json'),protocol_digest=digest(protocol),student=model.identity,
        terminal=binding,interviewer_sha256=sha(__file__),review_mode='delegated_expert',human_attestation=False,training_approved=False,
        created_at_utc=datetime.now(timezone.utc).isoformat())
    def requests():
        for line in sys.stdin:yield json.loads(line)
    def emit(v):print(json.dumps(v,ensure_ascii=False),flush=True)
    converse(model,protocol,ROOT/'conversation',header,requests(),emit)


def assess(grades):
    p=checked();binding=conversation_binding();folder=ROOT/'conversation';header=read(folder/'session.json');complete=read(folder/'completion.json')
    architecture=read(Path(binding['model_path'])/'config.json')['architecture']
    if (header['terminal']!=binding or header['protocol_sha256']!=sha(ROOT/'protocol.json') or header['interviewer_sha256']!=sha(__file__)
        or header['protocol_digest']!=digest(p['conversation']) or header['student']['model_manifest_sha256']!=binding['model_manifest_sha256']
        or header['student']['tokenizer_manifest_sha256']!=binding['tokenizer_manifest_sha256']
        or header['student']['architecture']!=architecture or header['student']['embedding_implementation']!=binding['embedding_implementation']
        or header['student']['decoding']!=p['conversation']['decoding'] or header['review_mode']!='delegated_expert'
        or header['human_attestation'] is not False or header['training_approved'] is not False
        or complete['session_sha256']!=sha(folder/'session.json') or complete['turns_sha256']!=sha(folder/'turns.jsonl') or complete['turns']!=8
        or complete['human_attestation'] is not False or complete['training_approved'] is not False or complete['assessment_pending'] is not True):
        raise ValueError('Bound completed raw interview required')
    result=validate_and_score([json.loads(x) for x in (folder/'turns.jsonl').read_text().splitlines()],p['conversation'],BPE.load(binding['tokenizer_path']),read(grades))
    result.update(creator='Navneet Prabhakar',terminal=binding,student=header['student'],protocol_sha256=sha(ROOT/'protocol.json'),
        transcript_sha256=sha(folder/'turns.jsonl'),grades_sha256=sha(grades),assessment_code_sha256=sha(__file__))
    publish(ROOT/'conversation-assessment.json',result)
    print(json.dumps({k:result[k] for k in ('normalized_score_out_of_100','successful_tasks','turns')}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['freeze','baseline','train','terminal','interview','assess']);parser.add_argument('--grades')
    a=parser.parse_args()
    if a.action=='freeze':freeze();return
    with (ROOT/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='baseline':evaluate()
        elif a.action=='terminal':evaluate(True)
        elif a.action=='train':train()
        elif a.action=='interview':interview()
        elif a.grades:assess(a.grades)
        else:raise ValueError('Direct grades required')


if __name__=='__main__':main()
