"""Backend-independent architecture and canonical FP32 initialization."""
from dataclasses import asdict, dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Config:
    vocab_size: int = 64
    hidden_size: int = 32
    intermediate_size: int = 64
    num_layers: int = 2
    num_heads: int = 4
    num_kv_heads: int = 2
    max_seq_len: int = 64
    rope_theta: float = 10000.0
    norm_eps: float = 1e-5

    def __post_init__(self):
        for name in ('vocab_size', 'hidden_size', 'intermediate_size', 'num_layers',
                     'num_heads', 'num_kv_heads', 'max_seq_len'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f'{name} must be a positive integer')
        if self.hidden_size % self.num_heads or self.num_heads % self.num_kv_heads:
            raise ValueError('Invalid head divisibility')
        if self.head_dim % 2:
            raise ValueError('RoPE requires an even head dimension')
        if not math.isfinite(self.rope_theta) or self.rope_theta <= 0:
            raise ValueError('Invalid RoPE base')
        if not math.isfinite(self.norm_eps) or self.norm_eps <= 0:
            raise ValueError('Invalid normalization epsilon')

    @property
    def head_dim(self):
        return self.hidden_size // self.num_heads

    def shapes(self):
        d, f, k = self.hidden_size, self.intermediate_size, self.num_kv_heads*self.head_dim
        shapes = {'embedding': (self.vocab_size, d), 'final_norm': (d,)}
        for i in range(self.num_layers):
            for name, shape in {'attn_norm': (d,), 'ffn_norm': (d,), 'q': (d, d),
                                'k': (k, d), 'v': (k, d), 'o': (d, d),
                                'gate': (f, d), 'up': (f, d), 'down': (d, f)}.items():
                shapes[f'layers.{i}.{name}'] = shape
        return shapes

    @property
    def parameter_count(self):
        return sum(math.prod(s) for s in self.shapes().values())

    def to_dict(self):
        return asdict(self)


def initialize(config: Config, seed=42):
    from slm.common.restart_guard import require_training_approval
    require_training_approval()
    rng = np.random.default_rng(seed)
    weights = {}
    for name, shape in config.shapes().items():
        if len(shape) == 1:
            weights[name] = np.ones(shape, dtype=np.float32)
        else:
            std = 0.02 / math.sqrt(2*config.num_layers) if name.endswith(('.o', '.down')) else 0.02
            weights[name] = rng.normal(0, std, shape).astype(np.float32)
    return weights


def validate_weights(config, weights):
    if weights.keys() != config.shapes().keys():
        raise ValueError('Checkpoint parameter keys do not match architecture')
    for name, shape in config.shapes().items():
        w = weights[name]
        if w.shape != shape or w.dtype != np.float32 or not np.isfinite(w).all():
            raise ValueError(f'Invalid tensor: {name}')
