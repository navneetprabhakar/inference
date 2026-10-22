"""Target-weighted FP32 gradient accumulation, with no optimizer side effects."""
import numpy as np


class TargetAccumulator:
    """Backend arrays stay on their backend; clipping occurs only after finish()."""
    def __init__(self, shapes, backend, target_cap=8192):
        if type(target_cap) is not int or not 1 <= target_cap <= 8192:
            raise ValueError('Invalid target cap')
        if backend not in ('torch', 'mlx') or not shapes:
            raise ValueError('Invalid accumulator configuration')
        self.shapes = dict(shapes)
        self.backend = backend
        self.target_cap = target_cap
        self.targets = 0
        self.microbatches = 0
        self._sums = None
        self._loss_sum = 0.
        self._finished = False

    def add(self, mean_loss, mean_gradients, targets):
        if self._finished:
            raise ValueError('Accumulator already consumed')
        if type(targets) is not int or targets <= 0 or self.targets + targets > self.target_cap:
            raise ValueError('Invalid or over-budget supervision count')
        if set(mean_gradients) != set(self.shapes):
            raise ValueError('Gradient inventory mismatch')
        value = float(mean_loss)
        if not np.isfinite(value) or value < 0:
            raise ValueError('Invalid mean loss')
        if self.backend == 'torch':
            import torch
            for key, gradient in mean_gradients.items():
                if (not isinstance(gradient, torch.Tensor) or gradient.dtype != torch.float32
                        or tuple(gradient.shape) != tuple(self.shapes[key])
                        or not bool(torch.isfinite(gradient).all())):
                    raise ValueError('Invalid gradient: ' + key)
            weighted = {k: g.detach() * targets for k, g in mean_gradients.items()}
            finite = lambda x: bool(torch.isfinite(x).all())
        else:
            import mlx.core as mx
            for key, gradient in mean_gradients.items():
                if (not isinstance(gradient, mx.array) or gradient.dtype != mx.float32
                        or tuple(gradient.shape) != tuple(self.shapes[key])
                        or not bool(mx.all(mx.isfinite(gradient)))):
                    raise ValueError('Invalid gradient: ' + key)
            weighted = {k: mx.stop_gradient(g) * targets for k, g in mean_gradients.items()}
            finite = lambda x: bool(mx.all(mx.isfinite(x)))
        candidate = weighted if self._sums is None else {k: self._sums[k]+weighted[k] for k in self.shapes}
        loss_sum = self._loss_sum + value * targets
        if not np.isfinite(loss_sum) or not all(finite(v) for v in candidate.values()):
            raise ValueError('Accumulation overflow')
        # No accounting or buffer mutation until the complete microbatch validates.
        self._sums = candidate
        self._loss_sum = loss_sum
        self.targets += targets
        self.microbatches += 1

    def finish(self):
        if self._finished or not self.targets:
            raise ValueError('Empty or consumed accumulator')
        self._finished = True
        return self._loss_sum/self.targets, {k: v/self.targets for k,v in self._sums.items()}
