"""Approval-bound experiment support. Historical sources are imported, never edited."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PRIVATE = ROOT / 'private'
SOURCE = PROJECT / 'restart/broader-curriculum-v1/broad/epoch-100.pt'
SOURCE_SHA = '78c5213150ef5599dd0734db924b077c09c756ab43a6084b21f7ec8ada4d0cb3'
ORIGINAL_NLL = 1.3430354408919811
SEED = 246024


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serializer = import_file('bridge_serialization', PROJECT / 'restart/sol-conversation-sft-diagnostic-v1/runner.py')


def normalized(text):
    return re.findall(r'\w+', text.casefold())


def strict(expected, text, kind='legacy'):
    if kind == 'time':
        return bool(re.fullmatch(r'\d{2}:\d{2}', text.strip())) and text.strip() == expected.strip()
    if kind == 'name':
        return ' '.join(text.casefold().split()) == ' '.join(expected.casefold().split())
    return normalized(expected) == normalized(text)


def retention_content(case, text, turn):
    expected = case['messages'][2 * turn + 1]['content']
    if strict(expected, text):
        return True
    # Complete affirmative sentence for the same entity/value, not substring matching.
    entity = case.get('entity')
    if entity:
        family = case.get('family')
        allowed = ([f'The {entity} is {expected}.'] if family in ['color', 'correction'] else
                   [f'The {entity} is on the {expected}.', f'The {entity} is in the {expected}.'] if family == 'location' else
                   [f'The owner of the {entity} is {expected}.'])
        return any(normalized(text) == normalized(answer) for answer in allowed)
    return False


def assert_frozen():
    for relative, expected in read(ROOT / 'freeze.json')['files'].items():
        assert sha(PROJECT / relative) == expected, 'FROZEN_INPUT_CHANGED: ' + relative


class Meter:
    def __init__(self, phase):
        self.phase = phase
        self.path = ROOT / 'ledger.json'
        self.data = read(self.path) if self.path.exists() else dict(positions=0, updates=0, sft_targets=0,
            narrative_targets=0, model_seconds=0., peak_rss=0, segments=[], reservations=[])
        if self.data.get('active_segment'):
            raise RuntimeError('UNCLOSED_SEGMENT_REQUIRES_ACCOUNTING')
        self.start = time.time()
        self.data['active_segment'] = dict(phase=phase, start=self.start, pid=os.getpid())
        self.flush()
        self.check()

    def flush(self):
        save(self.path, self.data)

    def check(self):
        import psutil
        seconds = self.data['model_seconds'] + time.time() - self.start
        if seconds >= 2700:
            raise RuntimeError('MODEL_TIME_CAP')
        rss = psutil.Process().memory_info().rss
        self.data['peak_rss'] = max(self.data['peak_rss'], rss)
        if rss > 12 * 1024**3 or psutil.disk_usage(PROJECT).free < 60 * 1024**3:
            raise RuntimeError('RSS_OR_DISK_CAP')
        if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) > 5 * 1024**3:
            raise RuntimeError('ARTIFACT_CAP')
        approval = read(ROOT / 'approval.json')
        prep = time.time() - approval['preparation_start_epoch'] - seconds
        if prep >= 21600:
            raise RuntimeError('PREPARATION_TIME_CAP')

    def reserve(self, n, kind, updates=0, sft=0, narrative=0):
        self.check()
        assert n >= 0
        if updates and (ROOT / 'STOP.json').exists():
            raise RuntimeError('TERMINAL_STOP')
        limits = dict(positions=40000000, updates=1006, sft_targets=250000, narrative_targets=3000000)
        charges = dict(positions=int(n), updates=updates, sft_targets=sft, narrative_targets=narrative)
        for key, value in charges.items():
            if self.data[key] + value > limits[key]:
                raise RuntimeError('AGGREGATE_CAP_' + key)
        # Keep final tests funded until a terminal fit/guard result cancels them.
        if self.phase not in ['final', 'diagnosis'] and self.data['positions'] + n > 40000000 - 9437184:
            raise RuntimeError('FINAL_EVALUATION_RESERVATION')
        for key, value in charges.items():
            self.data[key] += value
        self.data['reservations'].append(dict(phase=self.phase, kind=kind, **charges))
        self.flush()

    def close(self):
        elapsed = time.time() - self.start
        self.data['model_seconds'] += elapsed
        self.data['segments'].append(dict(phase=self.phase, start=self.start, end=time.time(), seconds=elapsed))
        self.data.pop('active_segment', None)
        self.flush()


def load(path=SOURCE, mode='resume', cursor=None):
    common = import_file('bridge_engine_common', PROJECT / 'restart/foundation-recovery-v2-corrected/common.py')
    engine, _ = common.load_engine(path, 'bf16', schedule=lambda _: 2e-5)
    engine.mapping = sys.modules['engine_support'].mapping
    assert mode in ['fresh', 'resume']
    if mode == 'fresh':
        engine.base_step = 0
        for opt, names in [(engine.om, engine.matrix), (engine.on, engine.norm)]:
            opt.state['step'] = engine.mx.array(0, engine.mx.uint64)
            for key in names:
                for field in ['m', 'v']:
                    opt.state[key][field] = engine.mx.zeros_like(engine.params[key])
        engine.mx.random.seed(SEED)
    engine.mx.eval(engine.om.state, engine.on.state, engine.mx.random.state)
    engine.bridge_cursor = cursor if cursor is not None else engine.origin.get('bridge_cursor', 0)
    engine.bridge_sft = engine.origin.get('bridge_sft_targets', 0) if mode == 'resume' else 0
    engine.bridge_replay = engine.origin.get('bridge_replay_targets', 0) if mode == 'resume' else 0
    engine.last_lr = engine.origin.get('effective_learning_rate', 2e-5)
    return engine, common


def snapshot(engine, meter):
    state = engine.checkpoint()
    step = engine.base_step + engine.local_step
    state.update(schema='teacher-bridge-execution-v1', optimizer_step=step,
        parent_checkpoint_sha256=SOURCE_SHA, bridge_cursor=engine.bridge_cursor,
        bridge_sft_targets=engine.bridge_sft, bridge_replay_targets=engine.bridge_replay,
        cumulative_sft_updates=500 + engine.bridge_cursor,
        cumulative_sft_targets=14299 + engine.bridge_sft,
        cumulative_foundation_replay_targets=1024000 + engine.bridge_replay,
        effective_learning_rate=engine.last_lr, schedule_position=engine.bridge_cursor,
        ledger_cursor=len(meter.data['reservations']))
    for group in state['optimizer']['param_groups']:
        group['lr'] = engine.last_lr
    assert all(int(x['step']) == step for x in state['optimizer']['state'].values())
    return state


def checkpoint(engine, meter, name):
    import torch
    path = PRIVATE / (name + '.pt')
    state = snapshot(engine, meter)
    tmp = path.with_suffix('.tmp.pt')
    torch.save(state, tmp)
    tmp.replace(path)
    restored = torch.load(path, map_location='cpu', weights_only=False)
    exact_state(state, restored, metadata=True)
    return path


def exact_state(a, b, metadata=False):
    import torch
    assert a['model'].keys() == b['model'].keys()
    for key in a['model']:
        assert torch.equal(a['model'][key], b['model'][key]), key
    assert a['optimizer']['param_groups'] == b['optimizer']['param_groups']
    for key in a['optimizer']['state']:
        for field in ['step', 'exp_avg', 'exp_avg_sq']:
            assert torch.equal(a['optimizer']['state'][key][field], b['optimizer']['state'][key][field]), (key, field)
    for x, y in zip(a['mlx_rng_state'], b['mlx_rng_state']):
        assert np.array_equal(x, y)
    for key in ['optimizer_step', 'bridge_cursor', 'effective_learning_rate', 'schedule_position', 'bridge_sft_targets', 'bridge_replay_targets']:
        assert a[key] == b[key], key
    if metadata:
        assert a['ledger_cursor'] == b['ledger_cursor']
    assert torch.equal(b['model']['output.weight'], b['model']['tok_embeddings.weight'])


def update(engine, common, gfn, groups, narrative, lr, meter):
    # groups: [(name, coefficient, encoded_records)], narrative weight is .5.
    xs = [serializer.collate(rows) for _, _, rows in groups]
    ntargets = sum(int(m.sum()) for _, _, m, _ in xs)
    meter.reserve(sum(x.size for x, _, _, _ in xs) + narrative[:, :-1].size,
        'optimizer-update', updates=1, sft=ntargets, narrative=narrative[:, :-1].size)
    mx = engine.mx
    vb, gb = engine.grad_fn(engine.params, mx.array(narrative[:, :-1]), mx.array(narrative[:, 1:]))
    combined = {k: .5 * v / engine.scale for k, v in gb.items()}
    component = {'narrative': dict(loss=float(vb) / engine.scale, coefficient=.5,
        targets=narrative[:, :-1].size, norm=float(mx.sqrt(sum(mx.sum(v*v) for v in gb.values()))) / engine.scale)}
    for (name, weight, rows), (x, y, mask, _) in zip(groups, xs):
        assert float(mask.sum()) > 0 and weight > 0
        value, grad = gfn(engine.params, mx.array(x), mx.array(y), mx.array(mask))
        mx.eval(value, grad)
        component[name] = dict(loss=float(value), coefficient=weight, targets=int(mask.sum()),
            norm=float(mx.sqrt(sum(mx.sum(v*v) for v in grad.values()))))
        combined = {k: combined[k] + weight * grad[k] for k in combined}
    norm = mx.sqrt(sum(mx.sum(v*v) for v in combined.values()))
    mx.eval(combined, norm)
    if not math.isfinite(float(norm)) or float(norm) > 100 or not all(math.isfinite(v['loss']) for v in component.values()):
        raise RuntimeError('NUMERICAL_HARD_STOP')
    engine.params, _ = engine.step_fn(engine.params, combined, mx.array(lr))
    mx.eval(engine.params, engine.om.state, engine.on.state)
    engine.local_step += 1
    engine.bridge_cursor += 1
    engine.bridge_sft += ntargets
    engine.bridge_replay += narrative[:, :-1].size
    engine.last_lr = lr
    common.finite(engine)
    memory = engine.memory()
    meter.check()
    return dict(step=engine.bridge_cursor, optimizer_step=engine.base_step+engine.local_step,
        lr=lr, combined_gradient_norm=float(norm), components=component, memory=memory)


def foundation(engine, meter):
    arr = np.load(PROJECT / 'restart/foundation-stage3-v1/validation.npy')
    assert arr.shape == (512, 257)
    values = []
    for i in range(0, 512, 16):
        meter.reserve(4096, 'narrative-validation')
        values.append(engine.validation(arr[i:i+16]))
    loss = float(np.mean(values))
    assert math.isfinite(loss)
    return loss


def generate(engine, common, cases, sp, cap, meter, label, legacy=False):
    model = common.bind(engine)
    rows = []
    for case in cases:
        context = []
        for turn in range(len(case['messages']) // 2):
            context.append(case['messages'][2*turn])
            ids = serializer.prompt(sp, context)
            tokens, stop, overflow = [], None, len(ids) + cap > 256
            if not overflow:
                for _ in range(cap):
                    meter.reserve(len(ids), 'generate-' + label)
                    logits = model(engine.mx.array([ids], engine.mx.int32))[0, -1, :].astype(engine.mx.float32)
                    engine.mx.eval(logits)
                    engine.memory()
                    if not bool(engine.mx.all(engine.mx.isfinite(logits))):
                        raise RuntimeError('NONFINITE_LOGITS')
                    token = int(engine.mx.argmax(logits))
                    if token in [sp.bos_id(), sp.eos_id()]:
                        stop = token
                        break
                    tokens.append(token)
                    ids.append(token)
            text = sp.decode(tokens)
            expected = case['messages'][2*turn+1]['content']
            kind = case.get('kind', 'legacy')
            exact = strict(expected, text, kind)
            eos = stop == sp.eos_id()
            content = retention_content(case, text, turn) if legacy else exact
            rows.append(dict(id=case['id'], family=case['family'], turn=turn, user=context[-1]['content'],
                expected=expected, response=text, generated_ids=tokens, eos=eos, stop_token=stop,
                overflow=overflow, strict=exact and eos and not overflow, content=content and eos and not overflow))
            context.append(dict(role='assistant', content=text))
    save(PRIVATE / (label + '-responses.json'), rows)
    return dict(turns=len(rows), strict=sum(x['strict'] for x in rows), content=sum(x['content'] for x in rows),
        eos=sum(x['eos'] for x in rows), overflows=sum(x['overflow'] for x in rows),
        families={family: dict(turns=sum(x['family']==family for x in rows),
            strict=sum(x['strict'] for x in rows if x['family']==family)) for family in sorted({r['family'] for r in rows})})
