import json,subprocess,hashlib,datetime
from pathlib import Path
P=Path(__file__).resolve().parent;p=P/'complete_recovery_on_vm.py';sha=hashlib.sha256(p.read_bytes()).hexdigest();prefix=json.loads((P/'eager-qualification/config.json').read_text())['backup_prefix'];uri=prefix+'/completion-inputs/recovery-'+sha+'.py'
subprocess.run(['gcloud','storage','cp',str(p),uri,'--if-generation-match=0','--quiet'],check=True,timeout=60)
r=subprocess.run(['gcloud','storage','cat',uri],capture_output=True,check=True,timeout=60);assert hashlib.sha256(r.stdout).hexdigest()==sha
(P/'completion-code-backup.json').write_text(json.dumps({'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'uri':uri,'sha256':sha,'full_gcs_readback_verified':True,'original_runtime_packet_readback':json.loads((P/'eager-qualification/readback.json').read_text())},indent=2)+'\n')
