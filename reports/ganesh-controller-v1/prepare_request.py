"""Prepare the approved-task blueprint with NO authorization, lease or cloud writes."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_recovery_controller import validate_graph,canonical
P=Path(__file__).parent;D='reports/ganesh-english-curriculum-v2';O='runs/ganesh-recovery-next'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
fit={'manifest':'reports/english-first-v1/diagnostic-manifest.json','contract':'reports/english-first-v1/diagnostic-contract.json','suite':'reports/english-local-readiness-v1/fit-suite.json','development_suite':'reports/english-first-v1/development-suite.json'}
cur={'manifest':D+'/manifest.json','contract':D+'/quality-contract.json','suite':D+'/development-suite.json','protected_suite':'cloud_training/evaluation/conversation-tools-dev.json'}
files={}
for folder,freeze in [('reports/english-first-v1','packet-freeze.json'),(D,'freeze.json')]:
 for n,h in json.loads((ROOT/folder/freeze).read_text())['files'].items():
  if sha(ROOT/folder/n)!=h:raise ValueError('Frozen file mismatch')
  files[str(Path(folder)/n)]=h
for n in ['ganesh_recovery_task.py','cloud_training/nano_recovery_controller.py','cloud_training/nano_recovery_tasks.py','cloud_training/nano_recovery_gate.py','cloud_training/nano_fit_probe.py','cloud_training/nano_quality.py','cloud_training/nano_sft.py','cloud_training/nano_fit_readiness.py',fit['suite'],cur['protected_suite'],'runs/local-readiness-v1/base10b/manifest.json']:
 files[n]=sha(ROOT/n)
controller=O+'/controller';effective=controller+'/effective-request.json'
def command(ident,stage,operation,needs,directory,producer=None):
 result=O+'/'+ident+'-receipt.json'
 t={'id':ident,'stage':stage,'operation':operation,'kind':'command','source':'ganesh_recovery_task.py',
    'argv':[sys.executable,'ganesh_recovery_task.py','--request',effective,'--task',ident],
    'timeout_seconds':7200,'per_probe_seconds':1800,'needs':needs,'directory':directory,'result':result,
    'expected_status':'complete_requires_review' if operation.startswith('probe') else 'bounded_training_complete_not_accepted',
    'outputs':[result]}
 if operation.startswith('train'):t['outputs'] += [directory+'/result.json',directory+'/retention-journal.json']
 if producer:t['producer_directory']=producer
 return t
f=command('fit_train','fit','train_fit',[],O+'/fit')
p=command('fit_probes','fit','probe_fit',['fit_train'],O+'/fit-probes',O+'/fit')
r={'id':'fit_review','stage':'fit','kind':'fit_batch_review','needs':['fit_probes'],'raw':p['result'],
   'review':O+'/fit-semantic-review.json','suite':fit['suite'],'development_suite':fit['development_suite'],'producer_result':O+'/fit/result.json'}
c=command('curriculum_train','curriculum','train_curriculum',['fit_review'],O+'/curriculum')
cp=command('curriculum_probes','curriculum','probe_curriculum',['curriculum_train'],O+'/curriculum-probes',O+'/curriculum')
cr={'id':'curriculum_review','stage':'curriculum','kind':'development_batch_review','needs':['curriculum_probes'],'raw':cp['result'],'review':O+'/curriculum-semantic-review.json','suite':cur['suite'],'protected_suite':cur['protected_suite'],'producer_result':O+'/curriculum/result.json'}
request={'schema':1,'scope':'ganesh_english_recovery','path':'exact_resume','machine':'g2-standard-8','resource_count':1,
'provider_action':'STOP','disk_auto_delete':False,'automatic_retry':False,'automatic_restart':False,'http_enabled':False,
'files':files,'local_checks_passed':True,'launcher_integrated':True,'python':sys.executable,'tasks':[f,p,r,c,cp,cr],
'protected_roots':['runs/local-readiness-v1/base10b','reports/english-first-v1','reports/corrective-corpus-v1',D],
'controller_directory':controller,'termination_grace_seconds':600,'reserve_usd':None,'maximum_incremental_cost_usd':None,
'lease_start_utc':None,'provider_stop_utc':None,'worker_stop_utc':None,'backup_prefix':None,'backup_reserve_seconds':3600,
'fit_recipe':{'max_updates':64,'max_epochs':64,'lr_multiplier':.25,'packing_buffer':1,'context_tokens':2048},
'production_parent':'immutable_base10b','failed_learning_pilots':0,'release_exposed':False,'authorization':None,'evidence':{},
'fit_inputs':fit,'curriculum_inputs':cur,'training_inputs':{'repo':'runs/nanochat-source','base':'runs/local-readiness-v1/base10b','base_manifest_sha256':files['runs/local-readiness-v1/base10b/manifest.json'],'tokenizer':'runs/ownbase-v2-data/tokenizer','tokenizer_sha256':'ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'}}
validate_graph(request,ROOT)
(P/'request-template.json').write_text(json.dumps(request,indent=2)+'\n')
print(json.dumps({'tasks':len(request['tasks']),'spec_sha256':canonical({k:v for k,v in request.items() if k not in ('authorization','evidence')}),'authorization':None,'vm_start':False}))
