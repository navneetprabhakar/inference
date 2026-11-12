import json,subprocess,time,hashlib,datetime
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');out=ROOT/'results/broad-conversation-pilot-v1';out.mkdir(parents=True,exist_ok=False)
prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/broad-conversation-pilot-v1'
parent=ROOT/'results/review-004/sft/step-00000155';base=ROOT/'results/stage-004/step-00011445';toksha='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
def run(args,seconds):subprocess.run(['/usr/bin/python3','-u','-m',*args],check=True,timeout=seconds)
def quality(checkpoint,suite,name):
 sha=hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
 run(['cloud_training.nano_quality','--repo',str(ROOT/'nanochat-source'),'--checkpoint',str(checkpoint),'--checkpoint-manifest-sha256',sha,'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha256',toksha,'--suite',str(suite),'--seconds','540','--output',str(out/name)],600)
 return json.loads((out/name).read_text())
try:
 before={'automated_passed':1} # Matched 6B diagnostic baseline; not a fresh base-chat comparison
 deadline=datetime.datetime.fromtimestamp(min(time.time()+2700,1794476714-1200),datetime.timezone.utc).isoformat()
 run(['cloud_training.nano_sft','--manifest',str(ROOT/'sft/general-admitted-v1/manifest.json'),'--base',str(base),'--base-manifest-sha','dc1114859dd1cd9a3b9b82aeab5ff335be912366997f4e9d3b851465ee41994e','--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',toksha,'--repo',str(ROOT/'nanochat-source'),'--backup-prefix',prefix+'/checkpoints','--stage','general','--max-updates','1000','--batch-tokens','32768','--microbatch','8','--seed','103','--eval-rows','64','--eval-every-updates','250','--checkpoint-seconds','1800','--checkpoint-reserve-seconds','300','--deterministic','--deterministic-attention','--kernel-path',str(ROOT/'kernel'),'--kernel-sha','85b2e0c2ef47d48eb6a2131ddf6d9066c4dc44f87a231114cc4222b3a2575953','--deadline-utc',deadline,'--output',str(out/'sft')],2760)
 result=json.loads((out/'sft/result.json').read_text())
 if result.get('reason') not in ('pilot_update_limit','dataset_complete') or result['step']<1:raise RuntimeError('Broad pilot stopped unexpectedly; inspect saved result before continuation')
 checkpoint=Path(result['last_checkpoint']['path']);after=quality(checkpoint,ROOT/'repair-heldout-suite.json','after.json');original=quality(checkpoint,ROOT/'cloud_training/evaluation/conversation-tools-dev.json','original-suite.json')
 summary={'status':'complete','reference_6b_diagnostic_passed':before['automated_passed'],'updates':result['step'],'assistant_targets':result['assistant_targets'],'full_dataset_complete':result['status']=='complete','after_passed':after['automated_passed'],'total':after['automated_total'],'original_suite_passed':original['automated_passed'],'usable_model_claim':False,'next':'Review exact action and transcript regressions before broader tuning'}
except Exception as e:summary={'status':'blocked','error':str(e),'usable_model_claim':False}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
subprocess.run(['gcloud','storage','rsync','--recursive',str(out),prefix+'/results','--exclude=payload.pt','--quiet'],timeout=180,check=True)
