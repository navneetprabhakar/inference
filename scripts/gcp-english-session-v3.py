"""Single private L4 lifecycle with finite deletion, incremental backups and cleanup."""
# Creator: Navneet Prabhakar
import hashlib,json,os,re,shlex,subprocess,sys,time,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import urlopen

OUT=Path('data/english-gcp-session-v3')
PROJECT='executespecv1';ZONE='us-central1-a'
IMAGE='pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261001'
IMAGE_ID='8190671948398954841'
HOME_PROJECT='english-runtime-v3/project'
PARENT='data/english-balanced-experiment-v2';MAIN='data/english-uniform-main-run-v3'


def read(p):return json.loads(Path(p).read_text())
def save(p,x):
    p=Path(p);temp=p.with_suffix('.tmp');temp.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n');temp.replace(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def stamp():return datetime.now(timezone.utc)


def validate_instance(d,p,disk):
    if d['name']!=p['vm'] or d.get('labels',{}).get('run-id')!=p['run_id']:
        raise ValueError('Owned resource identity differs')
    if not d['machineType'].endswith('/g2-standard-4') or d.get('serviceAccounts'):
        raise ValueError('Single private machine/no service-account contract differs')
    if len(d['guestAccelerators'])!=1 or d['guestAccelerators'][0]['acceleratorCount']!=1 or not d['guestAccelerators'][0]['acceleratorType'].endswith('/nvidia-l4'):
        raise ValueError('Actual one L4 required')
    if any(n.get('accessConfigs') or n.get('ipv6AccessConfigs') for n in d['networkInterfaces']):
        raise ValueError('No public address allowed')
    s=d['scheduling']
    if s.get('automaticRestart') is not False or s.get('onHostMaintenance')!='TERMINATE' or s.get('provisioningModel')!='STANDARD' or s.get('instanceTerminationAction')!='DELETE':
        raise ValueError('Independent finite on-demand deletion policy differs')
    if datetime.fromisoformat(s['terminationTime'].replace('Z','+00:00'))!=datetime.fromisoformat(p['delete_at_utc']):
        raise ValueError('Absolute deletion time differs; never reset lifetime')
    if len(d['disks'])!=1 or d['disks'][0].get('autoDelete') is not True or d['disks'][0].get('boot') is not True:
        raise ValueError('One auto-delete boot disk required')
    if disk.get('sourceImageId')!=IMAGE_ID or int(disk['sizeGb'])!=100 or not disk['type'].endswith('/pd-standard'):
        raise ValueError('Pinned image/standard100GB disk contract differs')


def command(args,name,timeout=120,check=True):
    number=len(list(OUT.glob('command-*.json')))
    try:
        result=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired as error:
        save(OUT/f'command-{number:04d}.json',dict(name=name,args=args,complete=False,timeout_seconds=timeout,external_state_may_be_unknown=True))
        for stream in ('stdout','stderr'):
            value=getattr(error,stream) or b''
            if isinstance(value,bytes):value=value.decode(errors='replace')
            (OUT/f'{number:04d}-{name}.{stream}').write_text(value)
        raise
    save(OUT/f'command-{number:04d}.json',dict(name=name,args=args,returncode=result.returncode))
    (OUT/f'{number:04d}-{name}.stdout').write_text(result.stdout)
    (OUT/f'{number:04d}-{name}.stderr').write_text(result.stderr)
    if check and result.returncode:raise RuntimeError('Bounded command failed: '+name)
    return result


def gcloud(args,name,timeout=120,check=True):
    return command(['gcloud',*args,'--project='+PROJECT,'--quiet'],name,timeout,check)


def ssh(p,script,name,timeout=120,check=True):
    return gcloud(['compute','ssh',p['vm'],'--zone='+ZONE,'--tunnel-through-iap',
                   '--command='+script],name,timeout,check)


def remote_python(p,code,name,timeout=120):
    return ssh(p,'python3 -c '+shlex.quote(code),name,timeout)


