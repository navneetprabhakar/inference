"""Explicit foundation-weight import into a separately bound finite SFT stage."""
# Creator: Navneet Prabhakar
import argparse
import json
import os
from pathlib import Path
import time
import numpy as np
from slm.common import checkpoint
from slm.common.training import Trainer
from slm.data.schema import digest
from slm.data.tokenized import sha, stamp
from slm.data.curriculum import CurriculumBatches
from slm.eval.portability import environment, memory_snapshot
from slm.train import (Inputs, resolve_paths, read, write, leaves, verify_checkpoint,
                       save_checkpoint, synchronize, integer)


POLICY = 'fresh-adamw-stage-v1'
COUNTERS = ('step', 'cursor', 'tokens', 'supervised_tokens')


class StageInputs(Inputs):
    def __init__(self, spec, origin_spec, origin_checkpoint, origin_report, optimizer_policy, reason):
        if optimizer_policy != POLICY or not isinstance(reason, str) or not reason.strip():
            raise ValueError('Explicit fresh-AdamW policy and nonempty reason required; no implicit reset')
        super().__init__(spec)
        origin = None
        try:
            if isinstance(self.data, CurriculumBatches) or any(p.manifest['objective'] != 'sft' for p in leaves(self.data)):
                raise ValueError('New stage requires separately reviewed SFT data, without curriculum')
            origin = Inputs(origin_spec)
            if isinstance(origin.data, CurriculumBatches) or any(p.manifest['objective'] != 'foundation' for p in leaves(origin.data)):
                raise ValueError('Origin must be a verified foundation plan')
            root = Path(origin_checkpoint).resolve()
            _, state = verify_checkpoint(root, origin)
            report_file = Path(origin_report).resolve()
            report = read(report_file)
            final = {k: state[k] for k in COUNTERS}
            if (report.get('status') not in ('data_exhausted_before_target', 'update_target_reached')
                    or report['plan_hash'] != origin.identity or report['final'] != final
                    or state['step'] <= 0 or state['tokens'] <= 0
                    or report['latest_manifest_sha256'] != sha(root/'manifest.json')
                    or Path(report['latest_checkpoint']).name != root.name):
                raise ValueError('Verified terminal foundation checkpoint/report required')
            events = report_file.with_name('events.jsonl')
            logged = [json.loads(v) for v in events.read_text().splitlines()]
            if (sha(events) != report['events_sha256']
                    or [r['step'] for r in logged] != list(range(report['initial']['step']+1, state['step']+1))):
                raise ValueError('Origin terminal event coverage differs')
            if self.config != origin.config or self.data.tokenizer_hash != origin.data.tokenizer_hash:
                raise ValueError('Transition must preserve exact model configuration and tokenizer')
            if any(getattr(self.recipe, k) != getattr(origin.recipe, k)
                   for k in ('loss_implementation', 'embedding_implementation')):
                raise ValueError('Transition v1 preserves numerical implementation conventions')
            self.origin = dict(kind='foundation-weights-to-sft-v1', optimizer_policy=POLICY,
                reason=reason.strip(), source_plan_hash=origin.identity,
                source_checkpoint_sha256=sha(root/'manifest.json'),
                source_state_sha256=sha(root/'state/manifest.json'),
                source_model_sha256=sha(root/'state/model/manifest.json'),
                source_terminal_report_sha256=sha(report_file), source_final=final,
                new_stage_counters={k: 0 for k in COUNTERS},
                exposure_scope='Prior logical chain plus separate new-stage counters; prior discarded/replay work is not inferred.')
            self.source_model = root/'state/model'
            origin.pin_tree(root)
            self.guards.update(origin.guards)
            self.guards[report_file] = stamp(report_file)
            self.guards[events] = stamp(events)
            self.plan['initialization'] = self.origin
            self.plan['reference_sources']['stage_transition.py'] = sha(__file__)
            self.guards[Path(__file__).resolve()] = stamp(__file__)
            self.identity = digest(self.plan)
            self.check()
        except BaseException:
            self.close()
            raise
        finally:
            if origin is not None:
                origin.close()


