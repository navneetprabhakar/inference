"""Once-only isolated unpack or AST roundtrip, with preflight-armed watchdog."""
import argparse,hashlib,json,os,pathlib,re,signal,subprocess,sys,time
import safe_wheel
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';TARGET=BASE/'tool-dependencies/mwparserfromhell-0.7.2';SOURCE=ROOT/'enwiki-native-20row-capture-v1';WHEEL=ROOT/'mwparserfromhell-0.7.2-inert-wheel-v1/mwparserfromhell-0.7.2-cp312-cp312-macosx_11_0_arm64.whl'
CHILD=None;START=None
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def clock():return time.monotonic()
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file()) if p.exists() else 0
def write(path,value,cap):
 b=(json.dumps(value,indent=2)+'\n').encode()
 if size(path.parent)+len(b)>cap:raise ValueError('evidence_prewrite_cap')
 with path.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def kill():
 global CHILD
 if CHILD is not None:
  if CHILD.poll() is None:
   try:os.killpg(CHILD.pid,signal.SIGKILL)
   except ProcessLookupError:pass
  CHILD.wait(timeout=3)
def stop(signum,frame):
 kill();raise TimeoutError('preflight_armed_external60_or_termination_signal_'+str(signum))
def check():
 if clock()-START>=55:raise TimeoutError('shared55worker_deadline')
def verify(mode,digest):
 p=HERE/(mode+'-pins.json')
 if p.is_symlink() or not re.fullmatch('[0-9a-f]{64}',digest) or sha(p)!=digest:raise ValueError('explicit_frozen_manifest_digest')
 m=json.loads(p.read_text())
 if m['runtime']!={'python':sys.version,'launcher':sys.executable,'prefix':sys.prefix}:raise ValueError('exact_runtime')
 for name,h in m['files'].items():
  check();path=pathlib.Path(name)
  if path.is_symlink() or not path.is_file() or sha(path)!=h:raise ValueError('exact_input_or_dependency_pin:'+name)
 profile=json.loads((HERE/(mode+'-profile.json')).read_text())
 if profile['mode']!=mode or profile['limits']['external_seconds']!=60 or profile['limits']['RSS_bytes']!=1000000000:raise ValueError('exact_profile_limits')
 return profile

def main(a):
 global CHILD,START
 START=clock();old={s:signal.signal(s,stop) for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]};signal.setitimer(signal.ITIMER_REAL,60)
 out=ROOT/('mwparserfromhell-isolated-install-v1' if a.mode=='install' else 'mwparserfromhell-native20-AST-roundtrip-v1');created=False;peak=0
 cap=1000000 if a.mode=='install' else 16000000
 try:
  profile=verify(a.mode,a.pins);check()
  if out.exists() or out.is_symlink():raise ValueError('existing_output_no_retry')
  out.mkdir();created=True
  inventory=json.loads((HERE/'wheel-inventory.json').read_text())
  if a.mode=='install':safe_wheel.unpack(WHEEL,TARGET,inventory,check)
  command=[sys.executable,'-I','-B',str(HERE/'package_worker.py'),'--target',str(TARGET),'--mode','synthetic' if a.mode=='install' else 'native20','--source',str(SOURCE),'--output',str(out/'proof.json'),'--inventory',str(HERE/'wheel-inventory.json')]
  with (out/'worker.log').open('xb') as log:CHILD=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  pid=CHILD.pid
  while CHILD.poll() is None:
   check();ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   while True:
    more=owned|{p for p,q,r in rows if q in owned}
    if more==owned:break
    owned=more
   peak=max(peak,sum(r*1024 for p,q,r in rows if p in owned))
   if peak>1000000000 or size(out)>cap or size(TARGET)>5000000:raise ValueError('RSS_evidence_or_extracted_cap')
   time.sleep(.05)
  CHILD.wait(timeout=3)
  if CHILD.returncode:raise ValueError('isolated_import_or_AST_worker_failed')
  proof=json.loads((out/'proof.json').read_text())
  if proof['native_C_parser'] is not True:raise ValueError('C_parser_proof_required')
  verify(a.mode,a.pins)
  installed={str(p.relative_to(TARGET)):sha(p) for p in TARGET.rglob('*') if p.is_file()}
  if installed!={n:r['SHA256'] for n,r in inventory['files'].items()}:raise ValueError('installed_tree_exact_inventory_no_extra_pyc')
  write(out/'receipt.json',{'status':'COMPLETE_ISOLATED_INSTALL_VERIFIED' if a.mode=='install' else 'COMPLETE_NATIVE20_AST_ROUNDTRIP_ONLY','mode':a.mode,'pins_SHA256':a.pins,'proof_SHA256':sha(out/'proof.json'),'wheel_SHA256':safe_wheel.WHEEL_SHA,'installed_files_SHA256':installed,'installed_bytes':size(TARGET),'all20_source_negative_cases_retained':proof.get('all20negative_cases_preserved'),'worker_PID':pid,'worker_exit':CHILD.returncode,'elapsed_seconds':clock()-START,'peak_observed_process_tree_RSS_bytes':peak,'network_requests':0,'global_ledger_writes':0,'tokenization_extraction_template_expansion_models_admission':False},cap)
  print(json.dumps({'status':'COMPLETE','mode':a.mode,'output':str(out),'receipt_SHA256':sha(out/'receipt.json'),'elapsed':clock()-START}));return 0
 except BaseException as e:
  kill()
  if created:
   write(out/'terminal-failure.json',{'status':'TERMINAL_FAILED_NO_RETRY','mode':a.mode,'error':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clock()-START,'network_requests':0,'new_admitted_documents':0},cap)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['install','ast'],required=True);p.add_argument('--pins',required=True);a=p.parse_args();raise SystemExit(main(a))
