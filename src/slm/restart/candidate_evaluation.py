"""Native MLX evaluation of an already-published candidate checkpoint.

No entrypoint or initializer. The candidate launcher must provide process custody,
independent supervision and active-time charging before calling evaluate().
"""
import hashlib
import json
import time
from pathlib import Path
import numpy as np
from slm.common.config import Config,validate_weights
from slm.common.tokenizer import BPE
from . import numerical_snapshot,development_loss,choice_execution,generation_execution,full_diagnostics
from .evaluation_checkpoint import prepare,BoundLogits
from .evaluation_snapshot import MANIFEST_SHA256,_file
from .numerical_prerequisites import PINS
from .training_loss_sample import TrainingLossSample

SAMPLE_PIN='6100e12f2559f53b526ec30f57f5333778d1a8c3f537b22d064c4be48dee3c0d'


def inputs(project,event):
    if event not in ('dev_loss_checkpoint','full_development_diagnostics','copying_probes'):
        raise ValueError('Development evaluation event required')
    base=project/'restart/execution-v1'
    raw=_file(project,'restart/approval-v1/policy.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=numerical_snapshot.POLICY:raise ValueError('Changed architecture policy')
    policy=json.loads(raw);config=Config(**policy['architecture'])
    if config.parameter_count!=5114112:raise ValueError('Unexpected candidate parameter count')
    tp=base/'tokenizer-8192'
    if hashlib.sha256(_file(tp,'manifest.json').read_bytes()).hexdigest()!=PINS['tokenizer-8192/manifest.json']:
        raise ValueError('Changed evaluation tokenizer')
    tokenizer=BPE.load(tp)
    if tokenizer.vocab_size!=config.vocab_size:raise ValueError('Tokenizer/config mismatch')
    result={'config':config,'tokenizer':tokenizer}
    if event in ('dev_loss_checkpoint','full_development_diagnostics'):
        result['dev_store']=development_loss.DevelopmentTokens(base/'data-dev',manifest_sha256=PINS['data-dev/manifest.json'])
    if event=='full_development_diagnostics':
        raw=_file(base,'training-loss-sample-v1.json').read_bytes()
        result['train_store']=TrainingLossSample(base/'data-train',source_manifest_sha256=PINS['data-train/manifest.json'],spec_raw=raw,spec_sha256=SAMPLE_PIN)
        result['grammar_items']=choice_execution.load_development(project,'grammar')
        result['grounded_items']=choice_execution.load_development(project,'grounded')
        result['narrative_items']=generation_execution.load_development(project,'narrative')
        manifest=_file(base/'evaluation-frozen-v1','manifest.json').read_bytes()
        if hashlib.sha256(manifest).hexdigest()!=MANIFEST_SHA256:raise ValueError('Changed smoke inventory')
        result['smoke_ids']=json.loads(manifest)['development_smoke_ids']
        # Detect incompatible input lengths/recipes before backend allocation.
        choice_execution.prepare(result['grammar_items'],tokenizer)
        for variant in ('original','empty','shuffled'):choice_execution.prepare(result['grounded_items'],tokenizer,variant=variant)
    if event=='copying_probes':result['pairs']=generation_execution.load_development(project,'copy')
    return result


class _MLX:
    def __init__(self,prepared,config):
        validate_weights(config,prepared['params'])
        import mlx.core as mx
        from slm.backends import mlx_backend
        self.mx=mx;self.backend=mlx_backend;self.config=config
        # Explicit copy of verified checkpoint buffers; never random initialization.
        self.params={k:mx.array(v) for k,v in prepared['params'].items()};mx.eval(self.params)

    def export_parameters(self):return self.backend.export(self.params)

    def forward_numpy(self,x,padding):
        out,_,_=self.backend.forward(self.params,self.config,self.mx.array(x),padding_mask=self.mx.array(padding))
        self.mx.eval(out)
        return np.array(out)


def evaluate(project,checkpoint,*,checkpoint_root,manifest_sha256,identity,expected,schedule,ledger,context,deadline,heartbeat,quality=None):
    project=Path(project).resolve(strict=True)
    original_deadline=numerical_snapshot.authority(project,time.time())
    if type(deadline) not in (int,float) or not time.time()<deadline<=original_deadline:
        raise ValueError('Unavailable evaluator time budget')
    event=context.get('event');data=inputs(project,event);config=data.pop('config')
    actual_config_hash=hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest()
    if expected.get('config_hash')!=actual_config_hash:raise ValueError('Evaluation configuration hash mismatch')
    if expected.get('tokenizer_hash')!=PINS['tokenizer-8192/manifest.json']:
        raise ValueError('Evaluation tokenizer hash mismatch')
    prepared=prepare(checkpoint,checkpoint_root=checkpoint_root,manifest_sha256=manifest_sha256,identity=identity,
        expected=expected,shapes=config.shapes(),schedule=schedule,ledger=ledger,context=context,quality=quality)
    def tick():
        if time.time()>=deadline:raise ValueError('Evaluator deadline exhausted')
        heartbeat()
    tick();bound=BoundLogits(prepared,_MLX(prepared,config));started=time.monotonic()
    if event=='dev_loss_checkpoint':
        result=development_loss.score(data['dev_store'],context=prepared['context'],logits=bound,heartbeat=tick)
        verify=development_loss.quality_verifier(data['dev_store'])
    elif event=='full_development_diagnostics':
        execution={k:v for k,v in data.items() if k!='smoke_ids'}
        result=full_diagnostics.execute(context=prepared['context'],logits=bound,heartbeat=tick,**execution)
        verify=full_diagnostics.verifier(**data)
    else:
        result=generation_execution.copying(data['pairs'],data['tokenizer'],logits=bound,heartbeat=tick)
        result['context']=prepared['context'];verify=full_diagnostics.copying_verifier(**data)
    bound.check();tick()
    raw=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode()
    metrics=verify(raw,prepared['context'])
    receipt={'checkpoint_sha256':manifest_sha256,'parameter_sha256':prepared['parameter_sha256'],
             'result_sha256':hashlib.sha256(raw).hexdigest(),'forward_calls':bound.calls,
             'evaluation_seconds':time.monotonic()-started,'metrics':metrics}
    return raw,receipt
