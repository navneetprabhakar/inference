"""Raw completions from our own foundation checkpoints. This is a base, not an assistant."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import torch

from gpt2 import Config, GPT2
from pretrained_base import PRE_SFT_REPORT_SHA256
from tokenizer import ASSETS, load

ROOT = Path(__file__).resolve().parent
PARENT_SHA = 'f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4'
PARENT_PATH = ROOT / 'runs/astra-candidate-01' / f'step-000600-{PARENT_SHA}.pt'
CONTEXT = 512
PARAMETERS = 124_439_808
NAME = re.compile(r'step-(\d+)-([0-9a-f]{64})\.pt')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@contextmanager
def read_lock(run):
    # Do not create/update lock files or wait behind an active checkpoint writer.
    with (run / '.checkpoint.lock').open('rb') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('checkpoint publication is active; retry later') from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def verify_identity(identity):
    if identity.get('model') != asdict(Config()) or identity.get('tokenizer') != ASSETS:
        raise ValueError('expected own 124M GPT-2 architecture and pinned tokenizer')
    origin = identity.get('initialization', {})
    if (origin.get('mode') != 'own_pretraining' or origin.get('sha256') != PARENT_SHA
            or origin.get('random_lineage_root') != PRE_SFT_REPORT_SHA256
            or Path(origin.get('path', '')).resolve() != PARENT_PATH.resolve()):
        raise ValueError('unexpected own-base parent lineage')
    protocol = identity.get('protocol', {})
    parent = protocol.get('parent_checkpoint', {})
    if (parent.get('sha256') != PARENT_SHA
            or (ROOT / parent.get('path', '')).resolve() != PARENT_PATH.resolve()):
        raise ValueError('protocol parent differs from own-base lineage')
    if protocol.get('length') != CONTEXT:
        raise ValueError('sampler requires the trained 512-token context')
    if identity.get('scheduler') != protocol.get('scheduler'):
        raise ValueError('scheduler differs from frozen protocol')
    for name in ('gpt2.py', 'tokenizer.py'):
        if identity.get('code', {}).get(name) != digest(ROOT / name):
            raise ValueError(f'frozen inference implementation differs: {name}')


def verified_checkpoint(run, *, step=None, protected_step=None, filename=None):
    """Read-only validation before allocating the full model. Never selects latest implicitly."""
    run = Path(run).resolve()
    if sum(x is not None for x in (step, protected_step, filename)) != 1:
        raise ValueError('select exactly one explicit step, protected step, or filename')
    with read_lock(run):
        ledger = json.loads((run / 'campaign.json').read_text())
        signature = ledger.pop('sha256')
        if signature != hashlib.sha256(canonical(ledger)).hexdigest():
            raise ValueError('campaign ledger checksum mismatch')
        spec = json.loads((run / 'campaign-spec.json').read_text())
        if ledger.get('spec') != spec:
            raise ValueError('campaign ledger differs from frozen specification')
        identity = spec['identity']
        verify_identity(identity)
        protected_path = run / 'protected.json'
        protected = json.loads(protected_path.read_text()) if protected_path.exists() else []
        if not isinstance(protected, list) or any(not isinstance(n, str) or not NAME.fullmatch(n) for n in protected):
            raise ValueError('invalid protected checkpoint inventory')
        entries = ledger.get('checkpoints', [])
        if not isinstance(entries, list):
            raise ValueError('invalid campaign checkpoint receipts')
        receipts = {}
        for entry in entries:
            match = NAME.fullmatch(entry.get('file', ''))
            if (not match or match[2] != entry.get('sha256') or type(entry.get('bytes')) is not int
                    or entry['bytes'] <= 0):
                raise ValueError('invalid checkpoint size/digest receipt')
            receipts[entry['file']] = entry
        admitted = set(protected) | set(receipts)
        if filename is not None:
            if not isinstance(filename, str) or not NAME.fullmatch(filename) or filename not in admitted:
                raise ValueError('explicit file is not a receipted or protected checkpoint')
            candidates = [filename]
        else:
            selected_step = step if step is not None else protected_step
            if type(selected_step) is not int or selected_step < 0:
                raise ValueError('step must be a nonnegative integer')
            pool = set(protected) if protected_step is not None else admitted
            candidates = [name for name in pool if int(NAME.fullmatch(name)[1]) == selected_step]
        if len(candidates) != 1:
            raise ValueError('checkpoint step is missing or ambiguous; specify an exact --checkpoint filename')
        name = candidates[0]
        path = run / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('checkpoint must be a regular local file')
        stat = path.stat()
        # Full digest commits to exact contents AND length. Older protected files
        # lack a separate byte-count inventory; do not invent a historical receipt.
        if not 0 < stat.st_size <= 4 * 1024**3:
            raise ValueError('invalid checkpoint byte size')
        if name in receipts and stat.st_size != receipts[name]['bytes']:
            raise ValueError('checkpoint byte size differs from campaign receipt')
        expected_sha = NAME.fullmatch(name)[2]
        if digest(path) != expected_sha:
            raise ValueError('checkpoint SHA-256 mismatch')
        payload = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
        after = path.stat()
        if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('checkpoint changed during verification')
        if (payload.get('identity') != identity or payload.get('campaign_id') != ledger.get('campaign_id')
                or payload.get('spec_sha256') != hashlib.sha256(canonical(spec)).hexdigest()):
            raise ValueError('checkpoint is outside the frozen campaign identity')
        actual_step = payload.get('step')
        trained = payload.get('trained_tokens')
        effective = identity['protocol'].get('targets_per_update')
        if (type(actual_step) is not int or actual_step != int(NAME.fullmatch(name)[1])
                or type(trained) is not int or type(effective) is not int or effective <= 0
                or trained != actual_step * effective or payload.get('offset') != trained
                or not 0 <= trained <= ledger['reserved_tokens'] <= spec['token_limit']):
            raise ValueError('checkpoint cursor/token accounting mismatch')
        receipt = dict(file=str(path), sha256=expected_sha, bytes=stat.st_size, step=actual_step,
                       trained_tokens=trained, protected=name in protected, trained_context=CONTEXT,
                       separate_size_receipt=name in receipts)
        # Optimizer states and evaluation transcripts are not needed for sampling.
        weights = payload['model']
        del payload
        return weights, receipt


def load_model(run, **selection):
    weights, receipt = verified_checkpoint(run, **selection)
    model = GPT2()
    if sum(p.numel() for p in model.parameters()) != PARAMETERS:
        raise ValueError('unexpected model parameter count')
    if any(t.dtype != torch.float32 for t in weights.values()):
        raise ValueError('checkpoint master weights must be FP32')
    model.load_state_dict(weights, strict=True)
    return model.eval(), receipt


def validate_generation(prompt_ids, max_new_tokens, temperature):
    if not prompt_ids:
        raise ValueError('prompt must contain at least one token')
    if type(max_new_tokens) is not int or not 1 <= max_new_tokens <= CONTEXT:
        raise ValueError('max-new-tokens must be an integer from 1 to 512')
    if len(prompt_ids) + max_new_tokens > CONTEXT:
        raise ValueError('prompt plus requested continuation exceeds trained context 512; no silent truncation')
    if not math.isfinite(temperature) or temperature < 0:
        raise ValueError('temperature must be finite and nonnegative')


@torch.inference_mode()
def complete(model, prompt_ids, max_new_tokens=64, temperature=0., *, seed=0, eot=50256):
    validate_generation(prompt_ids, max_new_tokens, temperature)
    if next(model.parameters()).device.type != 'cpu':
        raise ValueError('this sampler is CPU-only to avoid competing with live MPS training')
    ids = list(prompt_ids)
    rng = torch.Generator(device='cpu').manual_seed(seed)
    for _ in range(max_new_tokens):
        logits = model(torch.tensor([ids], dtype=torch.long))[0, -1]
        if not torch.isfinite(logits).all():
            raise ValueError('nonfinite completion logits')
        token = (int(logits.argmax()) if temperature == 0 else
                 int(torch.multinomial(torch.softmax(logits / temperature, dim=-1), 1, generator=rng)))
        if token == eot:
            break
        ids.append(token)
    return ids[len(prompt_ids):]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--step', type=int)
    selection.add_argument('--protected-step', type=int)
    selection.add_argument('--checkpoint', help='exact receipted/protected basename; resolves duplicate-step ambiguity')
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--max-new-tokens', type=int, default=64)
    parser.add_argument('--temperature', type=float, default=0., help='0=greedy (default)')
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    torch.set_num_threads(1)
    tokenizer = load()  # Local pinned assets only: never calls fetch.
    ids = tokenizer.encode(args.prompt).ids
    validate_generation(ids, args.max_new_tokens, args.temperature)
    model, receipt = load_model(args.run, step=args.step, protected_step=args.protected_step, filename=args.checkpoint)
    print('Raw own-base completion; not an assistant. ' + json.dumps(receipt), file=sys.stderr)
    print(tokenizer.decode(complete(model, ids, args.max_new_tokens, args.temperature, seed=args.seed)))


if __name__ == '__main__':
    main()
