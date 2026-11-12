import json,subprocess,time,hashlib,datetime
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');out=ROOT/'results/repair-pilot-v1';out.mkdir(parents=True,exist_ok=False)
prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/repair-pilot-v1'
parent=ROOT/'results/review-004/sft/step-00000155';base=ROOT/'results/stage-004/step-00011445';toksha='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
def run(args,seconds):subprocess.run(['/usr/bin/python3','-u','-m',*args],check=True,timeout=seconds)
def quality(checkpoint,suite,name):
 sha=hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
 run(['cloud_training.nano_quality','--repo',str(ROOT/'nanochat-source'),'--checkpoint',str(checkpoint),'--checkpoint-manifest-sha256',sha,'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha256',toksha,'--suite',str(suite),'--seconds','540','--output',str(out/name)],600)
 return json.loads((out/name).read_text())
try:
 before=quality(parent,ROOT/'repair-heldout-suite.json','before.json')
 deadline=datetime.datetime.fromtimestamp(min(time.time()+1800,1794476714-1200),datetime.timezone.utc).isoformat()
 run(['cloud_training.nano_sft','--manifest',str(ROOT/'sft/targeted-context-admitted-v3/manifest.json'),'--base',str(parent),'--base-manifest-sha','32508e8aa15e9097b0535d0abcb5ef92db39c3ed3795f44314e76d9daa93bbe7','--ancestor',str(base),'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',toksha,'--repo',str(ROOT/'nanochat-source'),'--backup-prefix',prefix+'/checkpoints','--stage','targeted','--batch-tokens','32768','--microbatch','8','--seed','103','--eval-rows','64','--eval-every-updates','243','--checkpoint-seconds','1800','--checkpoint-reserve-seconds','300','--deterministic','--deterministic-attention','--kernel-path',str(ROOT/'kernel'),'--kernel-sha','85b2e0c2ef47d48eb6a2131ddf6d9066c4dc44f87a231114cc4222b3a2575953','--deadline-utc',deadline,'--output',str(out/'sft')],1860)
 result=json.loads((out/'sft/result.json').read_text())
 if result['status']!='complete':raise RuntimeError('Incomplete finite SFT; do not claim completed pilot')
 checkpoint=Path(result['last_checkpoint']['path']);after=quality(checkpoint,ROOT/'repair-heldout-suite.json','after.json');original=quality(checkpoint,ROOT/'cloud_training/evaluation/conversation-tools-dev.json','original-suite.json')
 summary={'status':'complete','before_passed':before['automated_passed'],'after_passed':after['automated_passed'],'total':after['automated_total'],'original_suite_passed':original['automated_passed'],'usable_model_claim':False,'next':'Review exact action and transcript regressions before broader tuning'}
except Exception as e:summary={'status':'blocked','error':str(e),'usable_model_claim':False}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
subprocess.run(['gcloud','storage','rsync','--recursive',str(out),prefix+'/results','--exclude=payload.pt','--quiet'],timeout=180,check=True)
