"""Explicit local control writer for retained VM diagnostics. Dry-run by default.

No provisioning or weight access. With --execute, polls every120s, publishes only
reviewed recipe commands using GCS generation CAS, and preserves raw evidence.
Unexpected root control writes are never overwritten. A blocker requires review.
"""
from __future__ import annotations
import argparse,datetime as dt,fcntl,hashlib,json,os
from pathlib import Path
import subprocess,tempfile,time
from cloud_training.nano_package import TOKENIZER_SHA,sha
from cloud_training.nano_campaign import validate_command
from cloud_training.nano_launch import uri

RECIPE_SHA='363a10155bf70c9744dce46a1391c1e32f5ba607ff7f33009c1a46cb4ef8b903'
DATA_PREFIX='gs://forge-ownbase-a100-20261110/ownbase-v2/sft/diagnostic-admitted-v1'
REMOTE_ROOT='/opt/ownbase-nano'

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def checksum(value):return hashlib.sha256(value).hexdigest()
def atomic(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.partial')
    with tmp.open('w') as f:json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def audit(path,event):
    with Path(path).open('a') as f:
        f.write(json.dumps({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),**event},sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

class Cloud:
    def __init__(self,deadline):self.deadline=deadline
    def run(self,args):
        seconds=min(45,self.deadline-time.time())
        if seconds<=0:raise TimeoutError('Watcher deadline expired')
        return subprocess.check_output(['gcloud','storage',*args,'--quiet'],timeout=seconds,stderr=subprocess.STDOUT)
    def snapshot(self,source):
        uri(source);meta=json.loads(self.run(['objects','describe',source,'--format=json']))
        # Telemetry overwrites unversioned objects. Retry only a proven overwrite
        # race, never an initially missing object, permission error or unchanged404.
        for attempt in range(3):
            generation=int(meta['generation'])
            try:return generation,self.run(['cat',source+'#'+str(generation)])
            except subprocess.CalledProcessError as error:
                if '404' not in str(error.output):raise
                fresh=json.loads(self.run(['objects','describe',source,'--format=json']))
                if int(fresh['generation'])==generation or attempt==2:raise
                meta=fresh
        raise AssertionError('Unreachable snapshot retry exhaustion')
    def read(self,source):return self.snapshot(source)[1]
    def cas(self,path,source,generation):return self.run(['cp',str(path),source,'--if-generation-match='+str(generation)])

def reviewed_inputs(recipe_path,admitted):
    if sha(recipe_path)!=RECIPE_SHA:raise ValueError('Only frozen diagnostic-v3 recipe permitted')
    recipe=json.loads(Path(recipe_path).read_text())
    msha,files=admitted_files(admitted,DATA_PREFIX)
    return recipe,msha,files

def admitted_files(admitted,prefix):
    root=Path(admitted)
    manifest=json.loads((root/'manifest.json').read_text());receipt=json.loads((root/'admission.json').read_text())
    if manifest.get('training_admitted') is not True or receipt.get('training_admitted') is not True:raise ValueError('Root-admitted diagnostic data required')
    if manifest['tokenizer_sha256']!=TOKENIZER_SHA or sha(root/'admission.json')!=manifest['admission']['sha256']:raise ValueError('Admission identity mismatch')
    hashes=[]
    for split in ('train','validation'):
        item=manifest[split]
        if item['file']!=split+'.jsonl' or sha(root/item['file'])!=item['sha256']:raise ValueError('Changed diagnostic split')
        hashes.append(item['sha256'])
    if receipt['jsonl_sha256']!=hashes:raise ValueError('Admission does not bind both splits')
    files=[{'path':'sft/'+root.name+'/'+name,'uri':prefix+'/'+name,'sha256':sha(root/name),'bytes':(root/name).stat().st_size} for name in ('manifest.json','admission.json','train.jsonl','validation.jsonl')]
    return sha(root/'manifest.json'),files

def evidence_json(cloud,entry,suffix,local):
    found=[e for e in entry['evidence'] if e['uri'].endswith(suffix)]
    if len(found)!=1:raise ValueError('Unique committed evidence artifact required: '+suffix)
    raw=cloud.read(found[0]['uri'])
    if checksum(raw)!=found[0]['sha256']:raise ValueError('Evidence hash mismatch')
    Path(local).write_bytes(raw)
    return json.loads(raw)

def checkpoint_from_result(cloud,result):
    last=result['last_checkpoint'];upload=last['upload'];raw=cloud.read(upload['remote_prefix']+'/manifest.json')
    if json.loads(raw)!=upload['manifest'] or last['step']!=result['step']:raise ValueError('Checkpoint result/remote manifest mismatch')
    marker=json.loads(cloud.read(upload['remote_prefix']+'/COMMITTED'))
    if marker.get('manifest_sha256')!=checksum(raw):raise ValueError('Checkpoint lacks matching COMMITTED marker')
    path=last['path']
    if not path.startswith(REMOTE_ROOT+'/results/') or '..' in Path(path).parts:raise ValueError('Checkpoint path outside controller outputs')
    return path,checksum(raw)

def command_base(config,step,watch_id):
    return {'schema':1,'campaign_sha256':config['campaign_sha256'],'expected_step':step,'reviewed':True,
            'review_receipt':'diagnostic-admitted-v1;recipe-sha256:'+RECIPE_SHA,'watch_id':watch_id}

def sft_command(config,recipe,files,step,milestone,checkpoint,manifest_sha):
    replacements={'admitted_manifest':REMOTE_ROOT+'/sft/diagnostic-admitted-v1/manifest.json','base_checkpoint':checkpoint,'base_manifest_sha':manifest_sha,
                  'tokenizer_dir':REMOTE_ROOT+'/tokenizer','repo':REMOTE_ROOT+'/nanochat-source','isolated_sft_gcs_prefix':config['backup_prefix'].rsplit('/',1)[0]+f'/diagnostic-{milestone}b',
                  'kernel_dir':REMOTE_ROOT+'/kernel','kernel_sha':config['kernel_sha256']}
    template=recipe['sft_argv_template'][3:];args=[];i=0
    while i<len(template):
        if template[i] in ('--output','--deadline-utc'):i+=2;continue
        value=template[i]
        for key,val in replacements.items():value=value.replace('{'+key+'}',val)
        if '{' in value:raise ValueError('Unresolved diagnostic recipe argument')
        args.append(value);i+=1
    return {**command_base(config,step,f'{milestone}b-sft'),'action':'run_stage','stage':'sft','seconds':480,'expected_end_step':155,'args':args,'fetch_files':files}

def quality_command(config,step,milestone,checkpoint,manifest_sha):
    return {**command_base(config,step,f'{milestone}b-quality'),'action':'run_stage','stage':'quality','seconds':180,
            'args':['--repo',REMOTE_ROOT+'/nanochat-source','--checkpoint',checkpoint,'--checkpoint-manifest-sha256',manifest_sha,
                    '--tokenizer',REMOTE_ROOT+'/tokenizer','--tokenizer-sha256',TOKENIZER_SHA,'--suite',REMOTE_ROOT+'/cloud_training/evaluation/conversation-tools-dev.json',
                    '--seconds','120','--repetition-penalty','1.0']}

def quality_vector(report,recipe,manifest_sha):
    if report.get('status')!='development_checks_complete' or report.get('diagnostic_base_mode') is not False:raise ValueError('Complete SFT quality assessment required')
    if report.get('suite_sha256')!=recipe['comparison']['quality_suite_sha256'] or report.get('repetition_penalty')!=1.0:raise ValueError('Quality suite/decoding changed')
    identity=report['identity']
    if identity.get('source_manifest_sha256')!=manifest_sha or identity.get('batch_tokens')!=32768 or identity.get('microbatch')!=8 or identity.get('horizon_updates')!=155 or report.get('step')!=155:
        raise ValueError('Quality checkpoint is not the identical complete diagnostic recipe')
    scores={str(r['session'])+':'+str(r['turn']):bool(r['assessment']['automated_pass']) for r in report['records'] if not r['assessment']['manual_review_required']}
    if not scores or len(scores)!=report['automated_total'] or sum(scores.values())!=report['automated_passed']:raise ValueError('Inconsistent narrow automated score')
    recipe_identity={k:identity.get(k) for k in ('stage','config','seed','batch_tokens','microbatch','lr_batch_scale','horizon_updates','packed_rows','torch','attention','kernel_sha256','numerical_mode','eval_rows','eval_every_updates','adapter_hashes')}
    return {'recipe_identity':recipe_identity,'scores':scores,'suite_sha256':report['suite_sha256'],'recipe_sha256':RECIPE_SHA,'source_manifest_sha256':manifest_sha,'runner_sha256':report['runner_sha256']}

def comparison(base,current):
    for key in ('suite_sha256','recipe_sha256','source_manifest_sha256','runner_sha256','recipe_identity'):
        if base.get(key)!=current.get(key):raise ValueError('Comparison provenance differs')
    if base['scores'].keys()!=current['scores'].keys():raise ValueError('Comparison tasks differ')
    regressions=[k for k,v in base['scores'].items() if v and not current['scores'][k]]
    gains=[k for k,v in base['scores'].items() if not v and current['scores'][k]]
    return {'continue_base':not regressions and bool(gains),'regressions':regressions,'gains':gains,'manual_review_required':True}

class Watcher:
    def __init__(self,config,recipe,manifest_sha,files,directory,cloud,initial_control_sha,final_inputs=None):
        self.config=config;self.recipe=recipe;self.manifest_sha=manifest_sha;self.files=files;self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.final_inputs=final_inputs
        self.cloud=cloud;self.control=config['retained']['control_uri'];self.initial_sha=initial_control_sha
        self.state_path=self.directory/'state.json';self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {'schema':1,'sent':{},'completed':{}}
        identity={'run_id':config['run_id'],'campaign_sha256':config['campaign_sha256'],'recipe_sha256':RECIPE_SHA,'manifest_sha256':manifest_sha,'control_uri':self.control,'final_inputs':None if final_inputs is None else {k:v[0] for k,v in final_inputs.items()}}
        if 'identity' in self.state and self.state['identity']!=identity:raise ValueError('Watcher state belongs to another campaign/recipe')
        self.state['identity']=identity;self.save()
    def save(self):atomic(self.state_path,self.state)
    def event(self,event):audit(self.directory/'events.jsonl',event)
    def block(self,reason):
        self.state['blocker']=reason;self.save();atomic(self.directory/'BLOCKER.json',{'reason':reason,'utc':dt.datetime.now(dt.timezone.utc).isoformat()});self.event({'event':'blocked','reason':reason})
    def publish(self,command):
        envelope={'command':command,'sha256':checksum(canonical(command))};raw=(json.dumps(envelope,sort_keys=True,indent=2)+'\n').encode()
        missing=False
        try:generation,existing=self.cloud.snapshot(self.control)
        except subprocess.CalledProcessError as error:
            if self.initial_sha!='0'*64 or 'control_generation' in self.state or not any(x in str(error.output) for x in ('404','not found','not exist')):raise
            generation,existing,missing=0,b'',True
        pending=self.state.get('pending')
        if pending:
            if checksum(existing)==pending['raw_sha256']:
                self.state['control_generation']=generation;self.state['control_sha256']=checksum(existing);self.state['sent'][pending['watch_id']]=envelope['sha256'];self.state.pop('pending');self.save();return
            if generation!=pending['expected_generation']:raise ValueError('Unexpected control writer changed pending CAS')
        expected=self.state.get('control_sha256',checksum(b'') if missing else self.initial_sha)
        if checksum(existing)!=expected or ('control_generation' in self.state and generation!=self.state['control_generation']):raise ValueError('Unexpected root/control command; refusing overwrite')
        validate_command(envelope,self.config,command['expected_step'],generation+1,generation)
        path=self.directory/'pending-command.json';path.write_bytes(raw)
        self.state['pending']={'watch_id':command['watch_id'],'raw_sha256':checksum(raw),'expected_generation':generation};self.save()
        self.cloud.cas(path,self.control,generation)
        new_generation,new_raw=self.cloud.snapshot(self.control)
        if new_generation<=generation or checksum(new_raw)!=checksum(raw):raise ValueError('Control CAS readback differs')
        self.state.update(control_generation=new_generation,control_sha256=checksum(raw));self.state['sent'][command['watch_id']]=envelope['sha256'];self.state.pop('pending');self.save()
        self.event({'event':'command_published','generation':new_generation,'command':command,'sha256':envelope['sha256']})
    def tick(self,status):
        summary={k:status.get(k) for k in ('status','reason','step','milestone_tokens')};summary['reviews']=[r.get('command_sha256') for r in status.get('review_stages',[])]
        key=checksum(canonical(summary))
        if self.state.get('status_sha256')!=key:self.event({'event':'state_change','state':summary});self.state['status_sha256']=key;self.save()
        if self.state.get('blocker'):return
        if status.get('reason')=='protected_finish_boundary':
            if self.final_inputs is None:self.block('ready_for_final_tuning_requires_root_review')
            else:self.finish_tick(status)
            return
        if status.get('status') in ('failed_closed','stopped'):self.block('controller_terminal:'+str(status.get('reason',status.get('error'))));return
        if status.get('status')!='awaiting_review' or status.get('reason')!='milestone_quality_review':return
        milestone={3_000_000_000:3,6_000_000_000:6}.get(status.get('milestone_tokens'))
        if milestone is None:raise ValueError('Unsupported automatic milestone')
        step=status['step'];sft_id=f'{milestone}b-sft';quality_id=f'{milestone}b-quality'
        reviews={r.get('command',{}).get('watch_id'):r for r in status.get('review_stages',[])}
        if sft_id not in self.state['sent']:
            result=evidence_json(self.cloud,status['stages'][-1],'/result.json',self.directory/f'{milestone}b-base-result.json')
            checkpoint,msha=checkpoint_from_result(self.cloud,result)
            self.publish(sft_command(self.config,self.recipe,self.files,step,milestone,checkpoint,msha));return
        if sft_id not in reviews:return
        sft=reviews[sft_id]
        if sft.get('sft_assessment',{}).get('finite_dataset_complete') is not True or sft['sft_assessment'].get('step')!=155:
            self.block(f'{milestone}B_instruction_diagnostic_incomplete');return
        if quality_id not in self.state['sent']:
            result=evidence_json(self.cloud,sft,'/sft/result.json',self.directory/f'{milestone}b-sft-result.json')
            if result.get('status')!='complete' or result.get('step')!=155 or result['identity'].get('source_manifest_sha256')!=self.manifest_sha:raise ValueError('Incomplete or mismatched SFT result')
            expected_parent=sft['command']['args'][sft['command']['args'].index('--base-manifest-sha')+1]
            if result['identity'].get('parent_bundle_manifest_sha256')!=expected_parent:raise ValueError('Diagnostic parent checkpoint differs from dispatched recipe')
            checkpoint,msha=checkpoint_from_result(self.cloud,result)
            self.publish(quality_command(self.config,step,milestone,checkpoint,msha));return
        if quality_id not in reviews:return
        report=evidence_json(self.cloud,reviews[quality_id],'/quality.json',self.directory/f'{milestone}b-quality-transcript.json')
        vector=quality_vector(report,self.recipe,self.manifest_sha)
        if milestone==3:
            self.state['baseline']=vector;self.save()
        else:
            if 'baseline' not in self.state:raise ValueError('Missing completed3B baseline')
            result=comparison(self.state['baseline'],vector);atomic(self.directory/'6b-comparison.json',result)
            if not result['continue_base']:self.block('6B_no_improvement_or_regression_requires_manual_review');return
        command={**command_base(self.config,step,f'{milestone}b-continue'),'action':'continue_base'}
        if command['watch_id'] not in self.state['sent']:self.publish(command)
        self.state['completed'][str(milestone)]=vector;self.save()

    def finish_tick(self,status):
        step=status['step'];reviews={r.get('command',{}).get('watch_id'):r for r in status.get('review_stages',[])}
        if 'final_base' not in self.state:
            result=evidence_json(self.cloud,status['stages'][-1],'/result.json',self.directory/'final-base-result.json')
            path,msha=checkpoint_from_result(self.cloud,result);self.state['final_base']={'path':path,'sha256':msha};self.save()
        base=self.state['final_base']
        phases=[('general','sft',9000),('general-quality','quality',600),('targeted','sft',1800),('targeted-quality','quality',600)]
        for index,(name,kind,seconds) in enumerate(phases):
            watch_id='final-'+name
            if watch_id not in self.state['sent']:
                needed=sum(p[2] for p in phases[index:])+300
                if self.cloud.deadline-time.time()<needed:self.block('insufficient_remaining_provider_budget_for_'+watch_id);return
                command={**command_base(self.config,step,watch_id),'action':'run_stage','stage':kind,'seconds':seconds}
                if kind=='sft':
                    msha,files=self.final_inputs[name]
                    parent=base if name=='general' else self.state['final-general-checkpoint']
                    args=['--manifest',REMOTE_ROOT+'/sft/'+name+'-admitted-v1/manifest.json','--base',parent['path'],'--base-manifest-sha',parent['sha256'],
                          '--tokenizer',REMOTE_ROOT+'/tokenizer','--tokenizer-sha',TOKENIZER_SHA,'--repo',REMOTE_ROOT+'/nanochat-source',
                          '--backup-prefix',self.config['backup_prefix'].rsplit('/',1)[0]+'/final-'+name+'/checkpoints',
                          '--stage',name,'--batch-tokens','524288' if name=='general' else '32768','--microbatch','8',
                          '--seed','103','--eval-rows','64','--eval-every-updates','200' if name=='general' else '64',
                          '--checkpoint-seconds','1800','--checkpoint-reserve-seconds','120','--deterministic','--deterministic-attention',
                          '--kernel-path',REMOTE_ROOT+'/kernel','--kernel-sha',self.config['kernel_sha256']]
                    if name=='targeted':args+=['--ancestor',base['path']]
                    command.update(args=args,fetch_files=files,review_receipt='root-approved-full-sft-admission-review;manifest-sha256:'+msha)
                else:
                    parent=self.state['final-'+name.split('-')[0]+'-checkpoint']
                    q=quality_command(self.config,step,name,parent['path'],parent['sha256']);command.update(args=q['args'])
                    where=command['args'].index('--seconds');command['args'][where+1]='540'  # Frozen controller caps outer quality stages at600; allow60s supervisor cleanup.
                self.publish(command);return
            if watch_id not in reviews:return
            if watch_id in self.state.get('final_completed',{}):continue
            entry=reviews[watch_id]
            if kind=='sft':
                if entry.get('sft_assessment',{}).get('finite_dataset_complete') is not True:self.block(watch_id+'_incomplete');return
                result=evidence_json(self.cloud,entry,'/sft/result.json',self.directory/(watch_id+'-result.json'))
                if result.get('status')!='complete' or result['identity'].get('source_manifest_sha256')!=self.final_inputs[name][0] or result['identity'].get('stage')!=name:
                    raise ValueError('Final SFT did not complete approved finite dataset/stage')
                parent=base if name=='general' else self.state['final-general-checkpoint']
                if result['identity'].get('parent_bundle_manifest_sha256')!=parent['sha256']:raise ValueError('Final SFT immutable parent differs')
                path,msha=checkpoint_from_result(self.cloud,result);self.state[watch_id+'-checkpoint']={'path':path,'sha256':msha}
            else:
                result=evidence_json(self.cloud,entry,'/quality.json',self.directory/(watch_id+'-transcript.json'))
                parent=self.state['final-'+name.split('-')[0]+'-checkpoint']
                if result.get('status')!='development_checks_complete' or result.get('diagnostic_base_mode') is not False or result.get('checkpoint_manifest_sha256')!=parent['sha256'] or result.get('suite_sha256')!=self.recipe['comparison']['quality_suite_sha256']:
                    raise ValueError('Final quality incomplete or provenance mismatch')
            self.state.setdefault('final_completed',{})[watch_id]={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'quality_pass_claimed':False};self.save()
        self.block('final_quality_complete_awaiting_root_acceptance_no_usable_claim')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','recipe','admitted','directory'):p.add_argument('--'+name,required=True)
    initial=p.add_mutually_exclusive_group(required=True)
    initial.add_argument('--initial-control-sha256')
    initial.add_argument('--initial-control-absent',action='store_true')
    p.add_argument('--final-general');p.add_argument('--final-targeted')
    p.add_argument('--deadline-epoch',required=True,type=float);p.add_argument('--execute',action='store_true')
    a=p.parse_args();config=json.loads(Path(a.config).read_text());recipe,msha,files=reviewed_inputs(a.recipe,a.admitted)
    if not time.time()<a.deadline_epoch<=time.time()+32*3600:raise ValueError('Watcher deadline must be within32h')
    if bool(a.final_general)!=bool(a.final_targeted):raise ValueError('Both admitted final datasets required')
    final_inputs=None if not a.final_general else {name:admitted_files(path,'gs://forge-ownbase-a100-20261110/ownbase-v2/sft/'+name+'-admitted-v1') for name,path in [('general',a.final_general),('targeted',a.final_targeted)]}
    if not a.execute:
        print(json.dumps({'status':'dry_run_no_cloud','recipe_sha256':RECIPE_SHA,'manifest_sha256':msha,'fetch_files':files,'poll_seconds':120},indent=2));return
    root=Path(a.directory);root.mkdir(parents=True,exist_ok=True)
    with (root/'.writer.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cloud=Cloud(a.deadline_epoch);watch=Watcher(config,recipe,msha,files,root,cloud,'0'*64 if a.initial_control_absent else a.initial_control_sha256,final_inputs)
        source='gs://forge-ownbase-a100-20261110/production-logs/'+config['run_id']+'/results/campaign-status.json'
        startup_until=min(a.deadline_epoch,time.time()+900)
        while time.time()<a.deadline_epoch:
            try:watch.tick(json.loads(cloud.read(source)))
            except subprocess.CalledProcessError as error:
                if time.time()<startup_until and any(x in str(error.output) for x in ('404','not found','not exist')):
                    time.sleep(min(120,max(0,a.deadline_epoch-time.time())));continue
                watch.block(str(error));return 2
            except Exception as error:watch.block(str(error));return 2
            if watch.state.get('blocker'):return 2
            time.sleep(min(120,max(0,a.deadline_epoch-time.time())))
        watch.block('watcher_hard_deadline_reached');return 2

if __name__=='__main__':raise SystemExit(main())
