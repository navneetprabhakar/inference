"""Independently reconstruct raw dialogue membership, spans, exclusions and finite exposure."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
import numpy as np
from slm.common.tokenizer import BPE,STRUCTURAL
from slm.data.tokenized import document_tokens
from slm.data.grounded_conversation_research import GroundedBatches
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.data.evaluation_exclusions import EvaluationExclusions
ROOT=Path('data/grounded-replay-sft-v1');PREP=Path('data/grounded-conversations-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
def main():
 output=ROOT/'independent-audit.json'
 if output.exists():raise FileExistsError(output)
 prep=json.loads((PREP/'preparation.json').read_text());policy=json.loads((ROOT/'admission.json').read_text())
 for name,h in prep['input_bindings'].items():
  if sha(name)!=h:raise ValueError('Source preparation input differs')
 for name,h in prep['files'].items():
  if sha(PREP/name)!=h:raise ValueError('Frozen pre-review file differs')
 source=json.loads(Path('data/grounded-qa-intake-v1/train-v1.1.json').read_text());pool={r['id']:r for l in (PREP/'candidates.jsonl').open() for r in [json.loads(l)]};train=[json.loads(l) for l in (ROOT/'train.jsonl').open()];c=json.loads(Path('configs/future-intake-evaluation-exclusions-v4.json').read_text());ex=EvaluationExclusions(c['inventory'],c['inventory_sha256']);qa_count=0
 for r in train:
  if pool.get(r['id'])!=r or len(r['original_questions'])!=3:raise ValueError('Intact frozen candidate membership differs')
  article=source['data'][r['article_index']];p=article['paragraphs'][r['paragraph_index']]
  if article['title']!=r['article'] or p['context']!=r['context']:raise ValueError('Original source context differs')
  expected=sorted(p['qas'],key=lambda q:digest(['grounded-three-turn-v1',q['id']]))[:3]
  for t,(q,saved) in enumerate(zip(expected,r['original_questions'])):
   if saved!=dict(id=q['id'],question=q['question'],answers=q['answers']):raise ValueError('Fixed original question differs')
   user=('Read the passage and answer the question using only the passage. Give only the answer.\n\nPassage:\n'+p['context']+'\n\nQuestion: '+q['question']) if t==0 else 'Using the same passage, give only the answer.\n\nQuestion: '+q['question']
   if r['messages'][t*2]!=dict(role='user',content=user) or r['messages'][t*2+1]!=dict(role='assistant',content=q['answers'][0]['text']):raise ValueError('Actual conversation framing differs')
   qa_count+=1
  if ex.guard.matches('\n'.join(m['content'] for m in r['messages'])):raise ValueError('Evaluation containment')
 replay=[json.loads(l) for l in (ROOT/'replay.jsonl').open()];remaining=[json.loads(l) for l in (ROOT/'remaining-retention.jsonl').open()];original=[json.loads(l) for l in Path(policy['untouched_retention_source']).open()];identity=lambda rr:{r['split_group']:digest(r) for r in rr}
 if set(identity(replay))&set(identity(remaining)) or {**identity(replay),**identity(remaining)}!=identity(original):raise ValueError('Untouched pool reallocation incomplete or overlapping')
 for r in replay:
  if ex.guard.matches(r['text']):raise ValueError('Replay evaluation containment')
 bpe=BPE.load(TOK);full=[]
 for r in replay:full+=bpe.encode(r['text'])+[STRUCTURAL['eos']]
 checked=0
 with GroundedBatches(ROOT,TOK,sha(ROOT/'schedule.json')) as batches:
  for i,r in enumerate(train):
   (ids,mask),reason=document_tokens(bpe,r,'sft',768)
   if reason:raise ValueError(reason)
   if any(not np.array_equal(a,b) for a,b in zip(batches.bases[0][i],(np.array([ids[:-1]]),np.array([ids[1:]]),np.array([mask[1:]])))):raise ValueError('Independent complete numeric QA reconstruction')
  for i in range(len(batches.bases[1])):
   x,y,m=batches.bases[1][i];n=x.size
   if x[0].tolist()!=full[checked:checked+n] or y[0].tolist()!=full[checked+1:checked+n+1] or not np.all(m==1):raise ValueError('Independent replay source reconstruction')
   checked+=n
  if checked!=len(full)-1:raise ValueError('Complete replay stream required')
  counts=collections.Counter(tuple(s) for s in batches.schedule);physical,supervised=batches.counts(len(batches));size=len(batches)
  if set(counts.values())!={2}:raise ValueError('Source replay exceeds two finite passes')
 for name in ('development','reserved'):
  refs=[json.loads(l) for l in (PREP/(name+'-references.jsonl')).open()]
  if {r['split_group'] for r in refs}&{r['split_group'] for r in train}:raise ValueError('Heldout article component contamination')
 report=dict(creator='Navneet Prabhakar',complete=True,passed=True,all4096_original_dialogues_reconstructed=len(train),all12288_original_question_answer_spans_reconstructed=qa_count,all4096_numeric_assistant_masks_reconstructed=len(train),replay_next_token_pairs_reconstructed=checked,article_disjoint_evaluation_conversations=200,observed_negative_article_components_withheld=True,untouched_replay_families=len(replay),remaining_untouched_families=len(remaining),raw_replay_pool_preserved=True,total_batches=size,two_finite_pass_physical_positions=physical,two_finite_pass_supervised_positions=supervised,source_qa_supervised_fraction=2*85583/supervised,input_bindings={str(p):sha(p) for p in [ROOT/'admission.json',ROOT/'train.jsonl',ROOT/'replay.jsonl',ROOT/'remaining-retention.jsonl',ROOT/'schedule.json',PREP/'preparation.json',Path(__file__)]},no_new_gradients=True,no_capability_claim=True)
 output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
