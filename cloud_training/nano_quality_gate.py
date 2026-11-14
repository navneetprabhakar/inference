"""Fail-closed training and release controls. No metric here certifies general intelligence."""
from __future__ import annotations
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path


def sha256(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def dataset_coverage(dataset):
    rows=[json.loads(line) for line in dataset.path.read_text().splitlines()]
    families={};modes=Counter()
    for row,targets in zip(rows,dataset.target_counts,strict=True):
        name=row.get('family','unclassified');f=families.setdefault(name,{'sessions':0,'assistant_targets':0})
        f['sessions']+=1;f['assistant_targets']+=targets
        policies=row.get('policies');turn=-1;called=False;enabled=False
        for m in row['messages']:
            if m['role']=='user':
                if turn>=0:modes[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
                turn+=1;enabled=bool(policies and policies[turn]['permit_calls']);called=False
            elif m['role']=='assistant' and 'tool_call' in m:called=True
        modes[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
    return {'sessions':len(rows),'assistant_targets':sum(dataset.target_counts),'families':families,'turn_modes':dict(modes)}


def contract_errors(contract, *, manifest, admission, train, dev, epochs, lr_multiplier, eval_interval, max_updates=None):
    errors=[]
    for key in ('dataset_manifest_sha256','tokenizer_sha256','required_parent_manifest_sha256','release_suite_sha256','protected_suite_sha256'):
        if not isinstance(contract.get(key),str) or not re.fullmatch('[0-9a-f]{64}',contract[key]):errors.append('Missing valid immutable identity: '+key)
    if contract.get('schema')!=1 or contract.get('objective')!='conversation_and_tools':return ['Missing supported quality contract']
    for key,actual in [('dataset_manifest_sha256',manifest['_sha256']),('tokenizer_sha256',manifest['tokenizer_sha256']),('context_tokens',manifest['context_tokens'])]:
        if contract.get(key)!=actual:errors.append('Contract/input mismatch: '+key)
    if contract.get('required_parent_manifest_sha256')!=admission.get('parent_manifest_sha256'):
        errors.append('Required corpus revision is not the admitted parent; resolve data intent explicitly')
    coverage=contract.get('coverage',{});limits=contract.get('recipe_limits',{})
    required_modes={'disabled_no_call','enabled_no_call','enabled_call'}
    minima=coverage.get('minimum_training_turns',{})
    if set(minima)!=required_modes or any(type(v)is not int or v<1 for v in minima.values()):errors.append('All three policy/action coverage minima must be positive')
    for mode,minimum in minima.items():
        if type(minimum)is int and train['turn_modes'].get(mode,0)<minimum:errors.append('Missing training coverage: '+mode)
        if dev['turn_modes'].get(mode,0)==0:errors.append('Missing development coverage: '+mode)
    minimum=coverage.get('minimum_unique_assistant_targets')
    if type(minimum)is not int or minimum<1 or train['assistant_targets']<minimum:errors.append('Unique assistant-target floor unmet or invalid')
    minima=coverage.get('minimum_family_sessions',{})
    if not minima:errors.append('Required semantic families unspecified')
    for family,minimum in minima.items():
        if type(minimum)is not int or minimum<1 or train['families'].get(family,{}).get('sessions',0)<minimum:errors.append('Family coverage unmet: '+family)
        if dev['families'].get(family,{}).get('sessions',0)==0:errors.append('Missing development family: '+family)
    for key,actual in [('max_epochs',epochs),('max_lr_multiplier',lr_multiplier),('max_eval_interval',eval_interval)]:
        limit=limits.get(key)
        if not finite(limit) or limit<=0 or actual>limit:errors.append('Recipe exceeds or lacks quality bound: '+key)
    if 'max_pilot_updates' in limits:
        ceiling=limits['max_pilot_updates']
        if type(ceiling)is not int or ceiling<1 or type(max_updates)is not int or not 1<=max_updates<=ceiling:errors.append('Missing or exceeded bounded pilot update limit')
    if contract.get('unresolved_required_data'):errors.append('Required data remains excluded/untrained')
    try:ValidationGuard(contract['regression'])
    except (KeyError,ValueError,TypeError):errors.append('Invalid mandatory regression guard')
    return errors


class ValidationGuard:
    """Persisted, idempotent validation patience; cannot reset on a resume."""
    def __init__(self, policy, state=None):
        tolerance=policy.get('relative_tolerance');patience=policy.get('patience')
        if not finite(tolerance) or not 0<=tolerance<=.25 or type(patience)is not int or not 1<=patience<=3:raise ValueError('Invalid regression policy')
        self.policy=dict(policy)
        self.state=dict(state) if state is not None else {'best_ce':None,'best_step':None,'last_step':-1,'last_ce':None,'strikes':0,'stopped':False}
        s=self.state
        if set(s)!={'best_ce','best_step','last_step','last_ce','strikes','stopped'}:raise ValueError('Invalid guard resume fields')
        if type(s['last_step'])is not int or s['last_step']< -1 or type(s['strikes'])is not int or s['strikes']<0 or type(s['stopped'])is not bool:raise ValueError('Invalid guard resume state')
        if s['last_step']>=0 and (not finite(s['best_ce']) or s['best_ce']<=0 or not finite(s['last_ce']) or s['last_ce']<=0 or s['best_ce']>s['last_ce'] or type(s['best_step'])is not int or not 0<=s['best_step']<=s['last_step']):raise ValueError('Invalid guard resume observations')
        if s['last_step']==-1 and (s['best_ce'] is not None or s['best_step'] is not None or s['last_ce'] is not None or s['strikes']!=0 or s['stopped']):raise ValueError('Invalid empty guard state')
        if s['stopped']!=(s['strikes']>=patience):raise ValueError('Inconsistent guard stop state')
    def observe(self,step,ce):
        s=self.state
        if type(step)is not int or step<0 or not finite(ce) or ce<=0:raise ValueError('Invalid validation observation')
        if step<s['last_step']:raise ValueError('Validation steps cannot move backwards')
        if step==s['last_step']:
            if not math.isclose(ce,s['last_ce'],rel_tol=1e-8,abs_tol=1e-10):raise ValueError('Changed validation on same-step resume')
            return s['stopped']
        if s['stopped']:return True
        if s['best_ce'] is None or ce<s['best_ce']:s.update(best_ce=ce,best_step=step,strikes=0)
        elif ce>s['best_ce']*(1+self.policy['relative_tolerance']):s['strikes']+=1
        else:s['strikes']=0
        s.update(last_step=step,last_ce=ce,stopped=s['strikes']>=self.policy['patience'])
        return s['stopped']


def evaluation_candidates(journal,best_step,last_step):
    """Require durable best AND last; never silently substitute the last for best."""
    result=[]
    for step in dict.fromkeys([best_step,last_step]):
        if type(step)is not int or step<0:raise ValueError('Missing best/last step')
        found=[e for e in journal['entries'] if e['state']=='committed' and e['receipt']['step']==step]
        if len(found)!=1:raise ValueError('Missing/ambiguous durable evaluation checkpoint')
        e=found[0]
        if step==best_step and 'best' not in e['pins']:raise ValueError('Best checkpoint is not protected')
        manifest=e['receipt']['manifest'];digest=hashlib.sha256((json.dumps(manifest,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()).hexdigest()
        result.append({'step':step,'roles':[role for role,wanted in [('best_development',best_step),('last',last_step)] if wanted==step],'remote_prefix':e['receipt']['remote_prefix'],'manifest_sha256':digest,'requires_generation_review':True})
    return result


def release_decision(*, raw, raw_sha256, suite, suite_sha256, review, contract, checkpoint_identity, protected=None, protected_suite=None, protected_suite_sha256=None):
    """Derive scores from complete hash-bound per-turn review; aggregate claims ignored."""
    errors=[]
    for value in [raw_sha256,suite_sha256,contract.get('_sha256'),raw.get('checkpoint_manifest_sha256')]:
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):errors.append('Missing immutable release evidence hash')
    if contract.get('require_one_shot_release'):
        claim=raw.get('release_claim',{})
        if claim.get('checkpoint_manifest_sha256')!=raw.get('checkpoint_manifest_sha256') or claim.get('suite_sha256')!=suite_sha256 or not claim.get('utc'):errors.append('Missing or mismatched one-shot release claim')
    if raw.get('status') not in ('complete_requires_full_review','complete'):errors.append('Raw evaluation did not complete')
    expected=[(s['id'],i) for s in suite.get('sessions',[]) for i,_ in enumerate(s['turns'])]
    if not expected:errors.append('Empty suite')
    if suite.get('purpose')!='heldout_release_never_train':errors.append('Development/exposed suite cannot authorize release')
    if contract.get('release_suite_sha256')!=suite_sha256 or raw.get('suite_sha256')!=suite_sha256:errors.append('Release suite identity mismatch')
    if checkpoint_identity.get('quality_contract_sha256')!=contract.get('_sha256'):errors.append('Training was not bound to this quality contract')
    if review.get('raw_sha256')!=raw_sha256 or review.get('checkpoint_manifest_sha256')!=raw.get('checkpoint_manifest_sha256'):errors.append('Review not bound to raw checkpoint outputs')
    if not review.get('reviewer') or not review.get('reviewed_utc'):errors.append('Missing reviewer provenance')
    records=raw.get('records',[]);judgments=review.get('records',[])
    if [(r.get('session'),r.get('turn')) for r in records]!=expected or [(r.get('session'),r.get('turn')) for r in judgments]!=expected or len(set(expected))!=len(expected):errors.append('Missing, duplicate, reordered or extra review/raw turns')
    if protected is None or protected_suite is None:errors.append('Missing protected regression evidence')
    else:errors.extend(protected_errors(protected,protected_suite,suite_sha256=protected_suite_sha256,expected_suite_sha256=contract.get('protected_suite_sha256'),checkpoint_sha256=raw.get('checkpoint_manifest_sha256')))
    if errors:return {'status':'blocked','reasons':errors,'quality_accepted':False}
    categories={s['id']:s['category'] for s in suite['sessions']};scores={};sessions={};invalid=0;tool_errors=0
    for r,j in zip(records,judgments,strict=True):
        category=categories[r['session']];result=r['result'];valid=result.get('status')=='complete';invalid+=not valid
        if type(j.get('strict_pass'))is not bool or not j.get('reason'):errors.append('Incomplete semantic review')
        tool_ok=category!='tool' or j.get('tool_workflow_pass') is True
        if category=='tool' and not tool_ok:tool_errors+=1
        passed=valid and j.get('strict_pass') is True and tool_ok
        bucket=scores.setdefault(category,{'passed':0,'total':0});bucket['total']+=1;bucket['passed']+=passed;sessions.setdefault(r['session'],[]).append(passed)
    thresholds=contract.get('release',{});minimums=thresholds.get('minimum_turns_by_category',{})
    if not minimums or not set(minimums)<=set(scores):errors.append('Required release categories absent')
    floor=thresholds.get('minimum_category_pass_rate');session_floor=thresholds.get('minimum_complete_session_rate')
    if not finite(floor) or not 0<floor<=1 or not finite(session_floor) or not 0<session_floor<=1:errors.append('Invalid release thresholds')
    else:
        for category,counts in scores.items():
            minimum=minimums.get(category)
            if type(minimum)is not int or minimum<1 or counts['total']<minimum or counts['passed']/counts['total']<floor:errors.append('Category quality floor failed: '+category)
        if sum(all(v) for v in sessions.values())/len(sessions)<session_floor:errors.append('Complete-session quality floor failed')
    if invalid:errors.append('Incomplete/invalid/blocked serving turns')
    if tool_errors:errors.append('Incorrect or unreviewed tool workflows')
    return {'status':'blocked' if errors else 'accepted','quality_accepted':not errors,'reasons':errors,'categories':scores,'complete_sessions':sum(all(v) for v in sessions.values()),'sessions':len(sessions),'invalid_turns':invalid,'tool_workflow_failures':tool_errors}


def protected_errors(raw, suite, *, suite_sha256, expected_suite_sha256, checkpoint_sha256):
    """Recompute protected exact workflow checks; never trust stored pass totals."""
    from cloud_training.nano_quality import assess
    errors=[]
    if suite_sha256!=expected_suite_sha256 or raw.get('suite_sha256')!=suite_sha256:errors.append('Protected suite identity mismatch')
    if raw.get('checkpoint_manifest_sha256')!=checkpoint_sha256:errors.append('Protected checkpoint mismatch')
    if raw.get('status')!='development_checks_complete':errors.append('Protected evaluation incomplete')
    expected=[(s['id'],i,t) for s in suite.get('sessions',[]) for i,t in enumerate(s['turns'])]
    records=raw.get('records',[])
    if not expected or [(r.get('session'),r.get('turn')) for r in records]!=[(s,i) for s,i,_ in expected]:return errors+['Protected coverage mismatch']
    for r,(_,_,spec) in zip(records,expected,strict=True):
        if not spec.get('exact_answers') or not assess(r['result'],spec)['automated_pass']:errors.append('Protected exact workflow failed: '+r['session'])
    return errors


def main():
    import argparse
    p=argparse.ArgumentParser(description='Require a complete, hash-bound held-out semantic review before accepting a checkpoint.')
    for name in ['contract','raw','suite','review','checkpoint','protected','protected-suite','output']:p.add_argument('--'+name,required=True)
    a=p.parse_args();output=Path(a.output)
    if output.exists():raise FileExistsError('Do not overwrite release evidence')
    from cloud_training.nano_checkpoint import validate_bundle
    validate_bundle(Path(a.checkpoint))
    read=lambda path:json.loads(Path(path).read_text())
    contract=read(a.contract);contract['_sha256']=sha256(a.contract);raw=read(a.raw)
    if raw.get('checkpoint_manifest_sha256')!=sha256(Path(a.checkpoint)/'manifest.json'):raise ValueError('Evaluation/checkpoint mismatch')
    protected_path=Path(a.protected);protected_suite=Path(a.protected_suite)
    decision=release_decision(raw=raw,raw_sha256=sha256(a.raw),suite=read(a.suite),suite_sha256=sha256(a.suite),review=read(a.review),contract=contract,checkpoint_identity=read(Path(a.checkpoint)/'metadata.json')['identity'],protected=read(protected_path),protected_suite=read(protected_suite),protected_suite_sha256=sha256(protected_suite))
    decision.update(protected_raw_sha256=sha256(protected_path),protected_suite_sha256=sha256(protected_suite))
    decision.update(checkpoint_manifest_sha256=raw['checkpoint_manifest_sha256'],contract_sha256=contract['_sha256'],raw_sha256=sha256(a.raw),review_sha256=sha256(a.review))
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(decision,indent=2,allow_nan=False)+'\n')
    print(json.dumps(decision,indent=2));return 0 if decision['quality_accepted'] else 2



def campaign_decision(state):
    """Pure admission decision for a *new* campaign; never allocates a VM itself.

    Checks need named SHA-bound receipts. The allocator must independently verify
    these receipts; this function is not a signature/authentication system.
    """
    required=('data_review','group_split_audit','policy_coverage','source_intent','token_mask_audit',
              'release_suite_frozen','protected_suite_frozen','cpu_tests','gpu_recovery_qualification',
              'stop_backup_drill','generation_sentinels','local_qualification_plan')
    errors=[]
    if state.get('schema')!=1:errors.append('Unsupported campaign state')
    if state.get('phase')!='ready_for_bounded_pilot':errors.append('Campaign is on quality hold')
    if type(state.get('failed_pilots'))is not int or not 0<=state['failed_pilots']<2:errors.append('Two failed pilots require a new diagnosis; no automatic retry')
    if type(state.get('active_training_vms'))is not int or state['active_training_vms']!=0:errors.append('One-writer constraint: an existing VM is active or status unknown')
    budget=state.get('budget',{})
    values=[budget.get(k) for k in ('authorized_usd','spent_upper_bound_usd','reserve_usd','pilot_upper_bound_usd')]
    if not all(finite(v) and v>=0 for v in values) or values[0]<=0 or values[2]<=0 or values[3]<=0:errors.append('Missing finite numeric budget, pilot bound or backup reserve')
    elif values[1]+values[2]+values[3]>values[0]:errors.append('Pilot plus reserve exceeds authorized cap')
    checks=state.get('checks',{})
    for name in required:
        receipt=checks.get(name,{})
        if receipt.get('status')!='pass' or not re.fullmatch('[0-9a-f]{64}',str(receipt.get('sha256',''))):errors.append('Missing passing evidence: '+name)
    return {'action':'hold_vm_off' if errors else 'eligible_for_bounded_pilot_after_receipt_verification','reasons':errors,'quality_accepted':False,'automatic_budget_increase_allowed':False,'automatic_data_or_lr_change_allowed':False}

if __name__=='__main__':raise SystemExit(main())
