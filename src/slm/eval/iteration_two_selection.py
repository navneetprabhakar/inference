"""Choose only from complete frozen screens and bind the exact resume state."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.iteration_two import choose,summarize
from slm.eval import iteration_two_results


def checked_checkpoint(path,expected):
    """Recheck every byte beneath the checkpoint identity scored earlier."""
    path=Path(path)
    if sha(path/'manifest.json')!=expected:raise ValueError('Scored checkpoint identity differs')
    outer=json.loads((path/'manifest.json').read_text())
    if set(outer)!={'binding.json','state/manifest.json'}:raise ValueError('Checkpoint wrapper differs')
    for name,want in outer.items():
        if sha(path/name)!=want:raise ValueError('Scored checkpoint wrapper differs')
    state=json.loads((path/'state/manifest.json').read_text())
    if set(state)!={'model/config.json','model/model.safetensors','model/manifest.json','optimizer.safetensors','state.json'}:raise ValueError('Scored training state inventory differs')
    for name,want in state.items():
        if sha(path/'state'/name)!=want:raise ValueError('Scored checkpoint payload differs')


def select_from_results(root,freeze_file,score_files):
    root=Path(root);freeze_file=Path(freeze_file)
    protocol=json.loads((root/'protocol.json').read_text());freeze=json.loads(freeze_file.read_text())
    if sha(root/'protocol.json')!=freeze['protocol_sha256'] or digest(protocol['groups'])!=protocol['groups_sha256']:
        raise ValueError('Frozen optimizer protocol differs')
    for path,want in protocol['source_sha256'].items():
        if sha(path)!=want:raise ValueError('Frozen experiment implementation differs')
    if set(score_files)!=set(protocol['specs']):raise ValueError('Both frozen screen scores required')
    metrics={};bindings={};expected=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144)
    for trial,file in sorted(score_files.items()):
        file=Path(file);score=json.loads(file.read_text());run=root/'runs'/trial;report=json.loads((run/'report.json').read_text())
        launch=json.loads((run/'run.json').read_text())
        spec_path=root/(trial+'.json')
        if (sha(spec_path)!=protocol['specs'][trial]['spec_file_sha256'] or score['trial']!=trial
            or score['protocol_sha256']!=sha(root/'protocol.json') or score['plan_hash']!=protocol['plan_hashes'][trial]
            or score['training_final']!=expected or report['final']!=expected or report['status']!='invocation_update_limit'
            or report['initial']!=dict(step=0,cursor=0,tokens=0,supervised_tokens=0)
            or launch['resume_manifest_sha256'] is not None or launch['plan_hash']!=score['plan_hash']
            or score['scorer_sha256']!=sha(iteration_two_results.__file__) or score['run_report_sha256']!=sha(run/'report.json')
            or report['plan_hash']!=score['plan_hash'] or score['checkpoint_manifest_sha256']!=report['latest_manifest_sha256']
            or sha(run/'events.jsonl')!=report['events_sha256']):raise ValueError('Complete unchanged scored screen required')
        latest=Path(report['latest_checkpoint']).resolve()
        if latest.parent!=(run/'checkpoints').resolve():raise ValueError('Scored checkpoint outside screen')
        checked_checkpoint(latest,score['checkpoint_manifest_sha256'])
        rebuilt=summarize(protocol['groups'],score['metrics']['foundation_group_nll'],score['metrics']['assistant_group_nll'])
        if rebuilt!=score['metrics']:raise ValueError('Cached screen metric aggregation differs')
        metrics[trial]=rebuilt
        bindings[trial]=dict(score_file=str(file.resolve()),score_sha256=sha(file),checkpoint=str(latest),
            checkpoint_manifest_sha256=score['checkpoint_manifest_sha256'],plan_hash=score['plan_hash'],
            source_balanced_foundation_nll=rebuilt['source_balanced_foundation_nll'],
            source_balanced_assistant_nll=rebuilt['source_balanced_assistant_nll'])
    winner=choose(metrics);selected=bindings[winner]
    exposure=protocol['exposure'];planned=exposure['planned_selected_chain_positions']
    if planned+262144>exposure['cumulative_physical_position_ceiling']:raise ValueError('Cumulative optimizer budget exceeded')
    return dict(creator='Navneet Prabhakar',version=1,selected_trial=winner,selected=selected,screens=bindings,
        protocol_sha256=sha(root/'protocol.json'),freeze_file_sha256=sha(freeze_file),selection_code_sha256=sha(__file__),
        selection_rule=protocol['optimizer_choice'],physical_positions_already_executed=524288,
        continuation_reserved_positions=planned-262144,maximum_physical_positions_after_continuation=planned+262144,
        production_accepted=False,scope='Predeclared optimizer choice from two complete scored screens; continue only the selected unchanged chain. No conversation acceptance or new data admission.')
