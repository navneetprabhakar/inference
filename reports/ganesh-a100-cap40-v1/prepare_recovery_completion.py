"""Build bounded completion of checks whose process never started before subdeadline."""
import ast,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P/'eager-qualification';source=(Q/'gpu_qualify.py').read_text();tree=ast.parse(source)
imports='\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom)))
functions='\n\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef))
header='''
import fcntl
ROOT=Path('/opt/english-eager');ORIGINAL=ROOT/'results';OUT=ROOT/'recovery-completion'
worker=(ROOT/'worker.lock').open('a');fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert (ROOT/'normal-stop-ready').exists() and not (ROOT/'backup-failure.txt').exists()
old=json.loads((ORIGINAL/'qualification.json').read_text())
assert old['status']=='hold_worker_failure' and old['backup_verified']
assert old['comparison']['status']=='pass' and old['replay']['eager']['fresh_process_equal']
assert all(c['matches_captured_output_exact'] for k in ('first','second') for c in old['replay']['eager'][k]['calls'])
assert all(json.loads((ORIGINAL/'capture-comparison.json').read_text())[k] for k in ('input_values_layout_equal','output_values_layout_equal','context_equal'))
assert 'nano_sft.py: error: Deadline must allow reserve and be within6hours' in (ORIGINAL/'signal_resume.log').read_text()
assert not (ORIGINAL/'signal_resume').exists(), 'Never retry a started writer'
marker=json.loads((ORIGINAL/'signal-marker.json').read_text());assert marker['partial_gradients_present'] and marker['live_post_rollback_saved']
rollback=json.loads((ORIGINAL/'rollback-comparison.json').read_text());assert rollback['status']=='pass'
config=json.loads((ROOT/'config.json').read_text());assert config['qualification_deadline_utc']=='2026-11-17T22:31:13Z'
config['worker_deadline_utc']='2026-11-17T22:26:13Z'
DEADLINE=dt.datetime.fromisoformat(config['qualification_deadline_utc'].replace('Z','+00:00')).timestamp()
assert DEADLINE-time.time()>1500, 'Need 10 minutes for pending checks and 15 minutes reserve'
REMOTE=config['backup_prefix'];BASE=ROOT/'base';PACKET=ROOT/'reports/english-first-v1'
OUT.mkdir(exist_ok=False)
(OUT/'completion-plan.json').write_text(json.dumps({'scope':'Only previously unstarted signal-resume, actual upload rejection, and decode timing; no English pilot or rerun of passed checks','original_qualification_deadline_utc':config['qualification_deadline_utc'],'child_deadline_utc':config['worker_deadline_utc'],'provider_stop_utc':config['deadline_utc'],'operational_command_reserve_seconds':900,'approved_cap_usd':40,'old_qualification_sha256':hashlib.sha256((ORIGINAL/'qualification.json').read_bytes()).hexdigest()},indent=2)+'\\n')
result={**old,'status':'running_completion','backup_verified':False,'original_qualification_error':old['error']};result.pop('error')
'''
body='''
try:
 # The original worker already downloaded and verified this exact GCS checkpoint.
 restored0=ROOT/'restored-step0';validate_bundle(restored0)
 signal_resume=sft('signal_resume',resume=restored0)
 first=ORIGINAL/'split_first'
 traces=compare_traces(first/'update-trace',signal_resume/'update-trace')
 (OUT/'signal-trace-comparison.json').write_text(json.dumps(traces,indent=2)+'\\n')
 signal_comparison=compare_and_record(first/'step-00000001',signal_resume/'step-00000001',OUT/'signal-comparison.json')
 if traces['status']!='pass':raise ValueError('Signal recovery trace mismatch')
 result.update(signal=signal_comparison,rollback=rollback,traces=traces)
'''
a=source.index(' # Reject a real payload upload');b=source.index('\nexcept BaseException as e:',a)
block=source[a:b]
# The benchmark itself writes into the original results location; retain its raw output.
block=block.replace("(OUT/'decode-benchmark.json').read_text()","(ORIGINAL/'decode-benchmark.json').read_text()")
footer='''
except BaseException as e:result.update(status='hold_completion_failure',error=repr(e))
finally:
 try:
  proofs=[]
  for bundle in sorted(OUT.glob('*/step-*')):
   validate_bundle(bundle)
   receipt=upload_bundle(bundle,remote_prefix=REMOTE+'/recovery-completion/salvage/checkpoints',timeout=min(600,remaining(180)))
   dst=ROOT/('completion-verify-'+str(len(proofs)));got=download_bundle(receipt['remote_prefix'],dst,reserve=120)
   assert got==receipt['manifest']
   proofs.append({'source':str(bundle),'remote_prefix':receipt['remote_prefix'],'manifest_sha256':hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest(),'readback':True})
   import shutil;shutil.rmtree(dst)
  result['original_bundle_readbacks']=old['bundle_readbacks'];result['bundle_readbacks']=proofs;result['backup_verified']=True
 except BaseException as e:result.update(backup_verified=False,backup_error=repr(e))
 (OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\\n')
 archive=ROOT/'completion-evidence.tar.gz'
 with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
  for p in OUT.rglob('*'):
   if p.is_file() and p.name!='payload.pt':tar.add(p,arcname='recovery-completion/'+str(p.relative_to(OUT)))
  for name in ('qualification.json','normal-comparison.json','capture-comparison.json','replay-comparison.json','signal-marker.json','rollback-comparison.json','signal_resume.log','decode-benchmark.json'):
   p=ORIGINAL/name
   if p.is_file():tar.add(p,arcname='original-results/'+name)
  tar.add(ROOT/'config.json',arcname='original-config.json')
 try:
  remote=REMOTE+'/recovery-completion';copy(archive,remote+'/evidence.tar.gz',reserve=60)
  readback=ROOT/'completion-readback.tar.gz';copy(remote+'/evidence.tar.gz',readback,reserve=30)
  assert hashlib.sha256(archive.read_bytes()).digest()==hashlib.sha256(readback.read_bytes()).digest()
  assert result['backup_verified']
  closeout=ROOT/'completion-closeout.json';closeout.write_text(json.dumps({'evidence_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_required_checkpoint_readbacks':True,'original_checkpoint_readbacks':old['backup_verified'],'evidence_readback':True,'utc':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\\n')
  copy(closeout,remote+'/closeout.json',reserve=20);copy(remote+'/closeout.json',ROOT/'completion-closeout-readback.json',reserve=10)
  assert closeout.read_bytes()==(ROOT/'completion-closeout-readback.json').read_bytes()
  (ROOT/'completion-normal-stop-ready').write_text('Original and completion evidence/readbacks verified\\n')
 except BaseException as e:(ROOT/'completion-backup-failure.txt').write_text(repr(e))
print(json.dumps(result,indent=2))
'''
s=imports+'\n'+header+'\n'+functions+'\n'+body+block+'\n'+footer
ast.parse(s);(P/'complete_recovery_on_vm.py').write_text(s)
print(hashlib.sha256(s.encode()).hexdigest())
