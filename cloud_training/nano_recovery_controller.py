"""Durable single-writer executor for an explicitly approved recovery task graph.

No provisioning API is called by this controller. Approved commands and all source
files must be bound before use; no shell interpolation or automatic retry. The
caller supplies real qualification receipts through the existing recovery gate.
Human/agent semantic-review tasks are explicit barriers, never inferred from exit0.
"""
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import time
from cloud_training.nano_recovery_gate import inspect, digest, timestamp
from cloud_training.nano_quality import atomic_report, assess
from cloud_training.nano_fit_readiness import score_fit

def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def safe(root,name):
    if not isinstance(name,str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Canonical relative path required')
    p=root/name
    if not p.resolve().is_relative_to(root) or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('Symlink/path escape forbidden')
    return p

def validate_graph(spec,root):
    tasks=spec.get('tasks',[]);seen=set()
    if not tasks:raise ValueError('Empty task graph')
    outputs=set();ancestors={};review_ids=set()
    for task in tasks:
        ident=task['id']
        if not isinstance(ident,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',ident) or ident in seen:raise ValueError('Duplicate/invalid task')
        if any(x not in seen for x in task.get('needs',[])):raise ValueError('Dependencies must precede task')
        ancestors[ident]=set(task.get('needs',[]))
        for dependency in task.get('needs',[]):ancestors[ident].update(ancestors[dependency])
        seen.add(ident)
        if task['stage'] not in ('qualification','fit','curriculum'):raise ValueError('Release is outside pilot controller')
        if task['kind'] not in ('command','fit_review','fit_batch_review','development_batch_review'):raise ValueError('Unknown task kind')
        if task['kind']=='fit_batch_review':review_ids.add(ident)
        if spec.get('path')=='no_resume_diagnostic' and task['stage']=='curriculum':raise ValueError('No-resume graph cannot include curriculum')
        if spec.get('training_inputs') and task['kind']=='command':
            operation=task.get('operation')
            expected={'train_fit':'fit','probe_fit':'fit','train_curriculum':'curriculum','probe_curriculum':'curriculum'}
            if operation not in expected or task['stage']!=expected[operation]:raise ValueError('Operation/stage mismatch')
            wanted=[spec['python'],'ganesh_recovery_task.py','--request',spec['controller_directory']+'/effective-request.json','--task',ident]
            if task['argv']!=wanted:raise ValueError('Unapproved task adapter argv')
            if task['stage']=='curriculum' and not (ancestors[ident]&review_ids):raise ValueError('Curriculum requires semantic review dependency')

        if task['kind']=='command':
            argv=task['argv']
            if not isinstance(argv,list) or len(argv)<2 or any(not isinstance(x,str) or not x for x in argv):raise ValueError('Explicit argv required')
            if argv[0] != spec['python']:raise ValueError('Only pinned Python executable allowed')
            # Every entry point must be a pinned local source, never -c, shell or arbitrary module.
            source=task['source'];safe(root,source)
            if source not in spec['files'] or argv[1]!=source:raise ValueError('Command source is not bound')
            if not (type(task['timeout_seconds']) is int and 1<=task['timeout_seconds']<=7200):raise ValueError('Bounded task timeout required')
        if task.get('result') and task['result'] not in task.get('outputs',[]):raise ValueError('Result must be a declared output')
        if task['kind'] in ('fit_review','fit_batch_review','development_batch_review'):
            for key in ('review','raw','suite'):safe(root,task[key])
            if task['raw'] not in outputs or task['suite'] not in spec['files']:raise ValueError('Review must consume a prior output and bound suite')
            if task['kind'] in ('fit_batch_review','development_batch_review') and task.get('producer_result') not in outputs:raise ValueError('Batch review requires prior training result')
            if task['kind']=='fit_batch_review' and task.get('development_suite') not in spec['files']:raise ValueError('Batch review requires bound development suite')
            if task['kind']=='development_batch_review' and task.get('protected_suite') not in spec['files']:raise ValueError('Protected suite must be bound')
        for name in task.get('outputs',[]):
            safe(root,name)
            if name in outputs:raise ValueError('Output reused across tasks')
            if name in spec['files']:raise ValueError('Cannot overwrite bound input')
            for protected in spec.get('protected_roots',[]):
                if safe(root,name).is_relative_to(safe(root,protected)):raise ValueError('Output inside protected inputs')
            outputs.add(name)
    if spec.get('training_inputs'):
        for group in ('fit_inputs','curriculum_inputs'):
            if any(name not in spec['files'] for name in spec[group].values()):raise ValueError('All data/suite/contract inputs must be bound')
        common=spec['training_inputs'];base=common['base']+'/manifest.json'
        if spec['files'].get(base)!=common['base_manifest_sha256']:raise ValueError('Base manifest not bound')
    return tasks

class Controller:
    def __init__(self,root,request_path,directory):
        self.root=Path(root).resolve();self.request_path=Path(request_path).resolve()
        self.directory=Path(directory).resolve()
        if not self.directory.is_relative_to(self.root):raise ValueError('Controller state must be inside workspace')
        self.directory.mkdir(parents=True,exist_ok=True)
        self.request=json.loads(self.request_path.read_text())
        self.tasks=validate_graph(self.request,self.root)
        if self.request.get('controller_directory') and self.directory!=safe(self.root,self.request['controller_directory']):raise ValueError('State directory differs from approved controller path')
        self.spec_hash=canonical({k:v for k,v in self.request.items() if k not in ('authorization','evidence')})
        self.statepath=self.directory/'state.json'
    def _state(self):
        if not self.statepath.exists():return {'spec_sha256':self.spec_hash,'completed':{},'running':None,'failed':None,'events':[],'evidence':{}}
        state=json.loads(self.statepath.read_text())
        if state['spec_sha256']!=self.spec_hash:raise ValueError('Campaign spec changed across restart')
        for task in state['completed'].values():
            for name,h in task['outputs'].items():
                if digest(safe(self.root,name))!=h:raise ValueError('Completed task output changed')
        return state
    def _save(self,state,event):
        state['events'].append({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),**event})
        atomic_report(self.statepath,state)
    def next(self):
        with (self.directory/'writer.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            state=self._state()
            if state['running'] is not None:raise ValueError('Interrupted in-flight task: reconciliation required; never auto-retry')
            if state['failed'] is not None:return {'status':'hold_failed_task','task':state['failed']}
            task=next((t for t in self.tasks if t['id'] not in state['completed']),None)
            if task is None:return {'status':'complete_not_release_accepted'}
            if not all(d in state['completed'] for d in task.get('needs',[])):raise ValueError('Unmet dependency')
            self.request['evidence']={**self.request.get('evidence',{}),**state.get('evidence',{})}
            # Local semantic review is permitted after VM STOP/lease expiry. It cannot
            # execute compute: the subsequent command still re-enters the full gate.
            if task['kind']!='command':
                if any(digest(safe(self.root,n))!=h for n,h in self.request['files'].items()):raise ValueError('Bound review inputs changed')
                if task['kind']=='fit_review':return self._review(task,state)
                if task['kind']=='fit_batch_review':return self._batch_review(task,state)
                return self._development_review(task,state)
            decision=inspect(self.root,self.request,task['stage'])
            if not decision['allowed']:return {'status':'hold_gate','decision':decision}
            # Resolve no placeholders: input/output paths and argv were frozen in approval.
            for n in task.get('outputs',[]):
                if safe(self.root,n).exists():raise FileExistsError('Refuse existing task output: '+n)
            budget=(timestamp(self.request['provider_stop_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()-self.request['backup_reserve_seconds']
            if task['timeout_seconds']+self.request.get('termination_grace_seconds',600)>budget:return {'status':'hold_insufficient_stage_time'}
            if self.request.get('controller_directory'):
                atomic_report(safe(self.root,self.request['controller_directory']+'/effective-request.json'),self.request)
            state['running']={'id':task['id'],'argv_sha256':canonical(task['argv'])}
            self._save(state,{'event':'intent_before_spawn','task':task['id']})
            log=self.directory/(task['id']+'.log')
            try:
                with log.open('x') as stream:
                    child=subprocess.Popen(task['argv'],cwd=self.root,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                    try:rc=child.wait(timeout=task['timeout_seconds'])
                    except BaseException:
                        os.killpg(child.pid,signal.SIGTERM)
                        try:child.wait(timeout=min(600,self.request.get('termination_grace_seconds',600)))
                        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                        raise
                if rc:raise RuntimeError('Task exit '+str(rc))
                outputs={n:digest(safe(self.root,n)) for n in task.get('outputs',[])}
                # A declared JSON result must match its frozen expected status; exit0 alone is never enough.
                if task.get('result'):
                    result=json.loads(safe(self.root,task['result']).read_text())
                    if result.get('status')!=task['expected_status']:raise ValueError('Task result status failed')
                state['completed'][task['id']]={'outputs':outputs,'kind':'command'}
                state['running']=None;self._save(state,{'event':'task_completed','task':task['id']})
                return {'status':'task_completed','task':task['id']}
            except BaseException as exc:
                state['failed']={'id':task['id'],'error':repr(exc)};state['running']=None
                self._save(state,{'event':'task_failed','task':task['id']})
                raise
    def _development_review(self,task,state):
        reviewpath=safe(self.root,task['review'])
        if not reviewpath.exists():return {'status':'waiting_for_semantic_review','path':task['review']}
        indexpath=safe(self.root,task['raw']);index=json.loads(indexpath.read_text());review=json.loads(reviewpath.read_text())
        if index.get('status')!='complete_requires_review' or review.get('index_sha256')!=digest(indexpath):raise ValueError('Development batch changed')
        if not review.get('reviewer') or not review.get('reviewed_utc'):raise ValueError('Review provenance required')
        suitepath=safe(self.root,task['suite']);suite=json.loads(suitepath.read_text())
        result=json.loads(safe(self.root,task['producer_result']).read_text())
        expected_steps=[-1]+sorted(set([result['best_development_step'],result['step']]))
        items=index['candidates'];grades=review.get('candidates',[])
        if [(i['scope'],i['step']) for i in items]!=[(kind,x) for kind in ('development','protected') for x in expected_steps] or len(grades)!=len(items):raise ValueError('Baseline/best/last full review required')
        expected=[(s['id'],j) for s in suite['sessions'] for j in range(len(s['turns']))]
        outputs={task['raw']:digest(indexpath),task['review']:digest(reviewpath)};scores=[]
        for item,grade in zip(items,grades):
            suitepath=safe(self.root,task['protected_suite'] if item['scope']=='protected' else task['suite']);suite=json.loads(suitepath.read_text())
            expected=[(s['id'],j) for s in suite['sessions'] for j in range(len(s['turns']))]
            specs=[t for s in suite['sessions'] for t in s['turns']]
            rawpath=safe(self.root,item['path']);raw=json.loads(rawpath.read_text())
            if digest(rawpath)!=item['sha256'] or grade.get('raw_sha256')!=item['sha256'] or grade.get('checkpoint_manifest_sha256')!=raw.get('checkpoint_manifest_sha256'):raise ValueError('Wrong reviewed development output')
            if raw.get('suite_sha256')!=digest(suitepath) or raw.get('status')!='development_checks_complete':raise ValueError('Incomplete development run')
            records=grade.get('records',[])
            if [(r.get('session'),r.get('turn')) for r in raw['records']]!=expected or [(r.get('session'),r.get('turn')) for r in records]!=expected or not all(type(r.get('pass')) is bool and r.get('reason') for r in records):raise ValueError('Missing ordered development turns')
            scores.append({'scope':item['scope'],'step':item['step'],'passed_turns':sum(g['pass'] and r['result'].get('status')=='complete' and (item['scope']!='protected' or assess(r['result'],spec)['automated_pass']) for g,r,spec in zip(records,raw['records'],specs)),'total_turns':len(expected)})
            outputs[item['path']]=item['sha256']
        state['completed'][task['id']]={'kind':'development_batch_review','outputs':outputs,'scores':scores,'quality_accepted':False}
        self._save(state,{'event':'development_review_completed_no_promotion','task':task['id']})
        return {'status':'review_complete_not_release','scores':scores}

    def _batch_review(self,task,state):
        reviewpath=safe(self.root,task['review'])
        if not reviewpath.exists():return {'status':'waiting_for_semantic_review','path':task['review']}
        indexpath=safe(self.root,task['raw']);index=json.loads(indexpath.read_text())
        review=json.loads(reviewpath.read_text())
        if index.get('status')!='complete_requires_review' or review.get('index_sha256')!=digest(indexpath):raise ValueError('Incomplete or changed probe batch')
        if not review.get('reviewer') or not review.get('reviewed_utc'):raise ValueError('Review provenance required')
        candidates=index['candidates'];judgments=review.get('candidates',[])
        result=json.loads(safe(self.root,task['producer_result']).read_text())
        best,last=result['best_development_step'],result['step']
        fit_steps=sorted(set([best,last]+[x for x in (0,16,32,64) if x<=last]))
        expected=[('exposed_fit',x) for x in fit_steps]+[('development',x) for x in sorted(set([0,best,last]))]
        if [(x['scope'],x['step']) for x in candidates]!=expected:raise ValueError('Missing/reordered checkpoint probes')
        if len({x['path'] for x in candidates})!=len(candidates):raise ValueError('Repeated raw probe path')
        if len(candidates)!=len(judgments) or not candidates:raise ValueError('All checkpoint reviews required')
        passing=[];outputs={task['raw']:digest(indexpath),task['review']:digest(reviewpath)}
        for item,grade in zip(candidates,judgments):
            path=safe(self.root,item['path']);raw=json.loads(path.read_text())
            if digest(path)!=item['sha256'] or grade.get('raw_sha256')!=item['sha256']:raise ValueError('Raw review binding mismatch')
            if grade.get('checkpoint_manifest_sha256')!=raw.get('checkpoint_manifest_sha256'):raise ValueError('Review checkpoint mismatch')
            suitepath=safe(self.root,task['suite'] if item['scope']=='exposed_fit' else task['development_suite'])
            suite=json.loads(suitepath.read_text())
            if raw.get('suite_sha256')!=digest(suitepath):raise ValueError('Wrong probe suite')
            expected=[(s['id'],i) for s in suite['sessions'] for i in range(len(s['turns']))]
            records=grade.get('records',[])
            if [(r.get('session'),r.get('turn')) for r in records]!=expected or not all(type(r.get('pass')) is bool and bool(r.get('reason')) for r in records):raise ValueError('Incomplete ordered semantic review')
            if item['scope']=='exposed_fit':
                score=score_fit(suite,raw,records)
                if score['fit_go']:passing.append(item['step'])
            elif raw.get('status')!='development_checks_complete':raise ValueError('Development probe incomplete')
            outputs[item['path']]=item['sha256']
        if not passing:
            state['failed']={'id':task['id'],'reason':'no_checkpoint_passed_frozen_fit'};self._save(state,{'event':'review_failed','task':task['id']})
            return {'status':'hold_fit_failed'}
        proof=self.directory/'fit-semantic-review-receipt.json'
        atomic_report(proof,{'status':'pass','check':'fit_semantic_review','spec_sha256':self.spec_hash,
                            'review_sha256':digest(reviewpath),'index_sha256':digest(indexpath),'earliest_passing_step':min(passing),'release_eligible':False})
        rel=str(proof.relative_to(self.root));outputs[rel]=digest(proof)
        state.setdefault('evidence',{})['fit_semantic_review']={'path':rel,'sha256':digest(proof)}
        state['completed'][task['id']]={'kind':'fit_batch_review','outputs':outputs}
        self._save(state,{'event':'all_probe_reviews_complete','task':task['id']})
        return {'status':'review_passed_not_release','earliest_passing_step':min(passing)}

    def _review(self,task,state):
        reviewpath=safe(self.root,task['review'])
        if not reviewpath.exists():return {'status':'waiting_for_semantic_review','path':task['review']}
        review=json.loads(reviewpath.read_text());rawpath=safe(self.root,task['raw']);suitepath=safe(self.root,task['suite'])
        if (review.get('raw_sha256')!=digest(rawpath) or review.get('suite_sha256')!=digest(suitepath)
            or not review.get('reviewer') or not review.get('reviewed_utc')):raise ValueError('Unbound semantic review')
        raw=json.loads(rawpath.read_text());suite=json.loads(suitepath.read_text())
        if raw.get('suite_sha256')!=digest(suitepath):raise ValueError('Raw/suite mismatch')
        if review.get('checkpoint_manifest_sha256')!=raw.get('checkpoint_manifest_sha256'):raise ValueError('Wrong reviewed checkpoint')
        score=score_fit(suite,raw,review['records'])
        if not score['fit_go']:
            state['failed']={'id':task['id'],'reason':'fit_semantic_failure','score':score};self._save(state,{'event':'review_failed','task':task['id']})
            return {'status':'hold_fit_failed','score':score}
        state['completed'][task['id']]={'kind':'fit_review','outputs':{task['raw']:digest(rawpath),task['review']:digest(reviewpath),task['suite']:digest(suitepath)}}
        self._save(state,{'event':'review_passed','task':task['id']})
        return {'status':'review_passed_not_release','score':score}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.')
    p.add_argument('--request',required=True);p.add_argument('--state',required=True)
    p.add_argument('--execute-next',action='store_true');a=p.parse_args()
    c=Controller(a.root,a.request,a.state)
    if not a.execute_next:
        print(json.dumps({'status':'validated_graph_no_execution','tasks':len(c.tasks),'spec_sha256':c.spec_hash}));return 0
    result=c.next();print(json.dumps(result,indent=2));return 0 if result['status'] in ('task_completed','review_passed_not_release','review_complete_not_release','complete_not_release_accepted') else 2
if __name__=='__main__':raise SystemExit(main())
