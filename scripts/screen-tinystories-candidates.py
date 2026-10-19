"""Full-window narrative screening of the acquired finite pool; no admission."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from slm.data.detector_projection import fasttext_line
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.intake_cache import IntakeCache
from slm.data.intake_ledger import IntakeLedger
from slm.data.narrative_screen import screen
from slm.data.prose_screen import windows
from slm.data.quality_audit import LIMITS,predict,top_scores
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/tinystories-quality-v1');PLAN=Path('configs/tinystories-quality-v1.json')

def encoded(v):return (json.dumps(v,sort_keys=True,ensure_ascii=False)+'\n').encode()
def save(p,v):p.write_bytes(encoded(v))

def worker():
    plan=json.loads(PLAN.read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned narrative quality input changed')
    ledger=IntakeLedger(ROOT/'charges',plan['ledger_contract']);cache=IntakeCache(ROOT/'cache',ledger)
    stage='initialization'
    try:
        ledger.reserve('auxiliary-artifacts',output_bytes=1048576);ledger.finish('auxiliary-artifacts',raw=b'')
        spec=json.loads(Path('configs/future-intake-evaluation-exclusions-v1.json').read_text())
        prior=EvaluationExclusions(spec['inventory'],spec['inventory_sha256'])
        protection=json.loads(Path(plan['upstream_protection']).read_text())
        from slm.data.prose_screen import RequestGuard
        upstream=RequestGuard([r['text'] for r in protection['prompts']])
        heldouts=set(protection['normalized_validation_families'])
        judgments={(r['file'],r['start']):r['judgment'] for r in json.loads(Path(plan['direct_review']).read_text())['records']}
        measurements={}
        with Path(plan['measurements']).open() as inp:
            for line in inp:
                r=json.loads(line)
                if r['kind']=='train_range':measurements[(r['file'],r['start'])]=r
        intake=json.loads(Path(plan['intake_report']).read_text());work=ROOT/'language';work.mkdir()
        summary=[]
        for item in intake['requests']:
            request=item['request']
            if request['kind']!='train_range':continue
            path=Path(plan['intake_cache'])/(digest('records/'+request['key'])+'.bin')
            if sha(path)!=item['records_sha256']:raise ValueError('Original acquired stories changed')
            rawrows=[json.loads(line) for line in path.read_bytes().splitlines()]
            for start in range(0,len(rawrows),plan['chunk_rows']):
                ledger.check_time();stage=request['key']+'/'+str(start)
                if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Free disk reserve reached')
                if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>plan['maximum_work_disk_bytes']:raise ValueError('Work disk cap reached')
                batch=rawrows[start:start+plan['chunk_rows']]
                ledger.reserve('assess/'+stage,rows=len(batch))
                parts=[windows(r['row']['text']) for r in batch];flat=[p for group in parts for p in group]
                if len(flat)>LIMITS['max_windows']:raise ValueError('Complete window count exceeds cap')
                projection=''.join(fasttext_line(p['text'])+'\n' for p in flat).encode()
                if len(projection)>LIMITS['max_input_bytes']:raise ValueError('Detector input exceeds cap')
                inp=work/'input.txt';pred=work/'predictions.txt';inp.write_bytes(projection)
                predict(Path(plan['detector']['binary']),Path(plan['detector']['model']),inp,pred,LIMITS)
                lines=pred.read_text().splitlines()
                if len(lines)!=len(flat):raise ValueError('Complete narrative window alignment differs')
                scores=[top_scores(line) for line in lines];cursor=0;output=[]
                for raw,group in zip(batch,parts,strict=True):
                    text=raw['row']['text'];key=(raw['file'],raw['row']['start']);measure=measurements[key]
                    if measure['raw_text_sha256']!=raw['row']['raw_text_sha256']:raise ValueError('Sizing/source identity differs')
                    lang=scores[cursor:cursor+len(group)];cursor+=len(group)
                    decision=screen(text,lang,prior.guard,upstream,heldouts,judgments.get(key))
                    output.append(dict(file=raw['file'],start=raw['row']['start'],end=raw['row']['end'],source_group=raw['source_group'],
                        raw_text_sha256=raw['row']['raw_text_sha256'],decision=decision,
                        windows=[dict(start=p['start'],end=p['end'],scores=s) for p,s in zip(group,lang,strict=True)],
                        content_tokens=measure['content_tokens'],training_approved=False,partition=None,
                        pending='Global exact/near/seed/ancestral grouping, finite corpus/content admission and realized mixture.'))
                cache.publish('decisions/'+stage,b''.join(encoded(r) for r in output));ledger.finish('assess/'+stage,raw=b'')
                summary.append(dict(key=stage,rows=len(output),provisional_pass_rows=sum(r['decision']['candidate'] for r in output),
                    provisional_pass_tokens=sum(r['content_tokens'] for r in output if r['decision']['candidate']),
                    total_tokens=sum(r['content_tokens'] for r in output),windows=len(flat),
                    reasons=dict(Counter(reason for r in output for reason in r['decision']['reasons']))))
                for p in (inp,pred,work/'detector.stderr'):
                    if p.exists():p.unlink()
                print(json.dumps(dict(chunks=len(summary),rows=sum(r['rows'] for r in summary),provisional_pass=sum(r['provisional_pass_rows'] for r in summary))),flush=True)
        for p,h in plan['input_bindings'].items():
            if sha(p)!=h:raise ValueError('Pinned narrative quality input changed during screening')
        snapshot=ledger.snapshot();save(ROOT/'ledger-snapshot.json',snapshot)
        result=dict(creator='Navneet Prabhakar',kind='actual-narrative-quality-v1',complete=True,plan_sha256=sha(PLAN),
            chunks=summary,rows=sum(r['rows'] for r in summary),windows=sum(r['windows'] for r in summary),
            provisional_pass_rows=sum(r['provisional_pass_rows'] for r in summary),provisional_pass_tokens=sum(r['provisional_pass_tokens'] for r in summary),
            reason_counts=dict(sum((Counter(r['reasons']) for r in summary),Counter())),reserved=snapshot['reserved'],
            training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='All acquired train stories screened without source rewriting; actual full-window detector scores retained. Exact official validation/upstream prefix/prior evaluation/direct nonapprovals enforced. Statistical signals only; no factual/privacy/category verification or global near/ancestral/source admission.')
        save(ROOT/'report.json',result);save(Path('reports/tinystories-quality.json'),result)
    except BaseException as error:
        save(ROOT/'failure.json',dict(complete=False,stage=stage,error_type=type(error).__name__,ledger=ledger.snapshot()))
        raise SystemExit('Narrative screening stopped; retain outputs and charges; no replay') from None
    finally:ledger.close()

def main():
    if '--worker' in sys.argv:worker();return
    if ROOT.exists():raise FileExistsError('Narrative quality run already attempted')
    ROOT.mkdir();save(ROOT/'plan.json',json.loads(PLAN.read_text()))
    child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
    try:
        code=child.wait(timeout=1800)
        if code:raise SystemExit(code)
    except BaseException:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise

if __name__=='__main__':main()
