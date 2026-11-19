"""Construct the native trainer invocation for a bounded qualification branch."""
import sys
from cloud_training import nano_pilot_window as window

def qualification_argv(ROOT,P,OUT,cfg,end,name,n,resume=None):
 prefix=cfg['backup_prefix']+'/qualification-v3/'+('split' if name.startswith('split') else 'signal' if name.startswith('signal') else name)+'/checkpoints'
 cmd=[sys.executable,'-m','cloud_training.nano_sft','--manifest',str(P/'broad-manifest.json'),'--quality-contract',str(P/'broad-contract.json'),
      '--block-plan',str(ROOT/'reports/ganesh-conversation-pilot-v1/exposure-plan.json'),'--block-arm','broad','--stage','targeted',
      '--base',str(ROOT/'parent'),'--base-manifest-sha',cfg['parent_manifest_sha256'],'--ancestor',str(ROOT/'ancestor'),
      '--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',cfg['tokenizer_sha256'],'--repo',str(ROOT/'nanochat-source'),
      '--output',str(OUT/name),'--batch-tokens','8192','--microbatch','1','--epochs','1','--seed','103','--lr-multiplier','.25',
      '--muon-kernel-mode','eager','--packing-buffer-size','1','--eval-every-updates','1','--eval-rows','128','--max-updates',str(n),
      '--deterministic','--checkpoint-reserve-seconds',str(window.CHECKPOINT),'--deadline-utc',end,'--backup-prefix',prefix]
 if resume:cmd+=['--resume',str(resume)]
 return cmd
