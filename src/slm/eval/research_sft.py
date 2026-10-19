"""Frozen local SFT diagnostics, finite optimizer choice and execution orchestration."""
# Creator: Navneet Prabhakar
import argparse
from dataclasses import asdict
import fcntl
import json
from pathlib import Path
import numpy as np
from slm.common import checkpoint
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.sft_research import open_research
from slm.data.tokenized import sha
from slm.eval.iteration_two import score as retention_score
from slm.eval.iteration_two_interview import protocol_checked
from slm.research_sft_stage import ResearchStageInputs, ExposureLedger, POLICY, run
from slm.train import read, verify_checkpoint

STAGE = Path('data/iteration-three-sft-stage-v2').resolve()
ROOT = Path('data/iteration-three-sft-experiment-v1').resolve()
TRIALS = ('lr-00001', 'lr-00005')
RULES = dict(screen_updates=64, retention_max_regression_nats=.2,
             lower_lr_tie_margin_nats=.01, bootstrap_seed=20261019,
             bootstrap_resamples=10000, terminal_min_improvement_nats=.1)


def publish(path, value):
    with Path(path).open('x') as out:
        out.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def groups_from(index, bpe):
    train = {g for g, in index.db.execute('SELECT DISTINCT gid FROM approved WHERE split="train"')}
    result = []
    for data, gid in index.db.execute('SELECT data,gid FROM approved WHERE split="validation" ORDER BY eid'):
        row = json.loads(data)
        x, y, mask = bpe.serialize(row['messages'], objective='assistant')
        if gid in train or not 1 <= len(x) <= 2048 or sum(mask) < 16:
            raise ValueError('Whole validation dialogue/group differs')
        result.append(dict(source=row['source'], example_id=row['example_id'], group=gid,
                           record_sha256=digest(row), x=x, y=y, assistant_mask=mask))
    if len({g['group'] for g in result}) != len(result) or not result:
        raise ValueError('Distinct nonempty validation groups required')
    return result


def choose(results, baseline, rules=RULES):
    if set(results) != set(TRIALS): raise ValueError('Both complete equal-exposure screens required')
    eligible = []
    for trial in TRIALS:
        a = results[trial]['assistant_mean_nll']
        f = results[trial]['retention']['source_balanced_foundation_nll']
        if not np.isfinite([a, f, baseline['retention']['source_balanced_foundation_nll']]).all():
            raise ValueError('Finite diagnostics required')
        if f <= baseline['retention']['source_balanced_foundation_nll'] + rules['retention_max_regression_nats']:
            eligible.append(trial)
    if not eligible: return None
    if len(eligible) == 1: return eligible[0]
    return TRIALS[0] if results[TRIALS[0]]['assistant_mean_nll'] <= results[TRIALS[1]]['assistant_mean_nll'] + rules['lower_lr_tie_margin_nats'] else TRIALS[1]


def paired(initial, final, rules=RULES):
    a, b = np.asarray(initial, float), np.asarray(final, float)
    if a.ndim != 1 or a.shape != b.shape or not len(a) or not np.isfinite([a,b]).all():
        raise ValueError('Finite complete paired group losses required')
    delta = a-b
    rng = np.random.default_rng(rules['bootstrap_seed'])
    draws = delta[rng.integers(0, len(delta), (rules['bootstrap_resamples'],len(delta)))].mean(1)
    lo, hi = map(float, np.percentile(draws,[2.5,97.5]))
    return dict(mean_improvement_nats=float(delta.mean()), improvement_95_percentile_ci=[lo,hi],
                bootstrap_resamples=rules['bootstrap_resamples'], bootstrap_seed=rules['bootstrap_seed'],
                diagnostic_smoke_passed=bool(delta.mean() >= rules['terminal_min_improvement_nats'] and lo > 0),
                conversation_capability_proved=False, production_accepted=False)


def inputs(trial):
    prep = read(STAGE/'preparation.json')
    return ResearchStageInputs(read(STAGE/(trial+'.json')), read(STAGE/'origin-spec.json'),
        prep['source_checkpoint'], prep['source_report'], POLICY, prep['transition_reason'])


