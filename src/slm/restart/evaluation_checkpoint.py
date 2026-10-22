"""Bind evaluation inputs to a complete current checkpoint and live ledger.

No random initialization, backend construction, or launcher authority. The scoped
parent must supply independently pinned identity, hashes, schedule and ledger.
"""
import hashlib
from pathlib import Path
import numpy as np
from . import checkpoint_binding,state
from .numerical_monitor_comparison import exact

EVENTS={'dev_loss_checkpoint','full_development_diagnostics','copying_probes'}


def prepare(path,*,checkpoint_root,manifest_sha256,identity,expected,shapes,schedule,ledger,context,quality=None):
    path=Path(path).absolute();root=Path(checkpoint_root).absolute()
    if root.resolve(strict=True)!=root or path.resolve(strict=True)!=path or path.parent!=root:
        raise ValueError('Checkpoint outside owned root or redirected')
    if not isinstance(manifest_sha256,str) or len(manifest_sha256)!=64:
        raise ValueError('Parent-pinned checkpoint digest required')
    if state.digest(path/'manifest.json')!=manifest_sha256:
        raise ValueError('Checkpoint differs from parent pin')
    restored=checkpoint_binding.restore(path,shapes=shapes,schedule=schedule,ledger=ledger,identity=identity,expected=expected)
    metadata=restored['metadata']
    required=dict(identity=identity,schedule_sha256=schedule.sha256,step=metadata['step'],targets=metadata['targets'],
                  checkpoint_sha256=manifest_sha256,event=context.get('event'))
    if context.get('event') not in EVENTS or not exact(context,required):
        raise ValueError('Evaluation context does not match checkpoint')
    if restored['charged_work_after_checkpoint']!={'later_updates_reserved':0,'later_targets_reserved':0,'refunds':0}:
        raise ValueError('Evaluation checkpoint is behind charged training work')
    snapshot=metadata['ledger_snapshot']
    if snapshot['updates_reserved']!=snapshot['updates_completed'] or snapshot['targets_reserved']!=snapshot['targets_completed']:
        from .interruption_recovery import validate_abandoned_work
        validate_abandoned_work(ledger,quality,checkpoint_step=metadata['step'])
    if state.digest(path/'manifest.json')!=manifest_sha256:raise ValueError('Checkpoint changed during read')
    params={k.split(':',1)[1]:np.array(v,copy=True) for k,v in restored['arrays'].items() if k.startswith('parameter:')}
    for value in params.values():value.flags.writeable=False
    return {'params':params,'context':dict(required),'parameter_sha256':fingerprint(params),
            'checkpoint_path':str(path),'checkpoint_sha256':manifest_sha256}


def fingerprint(params):
    if not params:raise ValueError('Missing evaluation parameters')
    result={}
    for name,value in params.items():
        if not isinstance(value,np.ndarray) or value.dtype!=np.float32 or not np.isfinite(value).all():
            raise ValueError('Invalid evaluation parameter buffer')
        h=hashlib.sha256();h.update(str(value.shape).encode());h.update(value.tobytes());result[name]=h.hexdigest()
    return result


class BoundLogits:
    """Wrap an already-created backend, verifying parameter identity before/after.

    Backend supplies forward_numpy(x,padding) and export_parameters(). Native
    model loading remains the scoped worker's responsibility after preflight.
    """
    def __init__(self,prepared,backend):
        self.backend=backend;self.expected=dict(prepared['parameter_sha256']);self.calls=0
        self.check()

    def check(self):
        if not exact(fingerprint(self.backend.export_parameters()),self.expected):
            raise ValueError('Evaluation backend differs from bound checkpoint')

    def __call__(self,x,padding):
        self.check()
        result=self.backend.forward_numpy(x,padding)
        self.check();self.calls+=1
        return result
