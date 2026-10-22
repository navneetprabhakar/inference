"""Native final evaluation orchestration, callable only under scoped supervision.

No initializer, optimizer or CLI. Checkpoint/termination validation precedes every
holdout read. Parent still owns immutable snapshot, custody and one-use dispatch.
"""
import hashlib,json,time
from pathlib import Path
from slm.common.config import Config
from slm.common.tokenizer import BPE
from . import numerical_snapshot,final_checkpoint,final_inputs,final_diagnostics
from .candidate_evaluation import _MLX
from .evaluation_checkpoint import BoundLogits
from .evaluation_snapshot import _file
from .numerical_prerequisites import PINS
from .final_loss import FinalTokens
from .final_baselines import FrozenBaselines


def inputs(project):
    base=project/'restart/execution-v1'
    raw=_file(project,'restart/approval-v1/policy.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=numerical_snapshot.POLICY:raise ValueError('Changed final architecture policy')
    config=Config(**json.loads(raw)['architecture'])
    if config.parameter_count!=5114112:raise ValueError('Unexpected final candidate architecture')
    tp=base/'tokenizer-8192'
    if hashlib.sha256(_file(tp,'manifest.json').read_bytes()).hexdigest()!=PINS['tokenizer-8192/manifest.json']:
        raise ValueError('Changed final tokenizer')
    tokenizer=BPE.load(tp)
    if tokenizer.vocab_size!=config.vocab_size:raise ValueError('Final tokenizer mismatch')
    return dict(config=config,tokenizer=tokenizer,store=FinalTokens(base/'data-final',manifest_sha256=PINS['data-final/manifest.json']),
        grammar_items=final_inputs.load(project,'grammar'),grounded_items=final_inputs.load(project,'grounded'),
        narrative_items=final_inputs.load(project,'narrative'),copy_pairs=final_inputs.load(project,'copy'),baselines=FrozenBaselines(project))


def evaluate(project,completion,*,catalog,quality,pilot,time_budget,dev_verify,copy_verify,heartbeat,selection=None):
    project=Path(project).resolve(strict=True)
    deadline=numerical_snapshot.authority(project,time.time())
    if time_budget.deadline!=deadline:raise ValueError('Final evaluator deadline differs from original authority')
    prepared=final_checkpoint.prepare(completion,catalog=catalog,quality=quality,pilot=pilot,time_budget=time_budget,
                                      dev_verify=dev_verify,copy_verify=copy_verify)
    if selection is not None and prepared['selection']!=selection:raise ValueError('Final ticket changed development selection')
    # Only this point may open final documents or diagnostics.
    data=inputs(project);config=data.pop('config');expected=catalog.args['expected']
    actual=hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest()
    if expected['config_hash']!=actual or expected['tokenizer_hash']!=PINS['tokenizer-8192/manifest.json']:
        raise ValueError('Final model/tokenizer differ from selected checkpoint')
    def tick():
        if time_budget.terminal() is not None or time.time()>=deadline or time_budget.charged()>=time_budget.cap:
            raise ValueError('Final evaluator time exhausted')
        heartbeat()
    tick();started=time.monotonic();bound=BoundLogits(prepared,_MLX(prepared,config))
    result=final_diagnostics.execute(context=prepared['context'],logits=bound,heartbeat=tick,**data)
    bound.check();tick()
    assessment=final_diagnostics.assess(result,context=prepared['context'],**data)
    if catalog.args['ledger'].snapshot()!=prepared['retained_ledger_snapshot']:raise ValueError('Training ledger changed during final evaluation')
    if hashlib.sha256((Path(prepared['checkpoint_path'])/'manifest.json').read_bytes()).hexdigest()!=prepared['checkpoint_sha256']:
        raise ValueError('Selected checkpoint changed during final evaluation')
    raw=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode()
    receipt={'result_sha256':hashlib.sha256(raw).hexdigest(),'selection':prepared['selection'],
        'termination':prepared['termination'],'parameter_sha256':prepared['parameter_sha256'],
        'retained_ledger_snapshot':prepared['retained_ledger_snapshot'],'forward_calls':bound.calls,
        'evaluation_seconds':time.monotonic()-started,'status':assessment['status'],'final_research_pass':False}
    return raw,receipt,assessment