def freeze():
    if ROOT.exists(): raise FileExistsError(ROOT)
    prep = read(STAGE/'preparation.json')
    for name, want in prep['source_sha256'].items():
        if sha(name) != want: raise ValueError('Executed stage source changed')
    with_inputs = inputs(TRIALS[0])
    try:
        spec = read(STAGE/(TRIALS[0]+'.json'))
        with open_research(next(iter(spec['releases'].values())), spec['policy_file_sha256']) as index:
            groups = groups_from(index, BPE.load(spec['tokenizer']))
        if len(groups) != 109: raise ValueError('All 109 validation groups required')
        retention = read('data/iteration-two-experiment-v1/protocol.json')['groups']
        if len(retention) != 64: raise ValueError('Original 64 retention groups required')
        old = Path('configs/iteration-one-conversation-assessment-v1.json')
        interview = read(old)
        interview.update(first_iteration_protocol_sha256=sha(old))
        protocol_checked(interview)
        sources = dict(prep['source_sha256'])
        for name in ('src/slm/eval/research_sft.py','src/slm/eval/iteration_two.py',
                     'src/slm/eval/iteration_two_interview.py','src/slm/eval/iteration_two_assessment.py',
                     'src/slm/inference/greedy.py','configs/iteration-one-conversation-assessment-v1.json'):
            sources[name] = sha(name)
        protocol = dict(version=1, kind='sft-terminal-assessment-contract-v1',creator='Navneet Prabhakar',
            actual_conversation_and_direct_score_required=True, policy_file_sha256=spec['policy_file_sha256'],
            groups=groups, groups_sha256=digest(groups), retention_groups=retention,
            retention_groups_sha256=digest(retention), rules=RULES, conversation=interview,
            stage_preparation_sha256=sha(STAGE/'preparation.json'), source_sha256=sources,
            selection_scope='Validation diagnostics only; no test losses, no factual-gold claim, no readiness percentage.',
            continuation_rule='Both screens must complete exactly 64 updates; choose by mean per-group assistant NLL subject to retention guard, lower LR within .01 nats. If neither eligible, stop and assess the lower-LR screen without continuation.',
            post_training_rule='At terminal checkpoint, retain all eight adaptive raw turns, directly score unchanged five-dimension rubric, record failures and limitations before any next iteration.')
        ROOT.mkdir()
        publish(ROOT/'protocol.json', protocol)
        contract = dict(version=1, kind='bounded-research-sft-experiment-v1',policy_file_sha256=spec['policy_file_sha256'],
            plans=[prep['trials'][t]['plan_hash'] for t in TRIALS],
            limits=dict(physical_data_positions=915325, optimizer_updates=539, max_physical_passes_per_group=3),
            preflight={prep['trials'][t]['plan_hash']:dict(path=str(STAGE/('preflight-'+t+'.json')),
                sha256=sha(STAGE/('preflight-'+t+'.json'))) for t in TRIALS},
            assessment=dict(path=str(ROOT/'protocol.json'),sha256=sha(ROOT/'protocol.json')),
            execution_root=str(ROOT/'execution'))
        publish(ROOT/'contract.json',contract)
        publish(ROOT/'freeze.json',dict(creator='Navneet Prabhakar',protocol_sha256=sha(ROOT/'protocol.json'),
            contract_sha256=sha(ROOT/'contract.json'),baseline_not_yet_scored=True))
        with_inputs.check()
    finally: with_inputs.close()
    print(json.dumps(dict(status='frozen',validation_groups=len(groups),retention_groups=len(retention))))


def checked():
    frozen = read(ROOT/'freeze.json')
    if sha(ROOT/'protocol.json') != frozen['protocol_sha256'] or sha(ROOT/'contract.json') != frozen['contract_sha256']:
        raise ValueError('Frozen experiment changed')
    p = read(ROOT/'protocol.json')
    if digest(p['groups']) != p['groups_sha256'] or digest(p['retention_groups']) != p['retention_groups_sha256']:
        raise ValueError('Frozen groups changed')
    for name, want in p['source_sha256'].items():
        if sha(name) != want: raise ValueError('Frozen scoring/execution implementation changed: '+name)
    prep = read(STAGE/'preparation.json')
    if sha(STAGE/'preparation.json') != p['stage_preparation_sha256']: raise ValueError('Preparation changed')
    for trial in TRIALS:
        if sha(STAGE/(trial+'.json')) != prep['trials'][trial]['spec_file_sha256']: raise ValueError('Spec changed')
    return p


