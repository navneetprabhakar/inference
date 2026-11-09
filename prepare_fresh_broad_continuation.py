"""Prepare bounded continuation from the audited 25M own-base checkpoint."""
import json
from pathlib import Path
from own_base_language_streams import AdmittedStreams, pinned, sha
from own_base_language_continue import REQUIRED_CODE, validate_launch
from own_base_language_parent import verified_language_parent
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports/fresh-broad-continuation-v1'
RUN=ROOT/'runs/own-base-fresh-broad-continuation-01'
def pin(p):return dict(path=str(p.resolve()),sha256=sha(p))
def write(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
    assert not OUT.exists() and not RUN.exists()
    spec=json.loads((ROOT/'reports/fresh-broad-language-100m-v1/activation.json').read_text())
    receipt_pin=pin(ROOT/'reports/language-handoff-25m-v1/parent-receipt.json');receipt=pinned(receipt_pin)
    cp=receipt['checkpoint'];spec['initialization'].update(path=str(Path(receipt['run'])/cp['file']),sha256=cp['sha256'])
    milestones=[0,3051*8192,6103*8192,9155*8192,12207*8192]
    protocol=pinned(spec['external_milestone_gate']['protocol'])
    protocol['planned_events']=len(milestones)
    protocol['budgets']={k:len(milestones)*protocol['worst_case'][k] for k in ('attempted_targets','input_positions','attention_elements')}
    protocol['budgets'].update(active_seconds=4500,calendar_seconds=5*86400)
    protocol['stop_paths']=sorted(set(protocol['stop_paths']+[str(RUN/'STOP')]))
    protocol['code_sha256']={n:sha(ROOT/n) for n in protocol['code_sha256']}
    OUT.mkdir();write(OUT/'external-protocol.json',protocol)
    spec.update(run=str(RUN),language_parent=receipt_pin,source_start_updates=3051,
        training_goal=milestones[-1],attempted_targets=milestones[-1]+512*8192,
        evaluation_targets=7*131072,evaluation_milestones=milestones,
        external_milestone_gate=dict(milestones=milestones,protocol=pin(OUT/'external-protocol.json')),
        stop_paths=sorted(set(spec['stop_paths']+[str(RUN/'STOP')])),
        code_sha256={n:sha(ROOT/n) for n in REQUIRED_CODE|{'prepare_fresh_broad_continuation.py'}})
    validate_launch(spec,RUN)
    data=AdmittedStreams(spec);parent=verified_language_parent(spec,data,lambda:None)
    exposure=data.schedule.state_at(12207)
    write(OUT/'review-policy.json',dict(
        state='prospective_bounded_continuation_after_correctness_audit',
        rationale='Preserve 25M learned updates and exact data/optimizer/RNG state; test longer fresh-text exposure after scoped math/device checks passed.',
        gates='Baseline must reproduce prior25M external diagnostics. At each25M inspect all32 raw samples,32 context pairs and web loss. Stop for nonfinite values, resource/STOP violations, web CE > baseline+0.15 or new behavioral regression. Persistent baseline repetition alone is not grounds for resetting learned weights. No automatic extension beyond100M additional targets.',
        interpretation='Loss improvement is not usability. No SFT or capability promotion without behavioral review; private conversation/tool acceptance remains required.',
        resource_budget='30 active hours,5 calendar days,4hour leases;124M local model;zero paid compute;one source pass maximum.',
        baseline_ce=4.395407707430422,baseline_context_correct=2,baseline_repetitive=32))
    write(OUT/'preflight.json',dict(state='PASS_verified_parent_and_full_schedule_no_training',
        parent_step=parent['step'],inherited_targets=parent['trained_tokens'],additional_targets=milestones[-1],
        total_fresh_targets=parent['trained_tokens']+milestones[-1],source_exposure=exposure['sources'],training_started=False))
    write(OUT/'activation.json',spec)
    print(json.dumps(pin(OUT/'activation.json')))
if __name__=='__main__':main()
