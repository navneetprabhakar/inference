"""Serial local paired raw-history assessment; no training or cloud operations."""
# Creator: Navneet Prabhakar
import fcntl,importlib.util,json,os,signal,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from slm.data.stream_hash import sha

PLAN=Path('configs/balanced-versus-foundation-assessment-v1.json')
ROOT=Path('data/balanced-versus-foundation-assessment-v1')

def save(path,value):
    path=Path(path);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n');tmp.replace(path)

def verify(plan):
    for name,h in plan['inputs'].items():
        if sha(name)!=h:raise ValueError('Frozen paired assessment input changed: '+name)

def main():
    p=json.loads(PLAN.read_text());verify(p)
    if len(sys.argv)>1:
        name=sys.argv[1]
        if name not in p['models']:raise ValueError('Bound endpoint required')
        from slm.english_language_stage import conversations
        conversations(p['models'][name]['path'],p['tokenizer'],ROOT/name,'mlx','default')
        verify(p);return
    if ROOT.exists():raise FileExistsError('Retain all prior outputs, no automatic replay')
    ROOT.mkdir();save(ROOT/'plan.json',p)
    with (ROOT/'execution.lock').open('x') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        save(ROOT/'process.json',dict(parent=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN)))
        try:
            for name in p['execution_order']:
                verify(p)
                with (ROOT/(name+'.log')).open('xb') as log:
                    child=subprocess.Popen([sys.executable,__file__,name],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    save(ROOT/'progress.json',dict(model=name,child=child.pid,phase='generating',maximum_seconds=p['maximum_seconds_per_model']))
                    try:code=child.wait(timeout=p['maximum_seconds_per_model'])
                    except BaseException:
                        os.killpg(child.pid,signal.SIGTERM)
                        try:child.wait(timeout=15)
                        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                        raise
                    if code:raise RuntimeError('Endpoint generation failed: '+name)
                done=json.loads((ROOT/name/'completion.json').read_text())
                if not done['complete'] or done['turns']!=300:raise ValueError('Complete actual endpoint required')
            verify(p)
            save(ROOT/'completion.json',dict(creator='Navneet Prabhakar',complete=True,models=2,conversations=200,raw_message_reply_pairs=600,model_updates=0,teacher_calls=0,cloud_commands=0,direct_assessment_pending=True,plan_sha256=sha(PLAN),completed_at_utc=datetime.now(timezone.utc).isoformat()))
        except BaseException as e:
            save(ROOT/'failure.json',dict(complete=False,error_type=type(e).__name__,message=str(e)[:1200],automatic_retry=False));raise

if __name__=='__main__':main()