def metrics(model, recipe, protocol):
    import mlx.core as mx
    from slm.backends import mlx_backend as impl
    cfg, weights = checkpoint.load(model)
    params = impl.load(cfg, weights)
    losses = []
    for row in protocol['groups']:
        x = np.asarray([row['x']],np.int32); y = np.asarray([row['y']],np.int32)
        m = np.asarray([row['assistant_mask']],np.float32)
        if x.shape != y.shape or x.shape != m.shape or not 1 <= x.shape[1] <= cfg.max_seq_len or m.sum()<16:
            raise ValueError('Frozen validation dimensions differ')
        v = float(impl.loss(params,cfg,mx.array(x),mx.array(y),mx.array(m),
            loss_implementation=recipe.loss_implementation,embedding_implementation=recipe.embedding_implementation))
        if not np.isfinite(v): raise ValueError('Nonfinite assistant loss')
        losses.append(v)
    del params
    mx.clear_cache()
    retained = retention_score(cfg,weights,protocol['retention_groups'],recipe)
    return dict(assistant_mean_nll=float(np.mean(losses)),assistant_group_nll=losses,retention=retained)


def baseline():
    p = checked(); inp = inputs(TRIALS[0])
    try:
        value = metrics(inp.source_model, inp.recipe, p)
        inp.check(); checked()
        publish(ROOT/'baseline.json',dict(creator='Navneet Prabhakar',protocol_sha256=sha(ROOT/'protocol.json'),
            model_manifest_sha256=sha(inp.source_model/'manifest.json'),metrics=value))
        print(json.dumps(dict(status='baseline_scored',assistant_mean_nll=value['assistant_mean_nll'],
            retention_nll=value['retention']['source_balanced_foundation_nll'])),flush=True)
    finally: inp.close()


def execute(trial, continuation=False):
    p = checked()
    if not (ROOT/'baseline.json').is_file(): raise ValueError('Score baseline before any optimizer screen')
    read_score('baseline')
    prep = read(STAGE/'preparation.json'); resume=None
    if continuation:
        selected=selection()
        if selected['selected_trial'] != trial: raise ValueError('Only selected screen can continue')
        resume = selected['checkpoint']
    else:
        if (ROOT/'selection.json').exists(): raise ValueError('Selection already frozen')
        if trial == TRIALS[1]: read_score(TRIALS[0])
    result = run(read(STAGE/(trial+'.json')),read(STAGE/'origin-spec.json'),prep['source_checkpoint'],prep['source_report'],
        ROOT/'runs'/('selected-continuation' if continuation else trial),optimizer_policy=POLICY,
        reason=prep['transition_reason'],backend='mlx',device='default',resume=resume,
        max_new_updates=475 if continuation else p['rules']['screen_updates'],wall_seconds=7200.,contract_file=ROOT/'contract.json')
    print(json.dumps(dict(status=result['status'],final=result['final'],checkpoint=result['latest_checkpoint'])),flush=True)