def run(spec, origin_spec, origin_checkpoint, origin_report, output, *, optimizer_policy,
        reason, backend='torch', device='cpu', resume=None, initialize_only=False,
        max_new_updates=1000000, wall_seconds=3600.):
    integer(max_new_updates)
    if type(initialize_only) is not bool:
        raise ValueError('Explicit initialization-only boolean required')
    if type(wall_seconds) not in (int, float) or not np.isfinite(wall_seconds) or wall_seconds <= 0:
        raise ValueError('Positive finite soft wall limit required')
    if (backend not in ('mlx', 'torch') or (backend == 'mlx' and device != 'default')
            or (backend == 'torch' and device != 'cpu' and not device.startswith('cuda'))):
        raise ValueError('Explicit backend/device required; no fallback')
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    spec = resolve_paths(spec, Path.cwd())
    origin_spec = resolve_paths(origin_spec, Path.cwd())
    started = time.perf_counter()
    inputs = StageInputs(spec, origin_spec, origin_checkpoint, origin_report, optimizer_policy, reason)
    events = latest = None
    created = False
    try:
        if inputs.research_limits and device.startswith('cuda'):
            raise ValueError('Research scope does not authorize CUDA')
        for path in inputs.guards:
            if path == output or output in path.parents or (path.is_dir() and path in output.parents):
                raise ValueError('Output overlaps immutable transition inputs')
        initial = {k: 0 for k in COUNTERS}
        if resume is not None:
            resume = Path(resume).resolve()
            if output == resume or output in resume.parents or resume in output.parents:
                raise ValueError('Output overlaps resume checkpoint')
            inputs.pin_tree(resume)
            _, state = verify_checkpoint(resume, inputs)
            initial = {k: state[k] for k in COUNTERS}
        if initial['step'] > spec['limits']['updates'] or initial['tokens'] > spec['limits']['processed_positions']:
            raise ValueError('Resume exceeds new-stage ceilings')
        env = environment(backend, device)
        inputs.check()
        output.mkdir(parents=True)
        created = True
        write(output/'run.json', dict(version=1, spec=spec, origin_spec=origin_spec,
            logical_plan=inputs.plan, plan_hash=inputs.identity, backend=backend, device=device,
            environment=env, initialize_only=initialize_only,
            resume_manifest_sha256=sha(resume/'manifest.json') if resume is not None else None,
            scope='Explicit new SFT stage; fresh optimizer only on first import, same-stage resume preserves it.'))
        events = (output/'events.jsonl').open('x')
        if resume is None:
            cfg, weights = checkpoint.load(inputs.source_model)
            trainer = Trainer(cfg, weights, inputs.data, backend, device, inputs.recipe, inputs.data.tokenizer_hash)
            if trainer.moments or any(getattr(trainer, k) for k in COUNTERS):
                raise ValueError('Declared fresh optimizer/counters not honored')
            exported = trainer.impl.export(trainer.params)
            if any(not np.array_equal(exported[k].view(np.uint32), value.view(np.uint32))
                   for k, value in weights.items()):
                raise ValueError('Imported weights changed at stage initialization')
            del weights, exported
        else:
            trainer = Trainer.resume(resume/'state', inputs.data, backend, device, inputs.data.tokenizer_hash)
        synchronize(backend, device)
        updates = 0
        while True:
            inputs.check()
            if initialize_only:
                status = 'initialized_only'
                break
            if trainer.step >= spec['limits']['updates']:
                status = 'update_target_reached'
                break
            if trainer.cursor >= len(inputs.data):
                status = 'data_exhausted_before_target'
                break
            if updates >= max_new_updates:
                status = 'invocation_update_limit'
                break
            if time.perf_counter()-started >= wall_seconds:
                status = 'soft_wall_limit'
                break
            _, end = trainer._update_context()
            if inputs.data.counts(end)[0] > spec['limits']['processed_positions']:
                status = 'position_ceiling_before_next_atomic_update'
                break
            tick = time.perf_counter()
            result = trainer.update()
            synchronize(backend, device)
            events.write(json.dumps(dict(event='update', seconds=time.perf_counter()-tick, **result), allow_nan=False)+'\n')
            events.flush()
            os.fsync(events.fileno())
            updates += 1
            if trainer.step % spec['checkpoint']['every_updates'] == 0:
                latest = save_checkpoint(output, trainer, inputs, {})
        latest = save_checkpoint(output, trainer, inputs, {})
        inputs.check()
        final = {k: getattr(trainer, k) for k in COUNTERS}
        result = dict(version=1, creator='Navneet Prabhakar', status=status, plan_hash=inputs.identity,
            initialization=inputs.origin, initial=initial, final=final,
            executed_this_invocation=dict(updates=updates, processed_positions=final['tokens']-initial['tokens'],
                                          supervised_positions=final['supervised_tokens']-initial['supervised_tokens']),
            cumulative_logical_processed_positions=inputs.origin['source_final']['tokens']+final['tokens'],
            cumulative_logical_supervised_positions=inputs.origin['source_final']['supervised_tokens']+final['supervised_tokens'],
            latest_checkpoint=str(latest), latest_manifest_sha256=sha(latest/'manifest.json'),
            events_sha256=sha(output/'events.jsonl'), total_seconds=time.perf_counter()-started,
            memory=memory_snapshot(backend, device), production_accepted=False, language_capability_proved=False,
            scope='Separate finite SFT stage; not full-state portability or quality acceptance. Prior physical discarded/replay work excluded from logical totals.')
        write(output/'report.json', result)
        return result
    except BaseException as error:
        if created:
            write(output/'failure.json', dict(complete=False, error_type=type(error).__name__,
                  latest_checkpoint=str(latest) if latest is not None else None))
        raise
    finally:
        if events is not None:
            events.close()
        inputs.close()


def main():
    p = argparse.ArgumentParser()
    for name in ('spec', 'origin-spec', 'origin-checkpoint', 'origin-report', 'output', 'optimizer-policy', 'reason'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--backend', choices=('torch', 'mlx'), default='torch')
    p.add_argument('--device', default='cpu')
    p.add_argument('--resume')
    p.add_argument('--initialize-only', action='store_true')
    p.add_argument('--max-new-updates', type=int, default=1000000)
    p.add_argument('--wall-seconds', type=float, default=3600.)
    a = p.parse_args()
    spec = resolve_paths(read(a.spec), Path(a.spec).resolve().parent)
    origin_spec = resolve_paths(read(a.origin_spec), Path(a.origin_spec).resolve().parent)
    result = run(spec, origin_spec, a.origin_checkpoint, a.origin_report, a.output,
        optimizer_policy=a.optimizer_policy, reason=a.reason, backend=a.backend, device=a.device,
        resume=a.resume, initialize_only=a.initialize_only, max_new_updates=a.max_new_updates, wall_seconds=a.wall_seconds)
    print(json.dumps({k: result[k] for k in ('status', 'initial', 'final', 'latest_checkpoint')}, indent=2))


if __name__ == '__main__':
    main()