def fetch_bundle(p,label,selection):
    folder=OUT/'bundles';folder.mkdir(exist_ok=True)
    local=folder/(label+'.tar.gz');receipt=folder/(label+'.json')
    if receipt.exists() and sha(local)==read(receipt)['sha256']:return
    code="""import hashlib,json,tarfile\nfrom pathlib import Path\nr=Path('english-runtime-v3');project=r/'project';files=[]\n"""+selection+"""
target=r/'LABEL.tar.gz'
with tarfile.open(target,'w:gz',compresslevel=1,dereference=True) as tar:
 for path in sorted(set(files)):
  if path.is_symlink() or not path.is_file():raise ValueError('Regular result files only')
  tar.add(path,arcname=str(path.relative_to(project)),recursive=False)
if target.stat().st_size>8*1024**3:raise ValueError('Bounded result archive required')
h=hashlib.sha256()
with target.open('rb') as f:
 for b in iter(lambda:f.read(1048576),b''):h.update(b)
print(json.dumps(dict(sha256=h.hexdigest(),bytes=target.stat().st_size)))
""".replace('LABEL',label)
    expected=json.loads(remote_python(p,code,'bundle-'+label,600).stdout)
    gcloud(['compute','scp','--zone='+ZONE,'--tunnel-through-iap',
            p['vm']+':english-runtime-v3/'+label+'.tar.gz',str(local)],'download-'+label,1800)
    if sha(local)!=expected['sha256']:raise ValueError('Returned archive checksum differs')
    save(receipt,dict(creator='Navneet Prabhakar',complete=True,**expected))
    ssh(p,'rm -- '+shlex.quote('english-runtime-v3/'+label+'.tar.gz'),'remove-transferred-'+label)


def probe(p):
    code=f"""import json,subprocess\nfrom pathlib import Path\nr=Path({HOME_PROJECT!r});parent=r/{PARENT!r};main=r/{MAIN!r}\ndef j(path):\n try:return json.loads(path.read_text())\n except (FileNotFoundError,json.JSONDecodeError):return None\nx=dict(pipeline_exit=j(parent/'cloud-pipeline-exit.json'),proof_exit=j(parent/'cloud-proof-exit.json'),paired=j(parent/'paired-proof.json'),main_freeze=j(main/'freeze.json'),progress=j(main/'language/progress.json'),checkpoints=[])\nif (main/'language').exists():\n for d in (main/'language').iterdir():\n  if d.is_dir() and (d.name=='terminal' or d.name.startswith('positions-')) and j(d/'manifest.json') is not None:x['checkpoints'].append(d.name)\nx['unit']=subprocess.run(['systemctl','is-active','slm-english-recovery'],capture_output=True,text=True).stdout.strip()\nprint(json.dumps(x))\n"""
    return json.loads(remote_python(p,code,'probe',120).stdout)


def cleanup(p):
    boot_disk=read(OUT/'actual-disk.json')['name'] if (OUT/'actual-disk.json').exists() else p['vm']
    d=gcloud(['compute','instances','describe',p['vm'],'--zone='+ZONE,'--format=json'],'cleanup-owned-describe',check=False)
    if d.returncode==0:
        v=json.loads(d.stdout)
        if v.get('labels',{}).get('run-id')!=p['run_id']:raise ValueError('Refuse unrelated instance cleanup')
        gcloud(['compute','instances','delete',p['vm'],'--zone='+ZONE],'delete-owned-vm',600)
    remaining=json.loads(gcloud(['compute','instances','list','--filter=name='+p['vm'],'--format=json'],'verify-no-vm').stdout)
    disks=json.loads(gcloud(['compute','disks','list','--filter=name='+boot_disk,'--format=json'],'verify-no-disk').stdout)
    if remaining or disks:raise ValueError('VM/auto-delete disk cleanup not confirmed')
    rules=json.loads(gcloud(['compute','firewall-rules','list','--filter=name='+p['firewall'],'--format=json'],'owned-rule-inventory').stdout)
    if rules:
        rule=rules[0]
        if rule.get('targetTags')!=[p['tag']] or rule.get('sourceRanges')!=['35.235.240.0/20']:
            raise ValueError('Refuse unrelated firewall cleanup')
        gcloud(['compute','firewall-rules','delete',p['firewall']],'delete-owned-rule')
    after=json.loads(gcloud(['compute','firewall-rules','list','--filter=name='+p['firewall'],'--format=json'],'verify-no-rule').stdout)
    if after:raise ValueError('Temporary firewall cleanup not confirmed')
    save(OUT/'cleanup.json',dict(creator='Navneet Prabhakar',complete=True,instances=0,boot_disks=0,temporary_rules=0,
         finished_at_utc=stamp().isoformat(),settled_cost_unknown=True))


