"""Root-reviewed data admission; no model loading, training or budget activation."""
import os
os.environ['OMP_NUM_THREADS']='1'
import hashlib
import json
from pathlib import Path
import shutil
import time

ROOT=Path(__file__).resolve().parents[2]
SOURCES={
 'own-base-chat-aligned-v1':('7970c9c35c76f1bfcc2dfded6589846db365e51166a84636a170de61b701b609',
  'PASS_independent_structural_and_sampled_serialization',{'train':(22143,29082,3707850),'validation':(394,511,64228)}),
 'own-base-tool-aligned-v1':('17adc50fc4dd44b0a6df606d5e4212ec564fe2734db3f7c342e62100589da1c8',
  'PASS_independent_stream_reload_diagnostic_only',{'train':(5334,7342,225426),'exposed-development':(422,583,17834)}),
 'own-base-tool-session-aligned-v1':('4b72130463efbf67dacf42b551edfbd851a9cd60c7e29f0e38c206c50655ce76',
  'PASS_independent_stream_reload_diagnostic_only',{'train':(29,87,6073),'exposed-development':(8,24,1678)})}

def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(path.read_bytes())
def require(ok,why):
 if not ok:raise ValueError(why)

def main():
 os.nice(10);start=time.monotonic();prepared=[]
 def check():
  require(time.monotonic()-start<180,'admission time ceiling')
  require(not (ROOT/'runs/STOP').exists(),'STOP')
  require(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor')
 for name,(expected,state,counts) in SOURCES.items():
  check();d=ROOT/'data'/name
  require(not (d/'STOP').exists(),'source STOP')
  require(not (d/'diagnostic-admission.json').exists() and not (d/'diagnostic-verification.json').exists(),'preserve existing receipts')
  require(sha(d/'receipt.json')==expected,'dataset receipt changed')
  receipt=read(d/'receipt.json');verification=read(d/'independent-verification.json');freeze=read(d/'freeze.json')
  require(sha(d/'freeze.json')==receipt['freeze_sha256'],'freeze changed')
  require(verification['state']==state and verification['receipt_sha256']==expected,'independent verification mismatch')
  observed={k:tuple(v[f] for f in ('histories','rows','targets')) for k,v in verification['counts'].items()}
  require(observed==counts,'verified count mismatch')
  for filename,pin in receipt['outputs'].items():
   check();p=d/filename
   require(p.parent==d and not p.is_symlink(),'unsafe output identity')
   require(p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'packed artifact changed')
  for filename,pin in freeze['pins'].items():
   check();p=ROOT/filename
   require(p.resolve().is_relative_to(ROOT),'input outside repository')
   require(sha(p)==pin,'frozen preparation input changed')
  extra={}
  if name=='own-base-chat-aligned-v1':
   reload=read(d/'reload-verification.json')
   require(reload['state']=='PASS_builder_reload_not_independent_review' and reload['receipt_sha256']==expected,'full chat reload required')
   extra['reload_sha256']=sha(d/'reload-verification.json')
  wrapper=dict(state='PASS',dataset_sha256=expected,source=name,
               independent_verification_sha256=sha(d/'independent-verification.json'),
               independent_state=state,counts=verification['counts'],
               checks='Exact frozen input/output identities and independent verified counts; see original verification for scope and limitations.',**extra)
  admission=dict(training_admitted=True,scope='bounded_own_base_diagnostic_and_hardware_preflight_only',
                 dataset_sha256=expected,source=name,quality_certified=False,launch_authorized=False,
                 decision_sha256=sha(Path(__file__).with_name('DECISION.md')),
                 code_sha256=sha(Path(__file__)),source_passes='Must be fixed separately before execution',
                 verification_receipt='diagnostic-verification.json')
  prepared.append((d,wrapper,admission))
 check()
 for d,verification,admission in prepared:
  for name,value in [('diagnostic-verification.json',verification),('diagnostic-admission.json',admission)]:
   with (d/name).open('x') as f:json.dump(value,f,indent=2)
 print(json.dumps(dict(state='diagnostic_data_admitted_no_job_launched',sources=list(SOURCES),seconds=time.monotonic()-start)))

if __name__=='__main__':main()
