"""Candidate lifecycle over supplied, preflighted state; no initializer/entrypoint.

Parent/worker launch and supervision are required. This controller persists stop
state, checkpoints, raw evaluations and pilot decisions around every transition.
"""
import hashlib,json,time,math
from pathlib import Path
from . import checkpoint_binding,state,candidate_evaluation,development_loss,full_diagnostics,pilot_evidence
from .supervisor import atomic_json
from .monitor import StopRun
from .pilot_gate import PilotRejected
from .ledger import WorkBudgetExhausted


class Loop:
    def __init__(self,*,project,output,identity,expected,config,schedule,store,ledger,quality,pilot,catalog,
                 measurements,time_budget,backend,params,moments,monitor,rng,step,targets,heartbeat,experiment_start):
        self.__dict__.update(locals());del self.self
        self.output=Path(output);self.project=Path(project)
        self.last_checkpoint_active=time_budget.charged();self.checkpoint_path=None
        self.inputs={}
        schedule.resume_position(step=step,cursor=schedule.update_cursors[step],targets=targets)
        if quality.position()!=step:raise ValueError('Loop/quality cursor mismatch')
        quality.require_monitor(monitor)

    def tick(self):
        if self.time_budget.terminal() is not None:raise StopRun('Terminal supervised clock')
        if time.time()>=self.time_budget.deadline or self.time_budget.charged()>=self.time_budget.cap:
            raise StopRun('Candidate time budget exhausted')
        if self.targets<=2000000 and self.time_budget.charged()>=7200 and self.pilot.decision() is None:
            raise StopRun('Pilot time budget exhausted')
        self.heartbeat()

    def save(self):
        self.tick()
        # Unique publication sequence also covers resumed/replayed logical steps.
        sequence=self.catalog.db.execute('SELECT count(*) FROM checkpoints').fetchone()[0]+1
        path=checkpoint_binding.save(self.output/'checkpoints',f'state-{sequence:06d}-step-{self.step:06d}',
            params=self.params,moments=self.moments,backend=self.backend,monitor=self.monitor,rng=self.rng,
            step=self.step,targets=self.targets,schedule=self.schedule,ledger=self.ledger,
            identity=self.identity,expected=self.expected)
        self.catalog.register(path.name);self.checkpoint_path=path
        self.last_checkpoint_active=self.time_budget.charged()
        self.tick();return path

    def verifier(self,event):
        if event not in self.inputs:self.inputs[event]=candidate_evaluation.inputs(self.project,event)
        data={k:v for k,v in self.inputs[event].items() if k!='config'}
        if event=='dev_loss_checkpoint':return development_loss.quality_verifier(data['dev_store'])
        if event=='full_development_diagnostics':return full_diagnostics.verifier(**data)
        if event=='copying_probes':return full_diagnostics.copying_verifier(**data)
        raise ValueError('Unknown evaluation')

    def evaluate_pending(self):
        self.catalog.reconcile_scores(self.quality)
        pending=self.quality.pending()
        if not pending:return
        path=self.catalog.evaluation_checkpoint(self.quality)
        if path is None and self.checkpoint_path is not None:
            restored=checkpoint_binding.restore(self.checkpoint_path,**self.catalog.args)
            if (restored['metadata']['step']==self.step and not any(restored['charged_work_after_checkpoint'].values())):
                path=self.checkpoint_path
        if path is None:path=self.save()
        self.checkpoint_path=path
        pin=state.digest(path/'manifest.json')
        for event in pending:
            self.tick()
            context=dict(identity=self.identity,schedule_sha256=self.schedule.sha256,step=self.step,targets=self.targets,
                         checkpoint_sha256=pin,event=event)
            stem=f'{path.name}-{event}';result_path=self.output/(stem+'.json')
            receipt_path=self.output/(stem+'-receipt.json')
            if result_path.exists() or receipt_path.exists():
                if not result_path.is_file() or not receipt_path.is_file():raise ValueError('Incomplete interrupted evaluation publication')
                raw=result_path.read_bytes();receipt=json.loads(receipt_path.read_bytes())
                from .evaluation_checkpoint import prepare
                prepared=prepare(path,checkpoint_root=self.output/'checkpoints',manifest_sha256=pin,identity=self.identity,
                    expected=self.expected,shapes=self.catalog.args['shapes'],schedule=self.schedule,ledger=self.ledger,context=context,quality=self.quality)
                metrics=self.verifier(event)(raw,context)
                if (receipt.get('checkpoint_sha256')!=pin or receipt.get('result_sha256')!=hashlib.sha256(raw).hexdigest()
                        or receipt.get('parameter_sha256')!=prepared['parameter_sha256'] or receipt.get('metrics')!=metrics
                        or type(receipt.get('forward_calls')) is not int or receipt['forward_calls']<=0
                        or type(receipt.get('evaluation_seconds')) not in (int,float) or not math.isfinite(receipt['evaluation_seconds']) or receipt['evaluation_seconds']<0):
                    raise ValueError('Unverified interrupted evaluation receipt')
            else:
                raw,receipt=candidate_evaluation.evaluate(self.project,path,checkpoint_root=self.output/'checkpoints',
                    manifest_sha256=pin,identity=self.identity,expected=self.expected,schedule=self.schedule,ledger=self.ledger,
                    context=context,deadline=self.time_budget.deadline,heartbeat=self.tick,quality=self.quality)
                with result_path.open('xb') as f:
                    f.write(raw);f.flush();__import__('os').fsync(f.fileno())
                atomic_json(receipt_path,receipt)
            self.quality.accept(event,result_path,checkpoint_sha256=pin,verify=self.verifier(event))
            self.monitor=self.quality.overlay(self.monitor)
            if event=='dev_loss_checkpoint':self.catalog.score(path.name,self.quality)
            self.tick()
        self.catalog.prune()

    def decide_pilot(self):
        existing=self.pilot.decision()
        if existing is not None:
            if existing['result']['status']!='PILOT_METRIC_RULES_PASS':raise PilotRejected('Persistent pilot rejection')
            return existing
        if self.checkpoint_path is None:raise ValueError('Missing pilot checkpoint')
        evidence,provenance=pilot_evidence.collect(barrier=self.quality,measurements=self.measurements,time_budget=self.time_budget,
            elapsed_seconds=time.time()-self.experiment_start,target_cap=self.schedule.target_cap,
            dev_verify=self.verifier('dev_loss_checkpoint'),full_verify=self.verifier('full_development_diagnostics'))
        atomic_json(self.output/'pilot-evidence-provenance.json',provenance)
        decision=self.pilot.decide(evidence,checkpoint_sha256=state.digest(self.checkpoint_path/'manifest.json'))
        if decision['result']['status']!='PILOT_METRIC_RULES_PASS':raise PilotRejected(decision['result']['reason'])
        return decision

    def run(self,*,stop_after_pilot=True):
        try:
            self.evaluate_pending()
            if self.targets==2000000:
                self.decide_pilot()
                if stop_after_pilot:return self.finish('PILOT_PASS')
            for update in self.schedule.updates[self.step:]:
                self.tick()
                reservation=f'work-{self.ledger.totals()["updates_reserved"]+1:06d}'
                result=pilot_evidence.execute_measured(update,measurements=self.measurements,time_budget=self.time_budget,
                    store=self.store,ledger=self.ledger,monitor=self.monitor,params=self.params,moments=self.moments,
                    backend=self.backend,backend_name='mlx',config=self.config,reservation_id=reservation,now=time.time(),
                    pilot_barrier=self.pilot,evaluation_barrier=self.quality)
                for key in ('params','moments','monitor','step','targets'):setattr(self,key,result[key])
                atomic_json(self.output/f'{reservation}-metrics.json',result['metrics'])
                self.evaluate_pending()
                if self.targets==2000000:
                    self.decide_pilot()
                    if stop_after_pilot:return self.finish('PILOT_PASS')
                if self.time_budget.charged()-self.last_checkpoint_active>=900:
                    self.save();self.catalog.prune()
            return self.finish('NORMAL_BUDGET_END')
        except BaseException as error:
            if isinstance(error,WorkBudgetExhausted):
                try:return self.finish_work_budget(error.proof)
                except BaseException as failed_stop:error=failed_stop
            if isinstance(error,StopRun) and str(error)=='development plateau':
                try:return self.finish_plateau()
                except BaseException as failed_stop:error=failed_stop
            reason=type(error).__name__+': '+str(error)
            # Persistent before returning control; no in-memory-only quality stop.
            self.time_budget.stop(reason)
            self.quality.db.execute('UPDATE barrier SET terminal=coalesce(terminal,?) WHERE id=1',(reason,))
            atomic_json(self.output/'worker-stop.json',{'status':'STOP','reason':reason,'step':self.step,'targets':self.targets,
                'active_seconds':self.time_budget.charged(),'final_research_pass':False})
            raise

    def finish_plateau(self):
        stop=self.quality.clean_stop()
        if stop is None or self.targets<=2000000 or self.checkpoint_path is None:
            raise ValueError('Missing post-pilot clean-stop evidence')
        path=self.checkpoint_path;pin=state.digest(path/'manifest.json')
        context=dict(stop['context'],event='copying_probes')
        if context['checkpoint_sha256']!=pin or context['step']!=self.step or context['targets']!=self.targets:
            raise ValueError('Clean-stop checkpoint mismatch')
        self.catalog.score(path.name,self.quality)
        return self.finish_stopped_copy('PLATEAU_END')

    def finish_work_budget(self,proof):
        self.ledger.verify_exhaustion(proof)
        path=self.save()
        self.quality.stop_work_budget(self.ledger,proof,checkpoint_sha256=state.digest(path/'manifest.json'))
        return self.finish_stopped_copy('WORK_BUDGET_END' if self.targets>=2000000 else 'PILOT_BUDGET_END')

    def finish_stopped_copy(self,status):
        stop=self.quality.clean_stop();path=self.checkpoint_path;pin=state.digest(path/'manifest.json')
        context=dict(stop['context'],event='copying_probes')
        if context['checkpoint_sha256']!=pin or context['step']!=self.step or context['targets']!=self.targets:
            raise ValueError('Clean-stop checkpoint mismatch')
        self.tick()
        raw,receipt=candidate_evaluation.evaluate(self.project,path,checkpoint_root=self.output/'checkpoints',
            manifest_sha256=pin,identity=self.identity,expected=self.expected,schedule=self.schedule,ledger=self.ledger,
            context=context,deadline=self.time_budget.deadline,heartbeat=self.tick,quality=self.quality)
        result_path=self.output/(path.name+'-termination-copying.json')
        with result_path.open('xb') as f:
            f.write(raw);f.flush();__import__('os').fsync(f.fileno())
        atomic_json(self.output/(path.name+'-termination-copying-receipt.json'),receipt)
        self.quality.accept_terminal_copy(result_path,verify=self.verifier('copying_probes'))
        self.tick();self.catalog.prune()
        return self.finish(status)

    def finish(self,status):
        result={'status':status,'step':self.step,'targets':self.targets,'active_seconds':self.time_budget.charged(),
                'checkpoint':str(self.checkpoint_path),'best':self.catalog.best(),'final_research_pass':False}
        atomic_json(self.output/'worker-completion.json',result)
        return result