def score_run(trial, terminal=False):
    p=checked(); inp=inputs(trial)
    try:
        name='selected-continuation' if terminal else trial
        if terminal and selection()['selected_trial'] != trial: raise ValueError('Wrong selected terminal plan')
        run_path=ROOT/'runs'/name; report=read(run_path/'report.json'); launch=read(run_path/'run.json')
        expected_step=475 if terminal else 64; expected_cursor=expected_step*4
        tokens, supervised=inp.data.counts(expected_cursor)
        expected=dict(step=expected_step,cursor=expected_cursor,tokens=tokens,supervised_tokens=supervised)
        initial=read(ROOT/(trial+'-score.json'))['training_final'] if terminal else dict(step=0,cursor=0,tokens=0,supervised_tokens=0)
        if (report['plan_hash'] != inp.identity or launch['logical_plan'] != inp.plan or report['final'] != expected
            or report['initial'] != initial or report['status'] != ('update_target_reached' if terminal else 'invocation_update_limit')
            or report['experiment_contract_sha256'] != sha(ROOT/'contract.json')
            or sha(run_path/'events.jsonl') != report['events_sha256']):
            raise ValueError('Complete exact-exposure report required')
        events=[json.loads(x) for x in (run_path/'events.jsonl').read_text().splitlines()]
        if [e['step'] for e in events] != list(range(initial['step']+1,expected_step+1)): raise ValueError('Update coverage differs')
        latest=Path(report['latest_checkpoint'])
        if latest.resolve().parent != (run_path/'checkpoints').resolve() or sha(latest/'manifest.json') != report['latest_manifest_sha256']:
            raise ValueError('Run checkpoint binding differs')
        _, state=verify_checkpoint(latest,inp)
        if any(state[k] != v for k,v in expected.items()): raise ValueError('Checkpoint counters differ')
        ledger=ExposureLedger(ROOT/'contract.json',inp,'mlx','default')
        try:
            if (inp.identity,sha(latest/'manifest.json')) not in ledger.checkpoints: raise ValueError('Unrecorded checkpoint')
            charged=dict(positions=ledger.positions,updates=ledger.updates,max_group_passes=max(ledger.groups.values()))
        finally: ledger.close()
        value=metrics(latest/'state/model',inp.recipe,p)
        inp.check(); checked()
        result=dict(creator='Navneet Prabhakar',trial=trial,plan_hash=inp.identity,training_final=expected,
            protocol_sha256=sha(ROOT/'protocol.json'),run_report_sha256=sha(run_path/'report.json'),
            checkpoint=str(latest),checkpoint_manifest_sha256=sha(latest/'manifest.json'),
            metrics=value,physical_exposure=charged,conversation_assessment_pending=True,production_accepted=False)
        if terminal:
            result['paired_diagnostic']=paired(read_score('baseline')['metrics']['assistant_group_nll'],value['assistant_group_nll'],p['rules'])
        publish(ROOT/('terminal-score.json' if terminal else trial+'-score.json'),result)
        print(json.dumps(dict(status='scored',trial=trial,assistant_mean_nll=value['assistant_mean_nll'],
            retention_nll=value['retention']['source_balanced_foundation_nll'],physical=charged)),flush=True)
    finally: inp.close()


def read_score(name):
    result=read(ROOT/(name+'.json' if name=='baseline' else name+'-score.json'))
    if result['protocol_sha256'] != sha(ROOT/'protocol.json'): raise ValueError('Score protocol differs')
    if name=='baseline':
        prep=read(STAGE/'preparation.json')
        if result['model_manifest_sha256'] != sha(Path(prep['source_checkpoint'])/'state/model/manifest.json'):
            raise ValueError('Baseline model changed')
    else:
        report=ROOT/'runs'/name/'report.json'; r=read(report)
        if result['run_report_sha256'] != sha(report) or result['checkpoint_manifest_sha256'] != r['latest_manifest_sha256'] or sha(Path(result['checkpoint'])/'manifest.json') != result['checkpoint_manifest_sha256']:
            raise ValueError('Score checkpoint/report changed')
    return result


def selection():
    p=checked(); base=read_score('baseline'); scores={t:read_score(t) for t in TRIALS}
    trial=choose({t:s['metrics'] for t,s in scores.items()},base['metrics'],p['rules'])
    result=dict(creator='Navneet Prabhakar',protocol_sha256=sha(ROOT/'protocol.json'),
        score_sha256={t:sha(ROOT/(t+'-score.json')) for t in TRIALS},baseline_sha256=sha(ROOT/'baseline.json'),
        selected_trial=trial,checkpoint=scores[trial]['checkpoint'] if trial else None,
        checkpoint_manifest_sha256=scores[trial]['checkpoint_manifest_sha256'] if trial else None,
        continuation_authorized=trial is not None,production_accepted=False)
    path=ROOT/'selection.json'
    if path.exists():
        if read(path) != result: raise ValueError('Frozen optimizer choice changed')
    else: publish(path,result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['freeze','baseline','train','score','select','continue','terminal'])
    parser.add_argument('--trial',choices=TRIALS)
    a=parser.parse_args()
    if a.action=='freeze': freeze(); return
    with (ROOT/'orchestrator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='baseline': baseline()
        elif a.action=='select': print(json.dumps(selection(),indent=2))
        elif a.action in ('train','continue'):
            trial=a.trial or (selection()['selected_trial'] if a.action=='continue' else None)
            if trial is None: raise ValueError('Explicit or eligible selected trial required')
            execute(trial,a.action=='continue')
        else:
            trial=a.trial or selection()['selected_trial']
            if trial is None: raise ValueError('Explicit or selected trial required')
            score_run(trial,a.action=='terminal')


if __name__=='__main__': main()
