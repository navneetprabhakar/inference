"""Retire only the closed final VM/disk after required GCS readback proofs."""
import json,subprocess
from pathlib import Path
P=Path(__file__).parent;name='forge-english-a100-1114-084208';project='executespecv1';zone='us-central1-f'
def run(*args):return subprocess.run(['gcloud',*args],check=True,capture_output=True,text=True,timeout=180).stdout
for stage in ('repair','faults'):
 proof=json.loads((P/stage/'worker-backup-check.json').read_text())
 if not all(proof.get(k) for k in ('all_required_checkpoint_readbacks','evidence_readback','local_archive_readback_verified')):raise ValueError('Missing backup proof')
vm=json.loads(run('compute','instances','describe',name,'--project',project,'--zone',zone,'--format=json'))
if vm['status']!='TERMINATED' or len(vm['disks'])!=1 or vm['disks'][0]['autoDelete'] or not vm['disks'][0]['source'].endswith('/disks/'+name):raise ValueError('Unexpected resource state')
run('compute','instances','delete',name,'--project',project,'--zone',zone,'--quiet','--keep-disks=all')
run('compute','disks','delete',name,'--project',project,'--zone',zone,'--quiet')
vms=json.loads(run('compute','instances','list','--project',project,'--format=json'))
disks=json.loads(run('compute','disks','list','--project',project,'--format=json'))
if any(x['name']==name for x in vms+disks):raise ValueError('Resource deletion not verified')
receipt={'status':'retired_after_verified_backup_and_normal_stop','removed_instance':name,'removed_disk':name,'zone':zone,'prior_resources_untouched':True,'retained':'Required GCS checkpoints, mismatch states, runtime/input provenance and evidence; local requested models','proofs':['repair/worker-backup-check.json','faults/worker-backup-check.json'],'remaining_instances':[{'name':x['name'],'status':x['status']} for x in vms]}
(P/'retention-closeout.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
