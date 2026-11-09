"""Freeze a bounded fresh-text experiment; preparation never launches training."""
import copy
import json
from pathlib import Path

from own_base_language_streams import AdmittedStreams, pinned, sha
from own_base_language_data import validation_manifest
from own_base_language_continue import REQUIRED_CODE, validate_launch

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports/fresh-broad-language-100m-v1'
RUN=ROOT/'runs/own-base-fresh-broad-language-100m-01'


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
    broad=ROOT/'data/fresh-broad-packed-v1'
    descriptor=dict(name='fresh_broad',passes=1,manifest=pin(broad/'language-manifest.json'),
                    verification=pin(broad/'language-manifest-verification.json'),
                    admission=pin(broad/'language-admission.json'))
    sources=[descriptor]
    windows=[];held=[]
    for d in sources:
        m=pinned(d['manifest']);selection=pinned(pin(Path(d['manifest']['path']).parent/'language-validation-selection.json'))
        windows+=selection['windows'];held += [dict(x,source=d['name']) for x in m['documents'] if x['split']=='validation']
    validation=validation_manifest(held,windows,512)
    OUT.mkdir()
    write(OUT/'validation-selection.json',dict(windows=windows,manifest=validation))
    milestones=[0,3051*8192,6103*8192,12207*8192]
    protocol=copy.deepcopy(pinned(spec['external_milestone_gate']['protocol']))
    protocol['planned_events']=4
    protocol['budgets']={k:4*protocol['worst_case'][k] for k in ('attempted_targets','input_positions','attention_elements')}
    protocol['budgets'].update(active_seconds=3600,calendar_seconds=5*86400)
    protocol['stop_paths']=sorted(set(protocol['stop_paths']+[str(RUN/'STOP')]))
    write(OUT/'external-protocol.json',protocol)
    spec.update(state='prepared_pending_root_review',run=str(RUN),seed=20261109,sources=sources,
                row_source_cycle=['fresh_broad']*16,
                validation_selection=pin(OUT/'validation-selection.json'),training_goal=milestones[-1],
                attempted_targets=milestones[-1]+512*8192,evaluation_targets=6*validation['evaluation_targets'],
                evaluation_milestones=milestones,active_seconds=30*3600,calendar_seconds=5*86400,
                stop_paths=sorted(set(spec['stop_paths']+[str(RUN/'STOP')])),
                external_milestone_gate=dict(milestones=milestones,protocol=pin(OUT/'external-protocol.json')),
                code_sha256={n:sha(ROOT/n) for n in REQUIRED_CODE|{'prepare_fresh_broad_language_spec.py'}})
    validate_launch(dict(spec,state='reviewed_for_own_language_continuation'),RUN)
    data=AdmittedStreams(spec)
    exposure=data.schedule.state_at(12207)
    assert sum(x['targets'] for x in data.schedule.next_update(data.schedule.initial())[0])==8192
    write(OUT/'activation-draft.json',spec)
    write(OUT/'preflight.json',dict(state='PASS_actual_sources_and_schedule_no_training',
          draft=pin(OUT/'activation-draft.json'),source_exposure=exposure['sources'],
          training_targets=milestones[-1],validation_targets=validation['evaluation_targets'],
          model_loaded=False,training_started=False))
    write(OUT/'review-policy.json',dict(state='prospective_bounded_fresh_text_test',
          rationale='Train on 100M fresh broad-language targets after quality and custody filtering; avoid another synthetic-dominant continuation or repeated old-web replay.',
          parent_choice='Original preserve-095 own-base checkpoint. This creates a comparable branch from the same verified parent as the prior two experiments. The weakly improved 20M replay endpoint is preserved, but not inherited; this costs its 20M updates and avoids an untested parent adapter.',
          changes=['100% fresh score>=4 broad text','100M finite target budget with gates at baseline,25M,50M,100M','One source pass maximum'],
          held_constant=['124M architecture','512 context','BF16 B2 accumulation8','constant6e-5 LR','complete original optimizer/RNG restoration'],
          interpretation='Fresh-data intervention, not an isolated quality-threshold ablation. Prior public exposure remains possible; final private acceptance is separate.',
          gates='Review external web loss, context-pair results and all32 raw continuations together. Stop on material external regression or clear collapse; source loss alone never authorizes success. Modest improvement is not usable conversation.',
          endpoint='No automatic extension, SFT or parameter growth. Require behavioral review. This finite budget does not promise usable conversation.',
          resource_budget='30 active hours,5 calendar days, existing4-hour lease/resource/STOP safeguards. No paid compute.'))
    print(json.dumps(dict(draft=pin(OUT/'activation-draft.json'),targets=milestones[-1],milestones=milestones)))


if __name__=='__main__':main()
