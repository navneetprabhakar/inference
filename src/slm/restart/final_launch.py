"""One supervised final dispatch after clean candidate continuation.

No automatic entrypoint or retry. Uses remaining original time, read-only state
copies and separate final custody. Semantic review remains an explicit next step.
"""
import json,os,sys,time
from pathlib import Path
from . import candidate_snapshot,final_custody,final_state,custody,known_leakage
from .candidate_launch import environment
from .supervisor import TimeBudget,supervise,atomic_json
from .ledger import Ledger


def launch(binding):
    project=Path(binding['project']).resolve(strict=True);candidate=Path(binding['output']).absolute()
    if candidate!=project/'restart/execution-v1/candidate-run-v1' or candidate.resolve(strict=True)!=candidate:
        raise ValueError('Unowned final candidate')
    if json.loads((candidate/'parent-binding.json').read_bytes())!=binding:raise ValueError('Changed original parent binding')
    bound=candidate_snapshot.verify(project,candidate/'snapshot.json',expected_sha256=binding['snapshot_sha256'],now=time.time())
    if binding['identity']!='candidate-v1:'+binding['snapshot_sha256'] or binding['deadline']!=bound['original_deadline']:
        raise ValueError('Changed final run contract')
    output=candidate/'final-run-v1';ticket_path=candidate/'final-ticket.json';frozen=candidate/'final-state-v1'
    if any(path.exists() for path in (output,ticket_path,frozen)):raise FileExistsError('Final attempt already reserved; no retry')
    if any((candidate/name).exists() for name in ('parent-stop.json','worker-stop.json','final-stop.json')):
        raise ValueError('Failed training cannot open final')
    phase='continuation-recovery' if (candidate/'continuation-recovery-ticket.json').exists() else 'continuation'
    completion_path=candidate/(phase+'-completion.json');completion=json.loads(completion_path.read_bytes())
    prior=json.loads((candidate/(phase+'-supervisor.json')).read_bytes())
    if (prior['status']!='PASS' or completion['status'] not in ('NORMAL_BUDGET_END','PLATEAU_END','WORK_BUDGET_END')
            or type(completion['targets']) is not int or completion['targets']<2000000):
        raise ValueError('No clean completed continuation')
    if not (candidate/'time.sqlite').is_file():raise ValueError('Missing original time budget')
    clock=TimeBudget(candidate/'time.sqlite',identity=binding['identity'],seconds_cap=129600,deadline_utc=binding['deadline'])
    sources={}
    try:
        if clock.terminal() is not None or not 0<clock.charged()<clock.cap or time.time()>=clock.deadline:
            raise ValueError('Original final time budget unavailable')
        leakage=known_leakage.verify(project)
        output.mkdir()
        atomic_json(output/'known-leakage.json',leakage)
        for name,file in (('ledger','exposures.sqlite'),('quality','quality.sqlite'),('pilot','pilot.sqlite'),('catalog','catalog.sqlite')):
            # Backup-only source handles never initialize or migrate training DBs.
            handle=Ledger.__new__(Ledger);handle.db=final_state.readonly(candidate/file,immutable=False);sources[name]=handle
        state_pin=final_state.freeze(frozen,**sources)
        profile=candidate/'final-worker.sb';profile.write_text(final_custody.profile(project,candidate,output))
        ticket=dict(schema=1,project=str(project),candidate=str(candidate),output=str(output),identity=binding['identity'],
            snapshot_sha256=binding['snapshot_sha256'],state_sha256=state_pin,completion_sha256=final_state.digest(completion_path),
            training_phase=phase,selection=completion['best'],deadline=binding['deadline'],parent_pid=os.getpid(),profile_sha256=final_state.digest(profile))
        with ticket_path.open('x') as f:json.dump(ticket,f,indent=2);f.flush();os.fsync(f.fileno())
        result=supervise(custody.command(profile,[sys.executable,'-m','slm.restart.final_worker',str(ticket_path),final_state.digest(ticket_path)]),
            cwd=output,env=environment(project,output),heartbeat=output/'heartbeat.json',budget=clock,
            receipt=output/'supervisor.json',active_ceiling=129600)
        if result['status']!='PASS' or clock.terminal() is not None:raise ValueError('Final worker failed supervision')
        done=json.loads((output/'completion.json').read_bytes());receipt=json.loads((output/'receipt.json').read_bytes())
        for name,key in (('raw.json','raw_sha256'),('receipt.json','receipt_sha256'),('assessment.json','assessment_sha256'),('review-packet.json','review_packet_sha256')):
            if final_state.digest(output/name)!=done[key]:raise ValueError('Changed final output bundle')
        if (done['status']!='NARRATIVE_REVIEW_REQUIRED' or done['final_research_pass'] is not False
                or receipt['selection']!=ticket['selection'] or receipt['result_sha256']!=done['raw_sha256']):
            raise ValueError('Unbound final worker completion')
        if sources['ledger'].snapshot()!=receipt['retained_ledger_snapshot'] or final_state.digest(completion_path)!=ticket['completion_sha256']:
            raise ValueError('Training state changed during final scoring')
        candidate_snapshot.verify(project,candidate/'snapshot.json',expected_sha256=binding['snapshot_sha256'],now=time.time())
        atomic_json(output/'parent-completion.json',done)
        return done
    except BaseException as error:
        clock.stop('Final evaluation failed: '+str(error))
        atomic_json(candidate/'final-stop.json',{'status':'STOP','reason':str(error),'final_research_pass':False})
        raise
    finally:
        for handle in sources.values():handle.db.close()
        clock.db.close()
