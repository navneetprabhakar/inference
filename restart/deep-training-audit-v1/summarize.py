"""Read-only aggregation of frozen forward and gradient evidence."""
import json,math,statistics
from pathlib import Path
from collections import defaultdict
import numpy as np
from sentencepiece import SentencePieceProcessor
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
sp=SentencePieceProcessor(model_file=str(P/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'));result=read(R/'result.json');summary={}
retbase=read(P/'restart/broader-curriculum-v1/private/parent-retention-responses.json');retafter=read(P/'restart/broader-curriculum-v1/private/broad-retention-100-responses.json');lookup={(r['id'],r['turn']):r for r in retbase};lost={(r['id'],r['turn']) for r in retafter if lookup[(r['id'],r['turn'])]['correct'] and not r['correct']};formatloss={(r['id'],r['turn']) for r in retafter if r['response'].startswith('The ') and r['response'].split()[-1].strip('.').casefold()==r['expected'].strip('.').casefold()}
for model in ['short_answer','broader_candidate']:
 rows=read(V/(model+'-forward.json'))
 def metrics(selected):
  contents=[(p,a,g) for r in selected for p,a,g in zip(r['gold_probabilities'][:-1],r['argmax_ids'][:-1],r['gold_ids'][:-1])]
  return dict(answers=len(selected),gold_target_nll=sum(r['sequence_nll'] for r in selected)/sum(len(r['gold_ids']) for r in selected) if selected else None,content_argmax_accuracy=sum(a==g for p,a,g in contents)/len(contents) if contents else None,premature_eos_top1_content_positions=sum(a==2 for p,a,g in contents),content_positions=len(contents),first_gold_top1=sum(r['argmax_ids'][0]==r['gold_ids'][0] for r in selected),first_gold_probability_mean=float(np.mean([r['gold_probabilities'][0] for r in selected])) if selected else None,first_eos_top1=sum(r['argmax_ids'][0]==2 for r in selected))
 byfamily={f:metrics([r for r in rows if r['source']=='matched' and r['section']=='copy' and r['mode']=='actual' and r['family']==f]) for f in ['color','location','owner','time']}
 history={mode:metrics([r for r in rows if r['source']=='matched' and r['section']=='history' and r['turn']>0 and r['mode']==mode]) for mode in ['actual','gold']}
 retention=metrics([r for r in rows if r['source']=='retention' and r['mode']=='actual']);oldtrain=metrics([r for r in rows if r['source']=='old_training']);oldtrain['all_reference_targets_argmax_correct']=sum(r['argmax_ids']==r['gold_ids'] for r in rows if r['source']=='old_training')
 fmt=[r for r in rows if r['source']=='retention' and r['mode']=='actual' and (r['id'],r['turn']) in formatloss]
 gaps=[math.log(max(r['gold_probabilities'][0],1e-30)/max(r['the_probabilities'][0],1e-30)) for r in fmt]
 raw=read(P/f'restart/matched-improvement-reassessment-v1/private/{model}-responses.json');early=[]
 for r in raw:
  gold=sp.encode(r['expected']);generated=r['generated_ids']
  if r['eos'] and 0<len(generated)<len(gold) and generated==gold[:len(generated)]:early.append(dict(id=r['id'],turn=r['turn'],family=r['family'],section=r['section'],generated_tokens=len(generated),required_content_tokens=len(gold)))
 save(V/(model+'-correct-prefix-early-eos.json'),early)
 gradients=result['models'][model]['gradient_samples'];balanced=[]
 for r in gradients:
  no=r['old_gradient_norm'];nn=r['new_gradient_norm'];nr=r['narrative_gradient_norm'];don=r['cosine_old_new']*no*nn;dor=r['cosine_old_narrative']*no*nr
  balanced.append(.25*no*no+.25*don+.5*dor)
 summary[model]=dict(copy_teacher_forcing=byfamily,history_conditioning=history,retention=retention,old_training=oldtrain,format_only_lost_cases=len(fmt),mean_log_gold_first_token_over_The_on_format_losses=float(np.mean(gaps)),correct_prefix_early_eos_answers=len(early),correct_prefix_early_eos_by_family={f:sum(r['family']==f for r in early) for f in sorted({r['family'] for r in early})},old_new_gradient_cosines=[r['cosine_old_new'] for r in gradients],historical_combined_old_gradient_dots=[r['old_gradient_dot_historical_combined'] for r in gradients],separately_normalized_equal_old_new_old_gradient_dots=balanced,weighted_new_to_old_gradient_norm_ratios=[(r['new_targets']*r['new_gradient_norm'])/(r['old_targets']*r['old_gradient_norm']) for r in gradients])
save(R/'summary.json',dict(models=summary,training_updates=0,interpretation_limits='Gold continuation/previous-history diagnostics are not free-generation successes. Four gradient samples at checkpoint weights, not gradients recorded along the historical trajectory; dot sign predicts infinitesimal SGD old-loss direction, not the actual AdamW update. Equal group normalization effects here are analytical, not a trained ablation. Token length, task and exposure are confounded.'))
print(json.dumps(read(R/'summary.json'),indent=2))
