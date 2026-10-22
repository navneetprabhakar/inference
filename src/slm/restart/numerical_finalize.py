"""Parent-side numerical aggregation after the owned supervisor has returned.

The launcher supplies its in-memory supervisor result and open durable ledgers.
This is evidence aggregation, not a model initialization or training permit.
"""
import hashlib,json
from pathlib import Path
from . import numerical_integrity
from .numerical_results import aggregate
from .supervisor import atomic_json


def finalize(output,*,expected_ids,work_budget,time_budget,supervisor_result,supervisor_receipt):
    output=Path(output).resolve(strict=True)
    destination=output/'result.json'
    if destination.exists():raise FileExistsError('Numerical result already finalized')
    paths={'progress':output/'progress.json','inputs':output/'integrity-inputs.json',
           'supervisor':Path(supervisor_receipt),'trajectory':output/'trajectory-evidence.json'}
    hashes={}
    try:
        raw={key:path.read_bytes() for key,path in paths.items()}
        hashes={key:hashlib.sha256(value).hexdigest() for key,value in raw.items()}
        progress=json.loads(raw['progress']);inputs=json.loads(raw['inputs']);receipt=json.loads(raw['supervisor'])
        if receipt!=supervisor_result:raise ValueError('Supervisor receipt differs from parent result')
        if (receipt.get('status')!='PASS' or receipt.get('reason')!='worker_completed'
                or type(receipt.get('worker_returncode')) is not int or receipt['worker_returncode']!=0
                or type(receipt.get('worker_pid')) is not int or receipt['worker_pid']<=1):
            raise ValueError('Supervisor did not confirm successful worker exit')
        if time_budget.terminal() is not None or receipt.get('charged_active_seconds')!=time_budget.charged():
            raise ValueError('Supervisor time ledger mismatch or terminal stop')
        if (progress.get('status')!='WORKER_CHECKS_COMPLETE_SUPERVISOR_INTEGRITY_PENDING'
                or progress.get('required_cases')!=40 or progress.get('reported_cases')!=34
                or len(progress.get('cases',{}))!=34):raise ValueError('Incomplete worker phase')
        worker={'cases':progress['cases']}
        preliminary=aggregate(expected_ids,[worker])
        if preliminary['failed'] or len(preliminary['missing'])!=6:raise ValueError('Worker checks failed or incomplete')
        events=work_budget.events()
        if inputs.get('work_events')!=events:raise ValueError('Worker work accounting differs from durable ledger')
        checkpoint=Path(inputs['complete_checkpoint']).resolve(strict=True)
        if not checkpoint.is_relative_to(output/'mlx'/'checkpoints'):raise ValueError('Checkpoint outside owned trajectory')
        # Require worker-reported fit/checkpoint evidence to match retained captures.
        captures=json.loads(raw['trajectory'])
        if set(captures)!= {'mlx','torch'}:raise ValueError('Missing trajectory evidence')
        if inputs['fit_losses']!={k:v['fit'] for k,v in captures.items()}:raise ValueError('Fit evidence mismatch')
        for key in ('checkpoint_path','checkpoint_identity','checkpoint_expected'):
            target='complete_checkpoint' if key=='checkpoint_path' else key
            if inputs[target]!=captures['mlx'][key]:raise ValueError('Checkpoint evidence mismatch')
        final=numerical_integrity.run(**inputs,supervisor=receipt,output_root=output)
        result=aggregate(expected_ids,[worker,final])
        result['evidence_sha256']=hashes
        if result['status']!='NUMERICAL_CASE_RESULTS_PASS':
            work_budget.stop('Numerical final checks failed');time_budget.stop('Numerical final checks failed')
        atomic_json(destination,result)
        return result
    except BaseException as error:
        reason=type(error).__name__+': '+str(error)
        work_budget.stop(reason);time_budget.stop(reason)
        atomic_json(destination,{'status':'NUMERICAL_CASE_RESULTS_FAIL','error':reason,
            'evidence_sha256':hashes,'training_authorized_by_this_check':False})
        raise
