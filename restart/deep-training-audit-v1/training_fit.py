"""Supplemental seen-example fit check, not an independent acceptance evaluation."""
import json,time,gc,importlib.util
from pathlib import Path
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
spec=importlib.util.spec_from_file_location('training_fit_readonly',P/'restart/matched-improvement-reassessment-v1/run.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);r.R=R;r.V=V
base=r.read(R/'result.json');r.started=r.read(R/'started.json')['epoch'];r.positions=base['analysis_positions'];r.peak_rss=base['peak_rss_bytes'];assert not (R/'training-fit.json').exists()
train=r.read(P/'restart/broader-curriculum-v1/private/training.json');schedule=r.read(P/'restart/broader-curriculum-v1/private/schedules.json')['broad'][:100];ordered=[];seen=set()
for batch in schedule:
 for i in batch:
  if i<2592 and train[i]['family'] in ['full_name','printed_time'] and i not in seen:ordered.append(train[i]);seen.add(i)
bank=[]
for family in ['full_name','printed_time']:
 candidates=[x for x in ordered if x['family']==family];selected=[];answers=set()
 for row in candidates:
  answer=row['messages'][1]['content']
  if answer not in answers:selected.append(row);answers.add(answer)
 for row in candidates:
  if len(selected)>=16:break
  if row not in selected:selected.append(row)
 assert len(selected)==16 and len(answers)==12
 for row in selected:bank.append(dict(id='fit-'+row['id'],family=family,section='seen_training_fit',wording='exact_training_prompt',value_level='seen_training',condition=None,messages=row['messages'],oracle=[row['messages'][1]['content']]))
r.save(V/'training-fit-bank.json',bank)
r.save(R/'training-fit-freeze.json',dict(script_sha256=r.s.sha(Path(__file__)),bank_sha256=r.s.sha(V/'training-fit-bank.json'),selection='First distinct consumed training example per target string, then first remaining examples until16 per family. Both families cover all12 target strings. Selection frozen before outputs.',purpose='Tests whether 100 updates fitted seen name/time examples; diagnostic reuse of training data, not generalization.',original_started_epoch=r.started,maximum_aggregate_positions=2000000,maximum_aggregate_wall_seconds=900))
from sentencepiece import SentencePieceProcessor
sp=SentencePieceProcessor(model_file=str(r.s.TOK));out={}
for label,config in r.read(R/'plan.json')['models'].items():
 r.frozen();r.s.SOURCE=P/config['path'];r.s.SOURCE_SHA=config['sha256'];e,c=r.s.load();out[label]=r.generate(e,c,bank,sp,label+'-seen-fit');assert e.local_step==0;del e,c;gc.collect()
r.frozen();r.save(R/'training-fit.json',dict(models=out,aggregate_analysis_positions=r.positions,additional_positions=r.positions-base['analysis_positions'],aggregate_elapsed_seconds=time.time()-r.started,training_updates=0,optimizer_updates=0,checkpoint_promoted=False))
print(json.dumps(r.read(R/'training-fit.json'),indent=2))
