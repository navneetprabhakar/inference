"""Read-only compact stage status; no model imports."""
import json,time
from pathlib import Path
r=Path(__file__).resolve().parent

def main():
    if (r/'train-failure.json').exists():result={'status':'FAILED','failure':json.loads((r/'train-failure.json').read_text())['error']}
    elif (r/'stage2-result.json').exists():result=json.loads((r/'stage2-result.json').read_text());result={k:result[k] for k in ['status','additional_updates','additional_training_targets','evaluation']}
    elif (r/'progress.json').exists():
      p=json.loads((r/'progress.json').read_text());result={k:p[k] for k in ['status','additional_update','targets','loss','tokens_per_second']};result['remaining_minutes_estimate']=(74973184-p['targets'])/p['tokens_per_second']/60
    else:result={'status':'STARTING'}
    if (r/'latest.json').exists():result['last_recoverable_update']=json.loads((r/'latest.json').read_text())['additional_updates']
    if (r/'resources.jsonl').exists():
      x=json.loads((r/'resources.jsonl').read_text().splitlines()[-1]);result['RSS_GiB']=round(x['RSS_bytes']/1024**3,3);result['additional_swap_MiB']=round(x['additional_swap_bytes']/1024**2,3)
    result['next_stage_authorized']=False;print(json.dumps(result))
if __name__=='__main__':main()
