import json,subprocess,time,hashlib,datetime
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');out=ROOT/'results/instruction-repair-v1';out.mkdir(parents=True,exist_ok=False)
prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/instruction-repair-v1'
parent=ROOT/'results/broad-conversation-pilot-v1/sft/step-00001000';base=ROOT/'results/stage-004/step-00011445';toksha='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
def run(args,seconds):subprocess.run(['/usr/bin/python3','-u','-m',*args],check=True,timeout=seconds)
def quality(checkpoint,suite,name):
 sha=hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
 run(['cloud_training.nano_quality','--repo',str(ROOT/'nanochat-source'),'--checkpoint',str(checkpoint),'--checkpoint-manifest-sha256',sha,'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha256',toksha,'--suite',str(suite),'--seconds','540','--output',str(out/name)],600)
 return json.loads((out/name).read_text())
def status(stage):
 print('PHASE '+stage,flush=True)
 (out/'status.json').write_text(json.dumps({'stage':stage,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 subprocess.run(['gcloud','storage','cp',str(out/'status.json'),prefix+'/status.json','--quiet'],check=True,timeout=60)
try:
 status('baseline_evaluation')
 before=quality(parent,ROOT/'instruction-heldout-suite.json','before.json')
 status('targeted_training')
 deadline=datetime.datetime.fromtimestamp(min(time.time()+1800,1794476714-1200),datetime.timezone.utc).isoformat()
 run(['cloud_training.nano_sft','--manifest',str(ROOT/'sft/instruction-repair-admitted-v1/manifest.json'),'--base',str(parent),'--base-manifest-sha','876a849e8be1a131b6b879d1120bccb51610714f05c05ffae74367cce5a79c92','--ancestor',str(base),'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',toksha,'--repo',str(ROOT/'nanochat-source'),'--backup-prefix',prefix+'/checkpoints','--stage','targeted','--batch-tokens','32768','--microbatch','8','--seed','103','--eval-rows','64','--eval-every-updates','40','--checkpoint-seconds','1800','--checkpoint-reserve-seconds','300','--deterministic','--deterministic-attention','--kernel-path',str(ROOT/'kernel'),'--kernel-sha','85b2e0c2ef47d48eb6a2131ddf6d9066c4dc44f87a231114cc4222b3a2575953','--deadline-utc',deadline,'--output',str(out/'sft')],1860)
 result=json.loads((out/'sft/result.json').read_text())
 if result['status']!='complete':raise RuntimeError('Incomplete finite SFT; do not claim completed pilot')
 status('post_training_evaluation')
 checkpoint=Path(result['last_checkpoint']['path']);after=quality(checkpoint,ROOT/'instruction-heldout-suite.json','after.json');original=quality(checkpoint,ROOT/'cloud_training/evaluation/conversation-tools-dev.json','original-suite.json')
 summary={'status':'complete','before_passed':before['automated_passed'],'after_passed':after['automated_passed'],'total':after['automated_total'],'original_suite_passed':original['automated_passed'],'usable_model_claim':False,'next':'Review exact action and transcript regressions before broader tuning'}
except Exception as e:summary={'status':'blocked','error':str(e),'usable_model_claim':False}
print(json.dumps(summary),flush=True)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
subprocess.run(['gcloud','storage','rsync','--recursive',str(out),prefix+'/results','--exclude=.*payload[.]pt$','--quiet'],timeout=180,check=True)
