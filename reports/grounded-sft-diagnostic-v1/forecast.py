"""Measured CPU metadata forecast; no model or training invocation."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import own_base_sft_train as t
OUT=Path(__file__).resolve().parent

def main():
 a=json.loads((ROOT/'reports/grounded-sft-preflight-v1/allocation.json').read_text());hpath=ROOT/'runs/own-base-grounded-sft-preflight-01/hardware-receipt.json';h=json.loads(hpath.read_text())
 if h['state']!='PASS':raise ValueError('hardware PASS required')
 data=t.Sources(a['datasets']);estimates={}
 for role,source in a['sources'].items():
  rows=sorted([r for r in data.rows['train'] if r['_source']==role],key=lambda r:(r['length'],r['doc_id'],r['turn']))
  def estimate(subset,measurement):
   return max(len(subset)*measurement['seconds']/measurement['rows'],sum(r['length']for r in subset)*measurement['seconds']/measurement['input_tokens'])
  measures=[m for m in h['timing']if m['source']==role and m['phase']=='measured' and m['kind']=='update']
  if role=='four_call_extension':training=estimate(rows,measures[0])
  else:
   training=0
   for q in range(4):
    group=rows[q*len(rows)//4:(q+1)*len(rows)//4];m=next(m for m in measures if m['stratum']==f'length-quartile-{q+1}');training+=estimate(group,m)
  evrows=[r for r in data.rows['validation']if r['_source']==role];m=next(m for m in h['timing']if m['source']==role and m['kind']=='evaluation');evaluation=estimate(evrows,m)
  estimates[role]=dict(training_seconds=training,one_evaluation_seconds=evaluation,actual_max_length=max(r['length']for r in rows),preflight_max_length=h['coverage'][role]['max_training_length'])
 training=sum(x['training_seconds']for x in estimates.values());evaluation=sum(x['one_evaluation_seconds']for x in estimates.values())
 # 39 periodic saves + initial + 3 evaluation saves + terminal protection; leases may add saves.
 saves=44;nominal=training+3*evaluation
 bound=1.75*(training*(1+100/a['updates'])+4*evaluation)+saves*30+600
 result=dict(hardware_sha256=t.digest(hpath),method='per-source training length quartiles, maximum row/input scaling; extension final-only timing extrapolated to all rows; evaluation maximum row/input scaling',sources=estimates,nominal_compute_seconds=nominal,planning_seconds=bound,assumed_slowdown=1.75,unmeasured_save_seconds=30,nominal_save_calls=saves,initialization_resume_allowance_seconds=600,limits='Short preflight is not sustained throughput; checkpoint cost unmeasured; extension all-row length tail exceeds final-only measurement. No quality ETA.')
 (OUT/'forecast.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
