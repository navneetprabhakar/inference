"""Freeze a bounded replay-dominant experiment; preparation never launches training."""
import copy
import json
from pathlib import Path

from own_base_language_streams import AdmittedStreams, pinned, sha
from own_base_language_data import validation_manifest
from own_base_language_continue import REQUIRED_CODE, validate_launch

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports/broad-language-20m-v1'
RUN=ROOT/'runs/own-base-broad-language-20m-01'


def pin(p):return dict(path=str(p.resolve()),sha256=sha(p))


def write(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    assert not OUT.exists() and not RUN.exists() and not (ROOT/'runs/STOP').exists()
    old=ROOT/'reports/own-language-300m-v1/activation.json'
    assert sha(old)=='2bfdac38bb468f57d9bdb946d51d8ef2d1c744c3aebeb781c9e1819c2570711c'
    spec=json.loads(old.read_text())
    # Preserve the original pre-mixture own parent and its complete optimizer state.
    # The failed 100M endpoint is retained as evidence, not promoted as a parent.
    broad=ROOT/'data/broad-replay-v1'
    descriptor=dict(name='broad',passes=1,manifest=pin(broad/'language-manifest.json'),
                    verification=pin(broad/'language-manifest-verification.json'),
                    admission=pin(broad/'language-admission.json'))
    sources=[descriptor]+[dict(d,passes=1) for d in spec['sources']]
    windows=[];held=[]
    for d in sources:
        m=pinned(d['manifest']);selection=pinned(pin(Path(d['manifest']['path']).parent/'language-validation-selection.json'))
        windows+=selection['windows'];held += [dict(x,source=d['name']) for x in m['documents'] if x['split']=='validation']
    validation=validation_manifest(held,windows,512)
    OUT.mkdir()
    write(OUT/'validation-selection.json',dict(windows=windows,manifest=validation))
    milestones=[0,1220*8192,2441*8192]
    protocol=copy.deepcopy(pinned(spec['external_milestone_gate']['protocol']))
    protocol['planned_events']=3
    protocol['budgets']={k:3*protocol['worst_case'][k] for k in ('attempted_targets','input_positions','attention_elements')}
    protocol['budgets'].update(active_seconds=2700,calendar_seconds=3*86400)
    protocol['stop_paths']=sorted(set(protocol['stop_paths']+[str(RUN/'STOP')]))
    write(OUT/'external-protocol.json',protocol)
    spec.update(state='prepared_pending_root_review',run=str(RUN),seed=20261109,sources=sources,
                row_source_cycle=['broad']*12+['explanatory']*3+['narrative'],
                validation_selection=pin(OUT/'validation-selection.json'),training_goal=milestones[-1],
                attempted_targets=milestones[-1]+512*8192,evaluation_targets=5*validation['evaluation_targets'],
                evaluation_milestones=milestones,active_seconds=8*3600,calendar_seconds=3*86400,
                stop_paths=sorted(set(spec['stop_paths']+[str(RUN/'STOP')])),
                external_milestone_gate=dict(milestones=milestones,protocol=pin(OUT/'external-protocol.json')),
                code_sha256={n:sha(ROOT/n) for n in REQUIRED_CODE|{'prepare_broad_language_spec.py'}})
    validate_launch(dict(spec,state='reviewed_for_own_language_continuation'),RUN)
    data=AdmittedStreams(spec)
    exposure=data.schedule.state_at(2441)
    assert sum(x['targets'] for x in data.schedule.next_update(data.schedule.initial())[0])==8192
    write(OUT/'activation-draft.json',spec)
    write(OUT/'preflight.json',dict(state='PASS_actual_sources_and_schedule_no_training',
          draft=pin(OUT/'activation-draft.json'),source_exposure=exposure['sources'],
          training_targets=milestones[-1],validation_targets=validation['evaluation_targets'],
          model_loaded=False,training_started=False))
    write(OUT/'review-policy.json',dict(state='prospective_bounded_replay_test',
          rationale='Test whether retaining broad-language coverage avoids the failed all-synthetic mixture transfer regression; not a claim that replay is sufficient pretraining.',
          parent_choice='Original preserve-095 own-base checkpoint; do not inherit the failed 100M synthetic continuation.',
          changes=['75% broad replay,18.75% explanatory,6.25% narrative targets','New deterministic sampler seed','Earlier external gates at about10M and20M'],
          held_constant=['124M architecture','512 context','BF16 B2 accumulation8','constant6e-5 LR','complete original optimizer/RNG restoration'],
          interpretation='Mixture intervention, not an isolated ablation: sampler seed and source allocation change. Public diagnostics have possible historical exposure; final private acceptance remains separate.',
          first_gate='Stop on clear external degradation or persistent zero context-pair transfer with unusable raw completions; inspect all32 completions. Source loss alone never authorizes success.',
          endpoint='No automatic extension. Require root review of external behavior before further pretraining, SFT or scaling.',
          prior_work='Old failed campaign budgets, checkpoints and results remain intact; this is a new bounded experiment, not a retry with refunded work.'))
    print(json.dumps(dict(draft=pin(OUT/'activation-draft.json'),targets=milestones[-1],milestones=milestones)))


if __name__=='__main__':main()
