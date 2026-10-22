"""Numerical-suite orchestration on supplied parameters; no initialization API.

The launcher owns approval/hash validation, custody and supervisor lifetime.
This module stops the shared attempt on any check failure; no automatic retries.
"""
from pathlib import Path
import numpy as np
from .supervisor import atomic_json
from .numerical_results import aggregate
from . import numerical_forward,numerical_gradients,numerical_oracles,numerical_segments,numerical_optimizer,numerical_trajectory,numerical_checkpoint

class NumericalCheckFailure(RuntimeError):pass

class Runner:
    def __init__(self,adapters,config,fixtures,*,budget,output,expected_ids):
        if set(adapters)!= {'mlx','torch'}:raise ValueError('Both scoped adapters required')
        if len(expected_ids)!=40 or len(set(expected_ids))!=40:raise ValueError('Incomplete case contract')
        if any(a.budget is not budget for a in adapters.values()):raise ValueError('Adapters must share work budget')
        self.adapters=adapters;self.config=config;self.fixtures=fixtures;self.budget=budget
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=True)
        self.expected=set(expected_ids);self.groups=[];self.cases={};self.started=False;self.pretrajectory_complete=False;self.trajectories_started=False
        if (self.output/'progress.json').exists():raise FileExistsError('Numerical results already exist; no in-place retry')

    def _persist(self,status,error=None):
        atomic_json(self.output/'progress.json',{'status':status,'required_cases':40,
            'reported_cases':len(self.cases),'cases':self.cases,'error':error,
            'charged_events':len(self.budget.events(require_complete=False)),
            'scope':'Partial suite progress only; never a launch authorization.'})

    def accept(self,group):
        if not isinstance(group,dict) or not isinstance(group.get('cases'),dict) or not group['cases']:
            raise NumericalCheckFailure('Empty or malformed check group')
        # Validate numeric claims and full accumulated ID uniqueness, allowing only
        # the expected missing cases while this is still a partial run.
        aggregate(sorted(self.expected),self.groups+[group])
        for key,value in group['cases'].items():
            if key not in self.expected or key in self.cases or type(value.get('passed')) is not bool:
                raise NumericalCheckFailure('Unknown/duplicate/malformed case result')
            self.cases[key]=value
        self.groups.append(group);self._persist('RUNNING')
        failed=[k for k,v in group['cases'].items() if not v['passed']]
        if failed:raise NumericalCheckFailure('Failed numerical checks: '+', '.join(failed))

    def pretrajectory(self):
        if self.started:raise NumericalCheckFailure('No repeated numerical attempt')
        self.started=True;self._persist('RUNNING')
        try:
            b=self.fixtures['batches'];padded=b['padded']
            def forward(name,x,**kwargs):return self.adapters[name].forward(x,**kwargs)
            def gradient(name,batch,**kwargs):return self.adapters[name].gradient(batch,**kwargs)
            def ce(name,x,y):return self.adapters[name].cross_entropy(x,y)
            def charged(kind):return sum(e['positions'] for e in self.budget.events(require_complete=False) if e['kind']==kind)
            before=charged('forward');group=numerical_forward.run(self.config,b,forward)
            if charged('forward')-before!=group['forward_input_positions']:raise NumericalCheckFailure('Forward budget reconciliation failed')
            self.accept(group)
            shapes={k:tuple(v.shape) for k,v in self.adapters['torch'].params.items()}
            before=charged('gradient');group=numerical_gradients.run(b,shapes,gradient)
            if charged('gradient')-before!=group['gradient_input_positions']:raise NumericalCheckFailure('Gradient budget reconciliation failed')
            self.accept(group)
            before=charged('ce_gradient');group=numerical_oracles.cross_entropy_cases(ce)
            if charged('ce_gradient')-before!=group['logit_target_positions']:raise NumericalCheckFailure('CE budget reconciliation failed')
            self.accept(group)
            self.accept({'cases':numerical_oracles.tied_embedding_case(lambda name:self.adapters[name].tied_embedding(padded))})
            params=self.adapters['torch'].impl.export(self.adapters['torch'].params)
            analytic={name:adapter.gradient(padded)[1] for name,adapter in self.adapters.items()}
            self.accept(numerical_oracles.finite_difference_case(params,analytic,
                lambda name,index,value:self.adapters['torch'].loss64(padded,name,index,value)))
            self.accept(numerical_segments.run(self.fixtures['long_documents'],self.output))
            self.accept({'cases':numerical_optimizer.accumulation_cases(b,shapes,gradient)})
            self.accept({'cases':numerical_optimizer.schedule_case()})
            if len(self.cases)!=25:raise NumericalCheckFailure('Pretrajectory case denominator mismatch')
            self.pretrajectory_complete=True
            self._persist('PRETRAJECTORY_CHECKS_COMPLETE_TRAJECTORIES_PENDING')
            return list(self.groups)
        except BaseException as error:
            self.budget.stop(type(error).__name__+': '+str(error))
            self._persist('FAILED',type(error).__name__+': '+str(error))
            raise

    def trajectories(self,*,expected):
        """Capture real replay evidence; parent must supply supervisor results later."""
        if not self.pretrajectory_complete or self.trajectories_started:
            raise NumericalCheckFailure('Trajectories require one successful pretrajectory phase')
        self.trajectories_started=True
        try:
            results={}
            for name in ('mlx','torch'):
                results[name]=numerical_trajectory.run(self.adapters[name],self.fixtures['batches']['fit'],
                    self.output/name,expected=expected)
            # Persist raw evidence before judging it so failures remain inspectable.
            def serial(value):
                if isinstance(value,np.ndarray):return value.tolist()
                if isinstance(value,np.generic):return value.item()
                if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
                if isinstance(value,(list,tuple)):return [serial(v) for v in value]
                return value
            atomic_json(self.output/'trajectory-evidence.json',serial(results))
            self.accept({'cases':numerical_optimizer.trajectory_cases({k:v['trajectory'] for k,v in results.items()})})
            self.accept(numerical_checkpoint.run({k:v['checkpoint'] for k,v in results.items()}))
            if len(self.cases)!=34:raise NumericalCheckFailure('Worker case denominator mismatch')
            reference=results['mlx']
            pending=dict(fit_losses={k:v['fit'] for k,v in results.items()},work_events=self.budget.events(),
                complete_checkpoint=reference['checkpoint_path'],checkpoint_identity=reference['checkpoint_identity'],
                checkpoint_expected=reference['checkpoint_expected'])
            atomic_json(self.output/'integrity-inputs.json',pending)
            self._persist('WORKER_CHECKS_COMPLETE_SUPERVISOR_INTEGRITY_PENDING')
            return pending
        except BaseException as error:
            self.budget.stop(type(error).__name__+': '+str(error))
            self._persist('FAILED',type(error).__name__+': '+str(error))
            raise
