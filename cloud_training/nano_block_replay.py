"""Exact, bounded conversational experiment; never a release training mode."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from cloud_training.nano_data import sha256_file

# One prospectively reviewed experiment. New experiments require a new review.
PLAN_SHA = '82a15f380ae90f3fd4f24904ef88886674dc6218f6345e3603223e3b17a07f5c'

class BlockReplay:
    def __init__(self, dataset, plan_path, arm):
        from cloud_training.nano_sft import BestFitConversations
        if arm not in ('broad', 'control') or sha256_file(plan_path) != PLAN_SHA:
            raise ValueError('Unreviewed block replay identity')
        self.plan = json.loads(Path(plan_path).read_text())
        self.dataset, self.arm = dataset, arm
        self.capacity, self.buffer_size = 2049, 1
        self.next_block = self.consumed = self.rows = 0
        self.sha = hashlib.sha256(json.dumps([PLAN_SHA, dataset.sha, arm]).encode()).hexdigest()
        rows = [json.loads(line) for line in dataset.path.read_text().splitlines()]
        ids = {r['id']: i for i, r in enumerate(rows)}
        if len(ids) != len(rows) or dataset.context != 2048:
            raise ValueError('Invalid block corpus')
        self.orders, self.counts = [], []
        for index, block in enumerate(self.plan['blocks']):
            if block['update'] != index + 1:
                raise ValueError('Invalid block order')
            order = [ids[x] for x in block[arm]]
            if any(rows[i]['family'] != block['family'] for i in order):
                raise ValueError('Block family mismatch')
            count = sum(dataset.target_counts[i] for i in order)
            if count != block['assistant_targets_each_arm']:
                raise ValueError('Block target mismatch')
            self.orders.append(order); self.counts.append(count)
            view = self._view(order)
            pack = BestFitConversations(view, buffer_size=1)
            try:
                while True: pack.next_indices()
            except StopIteration: pass
            if not 1 <= pack.rows <= 4:
                raise ValueError('Block exceeds four complete rows')
        exposures = Counter(i for order in self.orders for i in order)
        if len(self.orders) != 40 or sum(self.counts) != 9144 or set(exposures) != set(range(len(rows))):
            raise ValueError('Incomplete reviewed block plan')
        if max(exposures.values()) > (4 if arm == 'broad' else 20):
            raise ValueError('Replay exposure exceeded')

    def _view(self, order):
        dataset = self.dataset
        class View:
            tokenizer = dataset.tokenizer
            context = 2048
            sha = self.sha
            lengths = [dataset.lengths[i] for i in order]
            def __len__(self): return len(order)
            def get(self, index): return dataset.get(order[index])
        return View()

    def state_dict(self):
        return {'block_identity': self.sha, 'arm': self.arm, 'next_block': self.next_block,
                'consumed': self.consumed, 'rows': self.rows}

    def load_state_dict(self, state):
        n = state.get('next_block')
        if (set(state) != set(self.state_dict()) or state.get('block_identity') != self.sha
            or state.get('arm') != self.arm or type(n) is not int or not 0 <= n <= 40
            or type(state.get('consumed')) is not int or state['consumed'] != sum(map(len, self.orders[:n]))
            or type(state.get('rows')) is not int or state['rows'] != 4*n):
            raise ValueError('Block cursor identity/count mismatch')
        self.next_block, self.consumed, self.rows = n, state['consumed'], state['rows']

    def next_update(self):
        from cloud_training.nano_sft import BestFitConversations
        if self.next_block == 40: return [], 0
        pack = BestFitConversations(self._view(self.orders[self.next_block]), buffer_size=1)
        batches = []
        try:
            while True:
                x, y = pack.next_row(); batches.append(([x], [y]))
        except StopIteration: pass
        while len(batches) < 4:
            batches.append(([[self.dataset.tokenizer.get_bos_token_id()]*2048], [[-1]*2048]))
        count = sum(t != -1 for _, ys in batches for row in ys for t in row)
        if len(batches) != 4 or count != self.counts[self.next_block]:
            raise ValueError('Packed block target/position mismatch')
        self.consumed += len(self.orders[self.next_block]); self.rows += 4; self.next_block += 1
        return batches, count


def validate_recipe(args, contract, manifest):
    expected = {'stage': 'targeted', 'context_tokens': 2048, 'batch_tokens': 8192,
                'microbatch': 1, 'packing_buffer_size': 1, 'epochs': 1, 'seed': 103,
                'lr_multiplier': .25, 'muon_kernel_mode': 'eager'}
    for key, value in expected.items():
        if getattr(args, key) != value: raise ValueError('Block recipe mismatch: '+key)
    if (not args.deterministic or args.deterministic_attention or args.fit_diagnostic
        or args.eval_every_updates not in (1, 5) or args.eval_rows < 128
        or type(args.max_updates) is not int or not 1 <= args.max_updates <= 40):
        raise ValueError('Unbounded or nondeterministic block experiment')
    if (contract.get('objective') != 'controlled_conversation_pilot'
        or contract.get('block_plan_sha256') != PLAN_SHA
        or contract.get('block_arm') != args.block_arm
        or contract.get('required_parent_manifest_sha256') != args.base_manifest_sha
        or contract.get('training_sha256') != manifest['train']['sha256']
        or contract.get('release_eligible') is not False
        or contract.get('regression') != {'relative_tolerance': .05, 'patience': 2}):
        raise ValueError('Block experiment contract mismatch')
    if args.base_manifest_sha != json.loads(Path(args.block_plan).read_text())['parent_manifest_sha256']:
        raise ValueError('Block experimental parent mismatch')


def validate_packet(plan_path, arm, manifest, contract):
    """Re-read the complete frozen review packet; budget is a controller concern."""
    root=Path(plan_path).resolve().parent
    if sha256_file(root/'freeze.json') != 'd5b4f88fd18b0f851147f90c4aefee44079bf9dbd03aa85f56c9bc062baf4f4e':
        raise ValueError('Unreviewed candidate freeze')
    freeze=json.loads((root/'freeze.json').read_text())
    for name,digest in freeze['files'].items():
        if Path(name).name != name or sha256_file(root/name)!=digest:
            raise ValueError('Frozen candidate changed: '+name)
    spec=json.loads((root/'pilot-spec.json').read_text())
    expected=spec['arm_input_sha256'][arm]
    if (manifest['train']['sha256']!=expected
        or manifest['validation']['sha256']!=freeze['files']['development.jsonl']
        or contract.get('review_sha256')!=spec['review_sha256']
        or contract.get('source_manifest_sha256')!=spec['source_manifest_sha256']
        or manifest['tokenizer_sha256']!=spec['tokenizer_sha256']):
        raise ValueError('Inputs do not match reviewed experimental packet')
