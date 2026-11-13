"""Local retained-baseline runtime qualification, not promotion of a new model."""
import time,json,resource,sys
from pathlib import Path
sys.path.insert(0,str(Path('.').resolve()))
import torch
from cloud_training.nano_serve import load_own_bundle,BrokerChat,generate_action
start=time.monotonic();torch.set_num_threads(4)
model,tok,meta=load_own_bundle('runs/nanochat-source','runs/literal-state-repair-v1/results/sft/step-00000605','runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps')
loaded=time.monotonic();chat=BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n,repetition_penalty=1.0),context=2048,reply_budget=64)
results=[]
for prompt in ['Use calculate to subtract 19 from 73. Reply with only the numeric result.','What was the result of that subtraction? Reply with only the number.']:
 t=time.monotonic();result=chat.turn(prompt,policy={'permit_calls':True,'allowed_names':['calculate','convert']});results.append({'user':prompt,'seconds':time.monotonic()-t,'result':result})
report={'checkpoint':'literal-state-repair-v1/step-00000605','torch':torch.__version__,'device':'mps','load_seconds':loaded-start,'total_seconds':time.monotonic()-start,'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'mps_allocated_bytes':torch.mps.current_allocated_memory(),'mps_driver_bytes':torch.mps.driver_allocated_memory(),'records':results,'scope':'Existing retained baseline onactualM4; not newtraining or broad acceptance'}
Path('runs/ownbase-budget50-v1/local-baseline-probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