def monitor(p):
    while True:
        if stamp()>=datetime.fromisoformat(p['delete_at_utc'])-timedelta(minutes=20):
            raise TimeoutError('Independent VM deletion approaching; inspect/retrieve latest backups')
        state=probe(p);save(OUT/'progress.json',dict(observed_at_utc=stamp().isoformat(),**state))
        if state['paired'] and state['paired'].get('passed'):
            selection=f"files.extend((project/{(PARENT+'/cuda')!r}).rglob('*'))\nfiles=[x for x in files if x.is_file()]\n"
            fetch_bundle(p,'cuda-origin',selection)
        for checkpoint in sorted(state['checkpoints']):
            if not re.fullmatch(r'terminal|positions-[0-9]{9}',checkpoint):raise ValueError('Unexpected checkpoint identity')
            fetch_bundle(p,'main-'+checkpoint,f"files.extend(x for x in (project/{(MAIN+'/language/')!r}/{checkpoint!r}).rglob('*') if x.is_file())\n")
        ended=state['pipeline_exit'] is not None or state['unit'] in ('failed','inactive')
        if ended:
            selection=f"""for name in [{PARENT!r},{MAIN!r}]:
 folder=project/name
 if folder.exists():
  files.extend(x for x in folder.rglob('*') if x.is_file() and (x.suffix in ('.json','.jsonl','.npz','.md','.log','.sqlite','.txt','.xml') or x.name.endswith(('-journal','-wal','-shm'))))
"""
            fetch_bundle(p,'final-metadata',selection)
            save(OUT/'remote-terminal.json',dict(creator='Navneet Prabhakar',complete=bool(state['pipeline_exit'] and state['pipeline_exit'].get('complete')),state=state,actual_assessment_pending=True))
            if state['pipeline_exit'] and state['pipeline_exit'].get('complete'):
                cleanup(p)
            else:
                save(OUT/'needs-diagnosis.json',dict(creator='Navneet Prabhakar',complete=False,owned_vm_still_exists=True,
                     independent_delete_at_utc=p['delete_at_utc'],action='Inspect exact failure/ledgers now; fix on same bounded VM or clean up. Never retry gradients or create another VM automatically.'))
            return
        time.sleep(60)


