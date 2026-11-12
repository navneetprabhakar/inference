import json,subprocess,hashlib
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');OUT=ROOT/'results/conversation-prefix-diagnostic-v1';OUT.mkdir(parents=True,exist_ok=False)
prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/conversation-prefix-diagnostic-v1'
try:
 subprocess.run(['/usr/bin/python3','-u',str(ROOT/'conversation-prefix-launch/probe.py')],check=True,timeout=600)
 for name,checkpoint in [('before',ROOT/'results/instruction-repair-v3/sft/step-00000176'),('after',ROOT/'results/conversation-repair-v1/sft/step-00000090')]:
  sha=hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
  subprocess.run(['/usr/bin/python3','-u','-m','cloud_training.nano_quality','--repo',str(ROOT/'nanochat-source'),'--checkpoint',str(checkpoint),'--checkpoint-manifest-sha256',sha,'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha256','ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5','--suite',str(ROOT/'general-conversation-challenge.json'),'--seconds','540','--output',str(OUT/(name+'.json'))],check=True,timeout=600)
 summary={'status':'complete','purpose':'Prefix equivalence and fresh conversation response review','weights_modified':False}
except Exception as e:summary={'status':'blocked','error':str(e),'weights_modified':False}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
subprocess.run(['gcloud','storage','rsync','--recursive',str(OUT),prefix+'/results','--quiet'],check=True,timeout=180)
