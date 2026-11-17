"""Retire only this stopped allocation after required backup/readback verification."""
import json,subprocess,datetime
from pathlib import Path
P=Path('reports/ganesh-l4-cap20-v1');A=P/'attempts/us-west1-a-185831'
receipt=json.loads((A/'retention-receipt.json').read_text())
assert receipt['status']=='required_backups_verified_before_disposable_disk_cleanup' and receipt['local_archive_and_both_capture_payloads_verified']
assert len(receipt['retained_checkpoints'])==3 and all(x['worker_full_payload_readback'] and x['local_manifest_readback'] for x in receipt['retained_checkpoints'])
name='ganesh-l4-1117-185840';zone='us-west1-a'
def run(args):return subprocess.run(['gcloud',*args,'--project=executespecv1','--quiet','--format=json'],check=True,capture_output=True,text=True,timeout=180)
vm=json.loads(run(['compute','instances','describe',name,'--zone='+zone]).stdout)
assert vm['status']=='TERMINATED' and len(vm['disks'])==1 and not vm['disks'][0]['autoDelete']
disk=vm['disks'][0]['source'].rsplit('/',1)[-1];assert disk==name
# Saved intent and exact resources before mutation; do not touch any other runs.
(A/'retirement-intent.json').write_text(json.dumps({'vm':name,'zone':zone,'disk':disk,'backup_receipt':'retention-receipt.json','intent_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
run(['compute','instances','delete',name,'--zone='+zone,'--keep-disks=all'])
run(['compute','disks','delete',disk,'--zone='+zone])
rule=json.loads(run(['compute','firewall-rules','describe','ganesh-cap20-iap-ssh']).stdout)
assert rule['targetTags']==['ganesh-cap20-qualification'] and rule['sourceRanges']==['35.235.240.0/20']
run(['compute','firewall-rules','delete','ganesh-cap20-iap-ssh'])
instances=json.loads(run(['compute','instances','list']).stdout);disks=json.loads(run(['compute','disks','list']).stdout)
assert all(x['name']!=name for x in instances) and all(x['name']!=name for x in disks)
report={'status':'verified_backups_retained_disposable_vm_disk_and_iap_rule_removed','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'instances':instances,'disks':disks,'deleted_vm':name,'deleted_disk':disk,'no_GCS_data_deleted':True,'local_weights_unchanged':True}
(A/'retirement-receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