def main():
    if len(sys.argv)>1 and sys.argv[1]=='monitor':monitor(read(OUT/'plan.json'));return
    if OUT.exists():raise FileExistsError('No automatic VM retry or lifetime reset')
    package=Path('data/english-training-cloud-package-v3');receipt=read(package/'receipt.json')
    if not read('data/english-balanced-local-v2/supervisor-terminal.json')['complete']:
        raise ValueError('Actual corrected local terminal success required')
    quality=read('reports/english-balanced-local-learning-v2.json')
    if not quality['quality']['passed'] or sha(package/'inputs.tar.gz')!=receipt['archive_sha256']:
        raise ValueError('Actual useful local learning and sealed combined archive required')
    policy=read('configs/english-uniform-main-policy-v3.json')
    for name,h in policy['inputs'].items():
        if sha(name)!=h:raise ValueError('Frozen main policy changed: '+name)
    OUT.mkdir();save(OUT/'process.json',dict(parent=os.getpid(),phase='preflight'))
    try:
        inventory=json.loads(gcloud(['compute','instances','list','--format=json'],'preflight-instances').stdout)
        if inventory:raise ValueError('Existing project VMs require ownership reconciliation before creation')
        image=json.loads(command(['gcloud','compute','images','describe',IMAGE,'--project=deeplearning-platform-release','--format=json'],'pinned-image').stdout)
        if image['id']!=IMAGE_ID or image['status']!='READY':raise ValueError('Pinned image identity/status differs')
        region=json.loads(gcloud(['compute','regions','describe','us-central1','--format=json'],'region-quota').stdout)
        quota=next(q for q in region['quotas'] if q['metric']=='NVIDIA_L4_GPUS')
        if quota['limit']-quota['usage']<1:raise ValueError('Insufficient L4 quota')
        global_info=json.loads(gcloud(['beta','quotas','info','list','--service=compute.googleapis.com',
                                      '--filter=quotaId=GPUS-ALL-REGIONS-per-project','--format=json'],'global-gpu-quota').stdout)
        values=[int(x['details']['value']) for q in global_info for x in q.get('dimensionsInfos',[]) if 'global' in x.get('applicableLocations',[])]
        if not values or max(values)<1:raise ValueError('Insufficient verified global GPU quota')
        url='https://cloud.google.com/products/compute/pricing/accelerator-optimized?hl=en'
        html=command(['curl','--fail','--location','--max-time','45','--max-filesize','16777216',url],'primary-price',60).stdout.encode()
        if len(html)>16*1024**2:raise ValueError('Bounded primary pricing page required')
        (OUT/'price.html').write_bytes(html);text=html.decode();start=text.index('g2-standard-4')
        row=text[start:text.index('</tr>',start)];price=float(re.search(r'\$([0-9.]+) / 1 hour',row).group(1))
        if price>.8:raise ValueError('Listed VM price exceeds authorized ceiling')
        now=stamp();deadline=(now+timedelta(hours=45)).replace(microsecond=0)
        run_id=uuid.uuid4().hex[:8];name='slm-english-v3-'+run_id
        p=dict(creator='Navneet Prabhakar',vm=name,tag=name,firewall=name+'-iap',run_id=run_id,
               creation_started_at_utc=now.isoformat(),delete_at_utc=deadline.isoformat(),project=PROJECT,zone=ZONE,
               plan_sha256=receipt['plan_sha256'],archive_sha256=receipt['archive_sha256'],
               observed_vm_rate_usd=price,compute_reservation_usd=36,storage_network_reservation_usd=14,
               contingency_reservation_usd=50,total_ceiling_usd=100,maximum_instances_created=1,
               source_inputs={f:sha(f) for f in ['scripts/gcp-english-session-v3.py','scripts/bootstrap-english-cloud.sh',
                  'scripts/verify-english-cloud-archive.py','scripts/english-cloud-pipeline-v3.sh','scripts/english-cloud-proof-v3.sh',
                  'configs/english-uniform-main-policy-v3.json']})
        save(OUT/'plan.json',p)
        gcloud(['compute','firewall-rules','create',p['firewall'],'--network=default','--direction=INGRESS',
                '--action=ALLOW','--rules=tcp:22','--source-ranges=35.235.240.0/20','--target-tags='+p['tag'],'--format=json'],'create-owned-iap-rule')
        gcloud(['compute','instances','create',name,'--zone='+ZONE,'--machine-type=g2-standard-4','--accelerator=type=nvidia-l4,count=1',
                '--image='+IMAGE,'--image-project=deeplearning-platform-release','--boot-disk-size=100GB',
                '--boot-disk-type=pd-standard','--boot-disk-auto-delete','--no-address','--no-service-account','--no-scopes',
                '--no-restart-on-failure','--maintenance-policy=TERMINATE','--provisioning-model=STANDARD',
                '--termination-time='+deadline.isoformat(),'--instance-termination-action=DELETE','--tags='+p['tag'],
                '--labels=purpose=slm-english-recovery,run-id='+run_id,'--metadata=enable-oslogin=TRUE','--format=json'],'create-single-l4',600)
        d=json.loads(gcloud(['compute','instances','describe',name,'--zone='+ZONE,'--format=json'],'actual-vm').stdout)
        disk_name=d['disks'][0]['source'].split('/')[-1]
        disk=json.loads(gcloud(['compute','disks','describe',disk_name,'--zone='+ZONE,'--format=json'],'actual-boot-disk').stdout)
        validate_instance(d,p,disk);save(OUT/'actual-vm.json',d);save(OUT/'actual-disk.json',disk)
        launch={**p,'resource_contract_passed':True};save(OUT/'cloud-launch.json',launch)
        ready=False
        for attempt in range(24):
            if ssh(p,'true','ssh-readiness-'+str(attempt),30,False).returncode==0:ready=True;break
            time.sleep(5)
        if not ready:raise RuntimeError('SSH not ready; no VM retry/time reset')
        uploads=[package/'inputs.tar.gz',OUT/'cloud-launch.json',*[Path(f) for f in p['source_inputs'] if f.startswith('scripts/') and f!='scripts/gcp-english-session-v3.py']]
        gcloud(['compute','scp','--zone='+ZONE,'--tunnel-through-iap',*[str(f) for f in uploads],name+':.'],'upload-offline-inputs',1800)
        expected={f.name:sha(f) for f in uploads}
        code="import hashlib\nfrom pathlib import Path\nexpected="+repr(expected)+"\nfor name,h in expected.items():\n x=hashlib.sha256()\n with Path(name).open('rb') as f:\n  for b in iter(lambda:f.read(1048576),b''):x.update(b)\n if x.hexdigest()!=h:raise ValueError('Transferred launch input differs')\nprint('All transferred launch inputs verified')\n"
        remote_python(p,code,'verify-uploaded-archive-and-code',300)
        args=['bash','bootstrap-english-cloud.sh','inputs.tar.gz',receipt['archive_sha256'],'cloud-launch.json',
              'english-runtime-v3','verify-english-cloud-archive.py','english-cloud-pipeline-v3.sh','conditional-main','english-cloud-proof-v3.sh']
        ssh(p,shlex.join(args),'bootstrap-conditional-pipeline',900)
        save(OUT/'started.json',dict(creator='Navneet Prabhakar',complete=True,vm=name,independent_delete_at_utc=p['delete_at_utc'],
                                   scope='Actual resource/upload/bootstrap complete; CUDA proof and conditional main execute remotely.'))
        monitor(p)
    except BaseException as e:
        save(OUT/'failure.json',dict(creator='Navneet Prabhakar',complete=False,error_type=type(e).__name__,message=str(e)[:1000],
             no_automatic_vm_retry=True,independent_deletion_if_created=True,
             action='Inspect owned resource and retained logs. Recover/checksum results and clean up; setup fixes may reuse this same bounded VM only.'))
        raise


if __name__=='__main__':main()
