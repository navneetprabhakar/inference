"""Fresh local checks; no cloud calls or model training. Does not read release text."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from cloud_training.nano_package import extract_verified,verify_module_closure
from cloud_training.nano_checkpoint import validate_bundle
P=Path(__file__).parent

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 results={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'cloud_mutations':False,'training':False,'release_text_read':False}
 frozen={}
 for folder,fn in [('reports/english-first-v1','packet-freeze.json'),('reports/corrective-corpus-v1','freeze.json')]:
  files=json.loads((ROOT/folder/fn).read_text())['files']
  for name,h in files.items():
   if sha(ROOT/folder/name)!=h:raise ValueError('Changed frozen input: '+name)
  frozen[folder]={'count':len(files),'unchanged':True}
 results['frozen']=frozen
 models={}
 for name,path in [('base10b','runs/local-readiness-v1/base10b'),('sft50','runs/quality-rca-v1/step-00000050'),('default194','runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs')]:
  manifest=validate_bundle(ROOT/path)
  models[name]={'path':path,'manifest_sha256':sha(ROOT/path/'manifest.json'),'step':manifest['step'],'payload_verified':True}
 results['models']=models
 archive=ROOT/'runs/ganesh-launch-readiness-v1/runtime.tar.gz'
 with tempfile.TemporaryDirectory() as tmp:
  m=extract_verified(archive,Path(tmp).resolve()/'runtime')
  for n,v in m['files'].items():
   if n.startswith('cloud_training/') and sha(ROOT/n)!=v['sha256']:raise ValueError('Stale packaged code: '+n)
 results['runtime']={'path':str(archive.relative_to(ROOT)),'sha256':sha(archive),'bytes':archive.stat().st_size,'verified_members':len(m['files'])+1,'closure':verify_module_closure(ROOT),'scope':'Offline readback only; new recovery gate is local-only and not in runtime'}
 original=json.loads((ROOT/'reports/english-local-readiness-v1/experiment-card.json').read_text())['offline_preflight_argv']
 original[0]=sys.executable
 for label,capture in [('fit',False),('capture',True)]:
  argv=original.copy();argv[argv.index('--output')+1]=str(P/('preflight-'+label))
  if capture:
   argv[argv.index('--max-updates')+1]='2';argv+=['--capture-muon-step','1']
  with (P/('preflight-'+label+'.log')).open('w') as log:
   subprocess.run(argv,cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
  results[label+'_preflight']={'argv':argv,'returncode':0,'validation_only':True}
 listener=subprocess.run(['lsof','-nP','-iTCP:8765','-sTCP:LISTEN'],capture_output=True,text=True)
 if listener.returncode==0:raise ValueError('Unexpected HTTP listener')
 results['http_off']=True
 train=json.loads((ROOT/'reports/english-local-readiness-v1/fit-suite.json').read_text())
 dev=json.loads((ROOT/'reports/english-first-v1/development-suite.json').read_text())
 count=lambda s:sum(len(x['turns']) for x in s['sessions'])
 results['workload']={'fit_sessions':len(train['sessions']),'fit_turns':count(train),'development_sessions':len(dev['sessions']),'development_turns':count(dev),'fit_checkpoint_limit':6,'development_checkpoint_limit':3,'reply_tokens':128,'maximum_generation_calls':6*count(train)+3*count(dev),'maximum_actions_per_turn':3,'maximum_generated_tokens':3*128*(6*count(train)+3*count(dev)),'fit_updates':64,'max_input_positions':64*8192,'limit_not_throughput_estimate':True}
 (P/'local-results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps({'frozen_files':sum(v['count'] for v in frozen.values()),'model_payloads_verified':len(models),'local_preflights':'pass','runtime_sha256':results['runtime']['sha256'],'workload':results['workload']}))
if __name__=='__main__':main()
