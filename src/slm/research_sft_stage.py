"""Bounded research SFT transition and experiment-wide conservative exposure ledger."""
# Creator: Navneet Prabhakar
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict, fields
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
import numpy as np

from slm.common import checkpoint
from slm.common.config import Config
from slm.common.training import Trainer, Recipe
from slm.common.tokenizer import BPE
from slm.data.curriculum import CurriculumBatches
from slm.data.mixture import MixtureBatches
from slm.data.schema import digest
from slm.data.sft_research import open_research
from slm.data.tokenized import sha, stamp
from slm.eval.portability import environment, memory_snapshot
from slm.stage_transition import POLICY, COUNTERS
from slm.train import (Inputs, open_data, resolve_paths, read, write, leaves, verify_leaf,
                       verify_checkpoint, save_checkpoint, synchronize, integer)


class ResearchStageInputs(Inputs):
    def __init__(self, spec, origin_spec, origin_checkpoint, origin_report, optimizer_policy, reason):
        self.stack = ExitStack()
        self.guards = {}
        origin = None
        try:
            required = {'version','config','recipe','seed','tokenizer','data','releases','limits','checkpoint','scope','policy_file_sha256'}
            if (set(spec) != required or type(spec['version']) is not int or spec['version'] != 2
                    or spec['scope'] != 'language_pilot' or optimizer_policy != POLICY
                    or not isinstance(reason, str) or not reason.strip()):
                raise ValueError('Explicit research SFT v2 spec and fresh-optimizer declaration required')
            if set(spec['recipe']) != {f.name for f in fields(Recipe)}:
                raise ValueError('Complete explicit recipe required')
            if any(type(spec['recipe'][k]) not in (int, float) for k in ('lr','beta1','beta2','eps','decay','clip')):
                raise ValueError('Numeric recipe settings required')
            self.config = Config(**spec['config'])
            self.recipe = Recipe(**spec['recipe'])
            integer(spec['seed'], 0, 2**32-1)
            if set(spec['limits']) != {'updates', 'processed_positions'} or set(spec['checkpoint']) != {'every_updates','keep'}:
                raise ValueError('Explicit limits and checkpoint retention required')
            for value in spec['limits'].values(): integer(value)
            integer(spec['checkpoint']['every_updates'])
            integer(spec['checkpoint']['keep'], 2, 100)
            if spec['data']['kind'] not in ('tokens', 'mixture'):
                raise ValueError('Research SFT supports tokens or a finite single-component mixture only')
            self.data = self.stack.enter_context(open_data(spec['data'], spec['tokenizer']))
            parts = leaves(self.data)
            if len(parts) != 1 or len(spec['releases']) != 1:
                raise ValueError('Exactly one bounded research release and token component required')
            part = parts[0]
            if (part.manifest['objective'] != 'sft' or part.manifest.get('research_policy_file_sha256') != spec['policy_file_sha256']
                    or self.data.vocab_size != self.config.vocab_size or self.data.max_length > self.config.max_seq_len):
                raise ValueError('SFT objective/policy/vocabulary/context mismatch')
            fingerprint = part.manifest['release_manifest_sha256']
            if set(spec['releases']) != {fingerprint}:
                raise ValueError('Exact research release binding required')
            root = Path(spec['releases'][fingerprint])
            if sha(root/'manifest.json') != fingerprint:
                raise ValueError('Research release fingerprint differs')
            admitted = self.stack.enter_context(open_research(root, spec['policy_file_sha256']))
            self.research_limits = admitted.research_limits
            self.policy_hash = spec['policy_file_sha256']
            self.allowed_devices = read(root/'research-policy.json')['allowed_training_devices']
            caps = self.research_limits
            if (self.config.parameter_count > caps['max_parameters'] or part.max_length > caps['max_context']
                    or part.manifest['context_length'] > caps['max_context']
                    or spec['limits']['updates'] > caps['optimizer_updates']
                    or spec['limits']['processed_positions'] > caps['physical_data_positions']
                    or self.data.counts(len(self.data))[0] > caps['physical_data_positions']):
                raise ValueError('Research model/context/update/position limits exceeded')
            bpe = BPE.load(spec['tokenizer'])
            verify_leaf(part, admitted, bpe)
            lineage = [json.loads(line) for line in (part.path/'lineage.jsonl').read_text().splitlines()]
            scheduled = ([int(r['batch']) for r in self.data.index] if isinstance(self.data, MixtureBatches)
                         else list(range(len(part))))
            self.scheduled_groups = [lineage[i]['split_group'] for i in scheduled]
            if max(Counter(self.scheduled_groups).values()) > caps['max_physical_passes_per_group']:
                raise ValueError('Scheduled group repeats exceed policy')
            self.pin_tree(root)
            self.pin_tree(Path(spec['tokenizer']))
            self.pin_tree(self.data.path)
            self.pin_tree(part.path)
            origin = Inputs(origin_spec)
            if isinstance(origin.data, CurriculumBatches) or any(p.manifest['objective'] != 'foundation' for p in leaves(origin.data)):
                raise ValueError('Verified foundation origin required')
            old = Path(origin_checkpoint).resolve()
            _, state = verify_checkpoint(old, origin)
            report_path = Path(origin_report).resolve()
            report = read(report_path)
            final = {k: state[k] for k in COUNTERS}
            if (report.get('status') not in ('data_exhausted_before_target','update_target_reached')
                    or report['plan_hash'] != origin.identity or report['final'] != final
                    or state['step'] <= 0 or state['tokens'] <= 0
                    or report['latest_manifest_sha256'] != sha(old/'manifest.json')
                    or Path(report['latest_checkpoint']).resolve() != old):
                raise ValueError('Exact terminal foundation checkpoint/report required')
            events = report_path.with_name('events.jsonl')
            logged = [json.loads(line) for line in events.read_text().splitlines()]
            if sha(events) != report['events_sha256'] or [r['step'] for r in logged] != list(range(report['initial']['step']+1, state['step']+1)):
                raise ValueError('Origin terminal event coverage differs')
            if self.config != origin.config or self.data.tokenizer_hash != origin.data.tokenizer_hash:
                raise ValueError('Exact architecture/tokenizer preservation required')
            if any(getattr(self.recipe, k) != getattr(origin.recipe, k) for k in ('loss_implementation','embedding_implementation')):
                raise ValueError('Preserve origin numerical implementation conventions')
            self.origin = dict(kind='foundation-weights-to-research-sft-v1', optimizer_policy=POLICY, reason=reason.strip(),
                source_plan_hash=origin.identity, source_checkpoint_sha256=sha(old/'manifest.json'),
                source_state_sha256=sha(old/'state/manifest.json'), source_model_sha256=sha(old/'state/model/manifest.json'),
                source_terminal_report_sha256=sha(report_path), source_final=final, new_stage_counters={k: 0 for k in COUNTERS})
            self.source_model = old/'state/model'
            origin.pin_tree(old)
            self.guards.update(origin.guards)
            for p in (report_path, events): self.guards[p] = stamp(p)
            sources = dict(origin.plan['reference_sources'])
            for name in ('research_sft_stage.py','stage_transition.py','data/sft_research.py','data/sft_research_tokens.py',
                         'data/oasst_sft_screen.py','data/holdout.py','eval/cases.py','sft_research_preflight.py'):
                path = Path(__file__).parent/name
                sources[name] = sha(path)
                self.guards[path.resolve()] = stamp(path)
            self.plan = dict(version=2, config=self.config.to_dict(), recipe=asdict(self.recipe), seed=spec['seed'],
                initialization=self.origin, tokenizer_hash=self.data.tokenizer_hash, data_hash=self.data.fingerprint,
                data_kind=spec['data']['kind'], release_hashes=[fingerprint], limits=spec['limits'], checkpoint=spec['checkpoint'],
                scope='bounded_research_sft', research_policy_file_sha256=self.policy_hash, reference_sources=sources)
            self.identity = digest(self.plan)
            self.check()
        except BaseException:
            self.close()
            raise
        finally:
            if origin is not None: origin.close()


