"""Read-only exposure, label-distribution and evaluation-design audit."""
import json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from sentencepiece import SentencePieceProcessor
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
sp=SentencePieceProcessor(model_file=str(P/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
train=read(P/'restart/broader-curriculum-v1/private/training.json');schedule=read(P/'restart/broader-curriculum-v1/private/schedules.json')['broad'][:100]
by=defaultdict(Counter);unique=defaultdict(set);ratios=[]
for batch in schedule:
 old=new=0
 for i in batch:
  row=train[i];group='old_rehearsal' if i>=2592 else row['family'];n=sum(row['mask']);eos=len(row['messages'])//2
  by[group].update(examples=1,targets=n,eos_targets=eos,content_targets=n-eos);unique[group].add(row['id'])
  if i>=2592:old+=n
  else:new+=n
 ratios.append(old/(old+new))
for group in by:by[group]['unique_conversations']=len(unique[group])
short=read(P/'restart/factual-binding-v1/private/training.json');shortcounts=Counter()
for row in short:shortcounts.update(targets=sum(row['mask']),eos_targets=len(row['messages'])//2,content_targets=sum(row['mask'])-len(row['messages'])//2)
# Determine whether generated serial training cases vary output length and EOS frequency.
answer_vocab={}
for family in sorted({r['family'] for r in train[:2592]}):
 rows=[r for r in train[:2592] if r['family']==family];answers=[m['content'] for r in rows for m in r['messages'] if m['role']=='assistant']
 answer_vocab[family]=dict(conversations=len(rows),unique_answer_strings=len(set(answers)),answer_token_lengths=dict(Counter(len(sp.encode(a)) for a in answers)))
matched=read(P/'restart/matched-improvement-reassessment-v1/private/bank.json');lengths={}
for model in ['short_answer','broader_candidate']:
 rows=read(P/f'restart/matched-improvement-reassessment-v1/private/{model}-responses.json');lookup={r['id']:r for r in matched};groups={}
 for bucket in ['1','2','3-4','5+']:
  selected=[r for r in rows if r['section']=='copy' and (lambda n: ('1' if n==1 else '2' if n==2 else '3-4' if n<=4 else '5+'))(len(sp.encode(r['expected'])))==bucket]
  groups[bucket]=dict(cases=len(selected),exact=sum(r['exact_normalized'] for r in selected))
 lengths[model]=groups
save(R/'inventory.json',dict(actual_broader_update_count=100,by_consumed_family={g:dict(v) for g,v in by.items()},old_example_fraction=.25,old_target_fraction=by['old_rehearsal']['targets']/sum(v['targets'] for v in by.values()),mean_per_batch_old_target_weight=sum(ratios)/len(ratios),mean_old_objective_coefficient=.5*sum(ratios)/len(ratios),mean_new_objective_coefficient=.5*(1-sum(ratios)/len(ratios)),narrative_objective_coefficient=.5,short_bank_label_distribution=dict(shortcounts),short_bank_eos_target_fraction=shortcounts['eos_targets']/shortcounts['targets'],new_bank_answer_diversity=answer_vocab,matched_copy_exact_by_reference_token_length=lengths,limits='Loss coefficients are not loss-value or gradient contribution shares. Token-length results are confounded with task/value type; do not infer tokenization causality. Counts are exposures, not all unique data.',training_updates=0))
print(json.dumps(read(R/'inventory.json'),indent=2))