class ExposureLedger:
    """One frozen experiment, exclusive writer; uncertain reservations remain charged."""
    def __init__(self, contract_file, inputs, backend='torch', device='cpu', *, verify_device=True):
        self.file = Path(contract_file).resolve()
        self.contract_hash = sha(self.file)
        c = read(self.file)
        required = {'version','kind','policy_file_sha256','plans','limits','preflight','assessment','execution_root'}
        if (set(c) != required or type(c['version']) is not int or c['version'] != 1 or c['kind'] != 'bounded-research-sft-experiment-v1'
                or c['policy_file_sha256'] != inputs.policy_hash or inputs.identity not in c['plans']
                or not c['plans'] or len(c['plans']) != len(set(c['plans']))):
            raise ValueError('Frozen experiment must authorize this exact plan/policy')
        caps = inputs.research_limits
        expected = {'physical_data_positions','optimizer_updates','max_physical_passes_per_group'}
        if set(c['limits']) != expected or any(type(v) is not int or not 1 <= v <= caps[k] for k,v in c['limits'].items()):
            raise ValueError('Experiment-wide limits exceed policy')
        self.limits = c['limits']
        if set(c['preflight']) != set(c['plans']):
            raise ValueError('Every frozen plan needs its own preflight')
        prerequisites = [('preflight', plan, binding) for plan, binding in c['preflight'].items()]
        prerequisites.append(('assessment', None, c['assessment']))
        synthetic_positions = 0
        for kind, plan, binding in prerequisites:
            if set(binding) != {'path','sha256'}:
                raise ValueError('Pinned preflight and assessment files required')
            path = Path(binding['path'])
            if not path.is_absolute(): path = self.file.parent/path
            if sha(path) != binding['sha256']:
                raise ValueError('Frozen prerequisite differs')
            value = read(path)
            if kind == 'preflight':
                if (value['kind'] != 'sft-full-step-resource-preflight-v1' or value['passed'] is not True
                        or value['plan_hash'] != plan
                        or (verify_device and (value['backend'] != backend or value['device'] != device))
                        or value['source_model_sha256'] != inputs.origin['source_model_sha256']
                        or (plan == inputs.identity and value['recipe'] != asdict(inputs.recipe))
                        or value['config'] != inputs.config.to_dict()
                        or value['policy_file_sha256'] != inputs.policy_hash
                        or type(value['synthetic_gradient_positions']) is not int or value['synthetic_gradient_positions'] <= 0
                        or (plan == inputs.identity and (value['maximum_sequence_length'] < inputs.data.max_length
                            or value['synthetic_gradient_positions'] < inputs.data.max_length*inputs.recipe.accumulation_steps))
                        or value['implementation_sha256'] != sha(Path(__file__).with_name('sft_research_preflight.py'))
                        or value['source_unchanged'] is not True):
                    raise ValueError('Matching successful full-step preflight required')
                synthetic_positions += value['synthetic_gradient_positions']
            elif (value['kind'] != 'sft-terminal-assessment-contract-v1'
                  or value['actual_conversation_and_direct_score_required'] is not True
                  or value['policy_file_sha256'] != inputs.policy_hash):
                raise ValueError('Frozen terminal diagnostics/conversation contract required')
            inputs.guards[path.resolve()] = stamp(path)
        if synthetic_positions > caps['synthetic_preflight_gradient_positions']:
            raise ValueError('Combined synthetic preflight work exceeds policy')
        inputs.guards[self.file] = stamp(self.file)
        self.path = self.file.parent/'execution'
        if not Path(c['execution_root']).is_absolute() or Path(c['execution_root']).resolve() != self.path:
            raise ValueError('Frozen experiment execution location differs; copying cannot reset exposure')
        try:
            self.path.mkdir()
            fresh = True
        except FileExistsError:
            fresh = False
        self.lock = (self.path/'lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.log = self.path/'physical-events.jsonl'
            self.head = self.path/'head.json'
            self.events = []
            self.positions = self.updates = 0
            self.groups = Counter()
            self.checkpoints = set()
            if not self.log.exists():
                if not fresh:
                    raise ValueError('Existing exposure directory lost its journal; no automatic reset')
                with self.log.open('x') as stream:
                    stream.flush(); os.fsync(stream.fileno())
                fd = os.open(self.path, os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
            if not self.head.exists():
                if not fresh or self.log.stat().st_size:
                    raise ValueError('Existing exposure directory lost its journal head; no automatic reset')
                write(self.head, dict(contract_sha256=self.contract_hash, events=0, tail=None))
            if self.log.exists():
                if self.log.stat().st_size > 64*1024**2:
                    raise ValueError('Exposure journal exceeds metadata bound')
                for line in self.log.read_text().splitlines():
                    event = json.loads(line)
                    previous = digest(self.events[-1]) if self.events else None
                    if event['contract_sha256'] != self.contract_hash or event['previous'] != previous:
                        raise ValueError('Exposure journal chain differs')
                    self._account(event)
                    self.events.append(event)
            head = read(self.head)
            count = head['events']
            if (head['contract_sha256'] != self.contract_hash or type(count) is not int or not 0 <= count <= len(self.events)
                    or head['tail'] != (digest(self.events[count-1]) if count else None)):
                raise ValueError('Exposure journal rollback/truncation or changed committed tail')
            # A valid durable suffix after a crash is conservatively charged, never forgotten.
            if count < len(self.events): self._save_head()
        except BaseException:
            self.lock.close()
            raise

    def _account(self, event):
        if event['kind'] == 'reserve':
            self.positions += integer(event['positions'])
            self.updates += 1
            self.groups.update(event['groups'])
            if (self.positions > self.limits['physical_data_positions'] or self.updates > self.limits['optimizer_updates']
                    or max(self.groups.values()) > self.limits['max_physical_passes_per_group']):
                raise ValueError('Global physical exposure limit exceeded; reservation not executed')
        elif event['kind'] == 'checkpoint':
            self.checkpoints.add((event['plan'], event['checkpoint_sha256']))
        else: raise ValueError('Unknown exposure event')

    def append(self, event):
        event.update(contract_sha256=self.contract_hash, previous=digest(self.events[-1]) if self.events else None)
        # Validate a copy of accounting so refused reservations cannot consume an unlogged partial state.
        before = self.positions, self.updates, self.groups.copy(), self.checkpoints.copy()
        try: self._account(event)
        except BaseException:
            self.positions, self.updates, self.groups, self.checkpoints = before
            raise
        with self.log.open('a') as stream:
            stream.write(json.dumps(event, sort_keys=True)+'\n'); stream.flush(); os.fsync(stream.fileno())
        self.events.append(event)
        self._save_head()

    def _save_head(self):
        write(self.head, dict(contract_sha256=self.contract_hash, events=len(self.events),
                             tail=digest(self.events[-1]) if self.events else None))

    def reserve(self, inputs, start, end):
        groups = inputs.scheduled_groups[start:end]
        n = inputs.data.counts(end)[0]-inputs.data.counts(start)[0]
        self.append(dict(kind='reserve', plan=inputs.identity, start=start, end=end, positions=n, groups=groups))

    def record_checkpoint(self, inputs, path):
        fingerprint = sha(Path(path)/'manifest.json')
        if (inputs.identity, fingerprint) not in self.checkpoints:
            self.append(dict(kind='checkpoint', plan=inputs.identity, checkpoint_sha256=fingerprint))

    def close(self):
        self.lock.close()

def run(spec, origin_spec, origin_checkpoint, origin_report, output, *, optimizer_policy,
        reason, backend='torch', device='cpu', resume=None, initialize_only=False,
        max_new_updates=1000000, wall_seconds=3600., contract_file=None):
    integer(max_new_updates)
    if type(initialize_only) is not bool:
        raise ValueError('Explicit initialization-only boolean required')
    if type(wall_seconds) not in (int, float) or not np.isfinite(wall_seconds) or wall_seconds <= 0:
        raise ValueError('Positive finite soft wall limit required')
    if (backend, device) not in (('mlx', 'default'), ('torch', 'cpu')):
        raise ValueError('Explicit backend/device required; no fallback')
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    spec = resolve_paths(spec, Path.cwd())
    origin_spec = resolve_paths(origin_spec, Path.cwd())
    started = time.perf_counter()
    inputs = ResearchStageInputs(spec, origin_spec, origin_checkpoint, origin_report, optimizer_policy, reason)
    events = latest = ledger = None
    created = False
    try:
        if backend+':'+device not in inputs.allowed_devices:
            raise ValueError('Research policy does not authorize this device')
        if not initialize_only and contract_file is None:
            raise ValueError('Frozen experiment/preflight/assessment contract required before any training')
        if contract_file is not None:
            ledger = ExposureLedger(contract_file, inputs, backend, device, verify_device=not initialize_only)
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
            if initial['step'] and (ledger is None or (inputs.identity, sha(resume/'manifest.json')) not in ledger.checkpoints):
                raise ValueError('Learned resume checkpoint not recorded in this experiment exposure ledger')
        if initial['step'] > spec['limits']['updates'] or initial['tokens'] > spec['limits']['processed_positions']:
            raise ValueError('Resume exceeds new-stage ceilings')
        env = environment(backend, device)
        if backend == 'mlx':
            import mlx.core as mx
            if mx.default_device() != mx.gpu:
                raise ValueError('Actual MLX GPU required; no fallback')
        inputs.check()
        output.mkdir(parents=True)
        created = True
        write(output/'run.json', dict(version=1, spec=spec, origin_spec=origin_spec,
            logical_plan=inputs.plan, plan_hash=inputs.identity, backend=backend, device=device,
            environment=env, initialize_only=initialize_only,
            experiment_contract_sha256=ledger.contract_hash if ledger else None,
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
            if trainer.step == 0:
                _, weights = checkpoint.load(inputs.source_model)
                exported = trainer.impl.export(trainer.params)
                if any(not np.array_equal(exported[k].view(np.uint32), v.view(np.uint32)) for k,v in weights.items()):
                    raise ValueError('Zero-step resume must preserve exact foundation weights')
                del weights, exported
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
            start = trainer.cursor
            if inputs.data.counts(end)[0] > spec['limits']['processed_positions']:
                status = 'position_ceiling_before_next_atomic_update'
                break
            ledger.reserve(inputs, start, end)
            tick = time.perf_counter()
            result = trainer.update()
            synchronize(backend, device)
            events.write(json.dumps(dict(event='update', seconds=time.perf_counter()-tick, **result), allow_nan=False)+'\n')
            events.flush()
            os.fsync(events.fileno())
            updates += 1
            if trainer.step % spec['checkpoint']['every_updates'] == 0:
                latest = save_checkpoint(output, trainer, inputs, {})
                ledger.record_checkpoint(inputs, latest)
        latest = save_checkpoint(output, trainer, inputs, {})
        if ledger is not None: ledger.record_checkpoint(inputs, latest)
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
            experiment_contract_sha256=ledger.contract_hash if ledger else None,
            conservatively_charged_physical_positions=ledger.positions if ledger else 0,
            conservatively_charged_updates=ledger.updates if ledger else 0,
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
        try: inputs.close()
        finally:
            if ledger is not None: ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('spec','origin-spec','origin-checkpoint','origin-report','output','optimizer-policy','reason'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--backend', choices=('torch','mlx'), default='mlx')
    parser.add_argument('--device', default='default')
    parser.add_argument('--resume')
    parser.add_argument('--initialize-only', action='store_true')
    parser.add_argument('--contract')
    parser.add_argument('--max-new-updates', type=int, default=1000000)
    parser.add_argument('--wall-seconds', type=float, default=3600.)
    args = parser.parse_args()
    spec = resolve_paths(read(args.spec), Path(args.spec).resolve().parent)
    origin = resolve_paths(read(args.origin_spec), Path(args.origin_spec).resolve().parent)
    result = run(spec, origin, args.origin_checkpoint, args.origin_report, args.output,
        optimizer_policy=args.optimizer_policy, reason=args.reason, backend=args.backend, device=args.device,
        resume=args.resume, initialize_only=args.initialize_only, contract_file=args.contract,
        max_new_updates=args.max_new_updates, wall_seconds=args.wall_seconds)
    print(json.dumps({k:result[k] for k in ('status','initial','final','latest_checkpoint')}, indent=2))


if __name__ == '__main__':
    main()

