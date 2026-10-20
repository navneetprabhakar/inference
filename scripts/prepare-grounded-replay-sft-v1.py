"""Admit reviewed private three-turn QA and explicitly reallocate untouched replay."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
import numpy as np
from slm.common.tokenizer import BPE
from slm.data.tokenized import Writer,INDEX,document_tokens,ShardBatches
from slm.data.english_corpus import build_tokens,verify_tokens
from slm.data.grounded_conversation_research import read_release,GroundedBatches
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-replay-sft-v1');PREP=Path('data/grounded-conversations-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384');REPLAY=Path('data/english-balanced-preliminary-v2/remaining-retention.jsonl')
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 review=json.loads((PREP/'review-report.json').read_text());prep=json.loads((PREP/'preparation.json').read_text())
 if not review['passed'] or review['fully_read']!=64 or review['nonapproval_fraction']>.25:raise ValueError('Unchanged full64 review gate required')
 judgments=[json.loads(l) for l in (PREP/'direct-judgments.jsonl').open()];blocked={r['split_group'] for r in judgments if r['judgment']!='consider'}
 rows=[r for l in (PREP/'candidates.jsonl').open() for r in [json.loads(l)] if r['split_group'] not in blocked]
 rows.sort(key=lambda r:digest(['grounded-train-selection-v1',r['id']]))
 if len(rows)<4096:raise ValueError('Insufficient admitted unique paragraph supply')
 train=rows[:4096];c=json.loads(Path('configs/future-intake-evaluation-exclusions-v4.json').read_text());ex=EvaluationExclusions(c['inventory'],c['inventory_sha256']);remaining=[json.loads(l) for l in REPLAY.open()];replay=[]
 for source in ('general','narrative'):
  pool=sorted([r for r in remaining if r['source']==source],key=lambda r:digest(['grounded-replay-reallocation-v1',r['split_group']]))
  selected=[r for r in pool if not ex.guard.matches(r['text'])][:64]
  if len(selected)!=64:raise ValueError('Insufficient untouched protected-safe replay')
  replay+=selected
 replay.sort(key=lambda r:digest(['grounded-replay-order-v1',r['split_group']]))
 ROOT.mkdir()
 for name,rr in [('train',train),('replay',replay),('remaining-retention',[r for r in remaining if r['split_group'] not in {v['split_group'] for v in replay}])]:
  with (ROOT/(name+'.jsonl')).open('x') as f:
   for r in rr:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 paths=[PREP/'preparation.json',PREP/'sample.jsonl',PREP/'direct-judgments.jsonl',PREP/'review-report.json',PREP/'development-100.json',PREP/'reserved-100.json',PREP/'development-references.jsonl',PREP/'reserved-references.jsonl',REPLAY,Path('data/english-balanced-preliminary-v2/policy.json'),Path('data/english-recovery-corpus-v1/admission.json'),Path(c['inventory']),Path('configs/future-intake-evaluation-exclusions-v4.json'),Path('configs/conversation-recovery-target-v1.json'),Path('configs/english-owner-cloud-hold-v1.json'),Path(__file__),Path('src/slm/data/grounded_conversation_research.py')]
 policy=dict(creator='Navneet Prabhakar',kind='private-local-grounded-conversation-v1',authorized_by='Navneet Prabhakar',authorization='Owner requires continued local conversation training toward70–75%correctness; delegated expert source decision, no fabricated human attestation.',training_approved=True,human_attestation=False,content_category='unreviewed',cloud_allowed=False,max_physical_passes=2,maximum_remaining_sft_positions=19729641,train_rows=len(train),train_sha256=sha(ROOT/'train.jsonl'),replay_rows=len(replay),replay_sha256=sha(ROOT/'replay.jsonl'),untouched_retention_source=str(REPLAY),preparation_root=str(PREP),source_revision='eee5fdbf62f8613a7812b03419e6b29617b74fd1',source_evidence='Public SQuAD1.1 original human questions/answer spans; retained pinned source page states CC-BY-SA4.0 for data, separate Apache2code license. Explicit private local research decision only; no public/model distribution or service clearance, no agreement acceptance.',review_gate='64 complete distinct train-article dialogues directly read; all observed negative article components withheld. Most retained paragraphs unread; categoryunreviewed, no SFW certification or factual certification.',objective='One whole three-turn conversation per paragraph; assistant-only targets on all three original human spans. No fabricated answers, repeated paragraph question variants or benchmark training. Lower LR and original-language replay are hypotheses, not capability guarantees.',replay_reallocation='128 whole untouched retention families,64general+64narrative, at most2physicalpasses. Removed only in new sidecar; original pool/failed runs/checkpoints remain immutable. All joint QA/replay gradient positions charged against remaining conditionalSFT20M cap.',original_retention_families=len(remaining),remaining_retention_families=len(remaining)-len(replay),inputs={str(p):sha(p) for p in paths})
 # Source license evidence remains independently pinned by the successful intake.
 intake=json.loads(Path('data/grounded-qa-intake-v1/report-v2.json').read_text())
 for e in intake['evidence'].values():policy['inputs'][e['path']]=e['sha256']
 save(ROOT/'admission.json',policy);checked,replay,policy=read_release(ROOT,sha(ROOT/'admission.json'));bpe=BPE.load(TOK);tokens=ROOT/'qa-tokens';tokens.mkdir();writer=Writer(tokens,262144,10000000);lineage=[]
 for r in checked:
  result,reason=document_tokens(bpe,r,'sft',768)
  if reason:raise ValueError('No filtering/truncation after admission: '+reason)
  ids,mask=result;writer.add(ids[:-1],ids[1:],mask[1:]);lineage.append(dict(example_id=r['id'],source=r['source'],source_revision=r['source_revision'],split_group=r['split_group'],paragraph_component=r['paragraph_component'],record_sha256=digest(r),prediction_positions=len(ids)-1,supervised_positions=sum(mask[1:]),three_turn_whole_dialogue=True))
 writer.flush();writer.close()
 with (tokens/'lineage.jsonl').open('x') as f:
  for r in lineage:f.write(json.dumps(r,sort_keys=True)+'\n')
 save(tokens/'report.json',dict(creator='Navneet Prabhakar',objective='sft',retained_records=len(checked),processed_prediction_positions=writer.processed,supervised_positions=writer.supervised,admission_sha256=sha(ROOT/'admission.json'),truncation=False,whole_dialogues=True))
 save(tokens/'manifest.json',dict(version=1,kind='portable-token-shards-v1',split='train',batch_size=1,objective='sft',message_format='plain-dialogue-v1',context_length=768,vocab_size=bpe.vocab_size,tokenizer_hash=sha(TOK/'manifest.json'),batches=writer.batches,processed_tokens=writer.processed,supervised_tokens=writer.supervised,index_dtype=INDEX.descr,shards=writer.shards,lineage_schema='record-content-spans-v2',allowed_categories=['unreviewed'],allowed_sources=['SQuAD-1.1'],files={str(p.relative_to(tokens)):sha(p) for p in tokens.rglob('*') if p.is_file()}))
 with ShardBatches(tokens,TOK) as batches:
  for i,r in enumerate(checked):
   (ids,mask),reason=document_tokens(bpe,r,'sft',768);expected=(np.array([ids[:-1]]),np.array([ids[1:]]),np.array([mask[1:]]))
   if reason or any(not np.array_equal(a,b) for a,b in zip(batches[i],expected)):raise ValueError('Complete QA numeric reconstruction differs')
 replayreport=build_tokens(replay,bpe,ROOT/'replay-tokens',sha('data/english-recovery-corpus-v1/manifest.json'),sha(TOK/'manifest.json'),sha(ROOT/'admission.json'))
 verified=verify_tokens(replay,bpe,ROOT/'replay-tokens',TOK)
 with ShardBatches(ROOT/'replay-tokens',TOK) as replaybatches:replayn=len(replaybatches)
 schedule=[]
 for epoch in range(2):
  qaorder=sorted(range(len(train)),key=lambda i:digest(['grounded-finite-order-v1',epoch,train[i]['id']]))
  # Interleave complete finite batch supplies, preserving every original replay batch.
  addresses=[(i/len(qaorder),0,index) for i,index in enumerate(qaorder)]+[(i/replayn,1,i) for i in range(replayn)]
  schedule += [[source,index] for _,source,index in sorted(addresses)]
 total=2*(writer.processed+verified);supervised=2*(writer.supervised+verified)
 save(ROOT/'schedule.json',dict(creator='Navneet Prabhakar',admission_sha256=sha(ROOT/'admission.json'),token_manifests={name:sha(ROOT/name/'manifest.json') for name in ('qa-tokens','replay-tokens')},schedule=schedule,physical_positions=total,supervised_positions=supervised,passes=2,implicit_wraparound=False,qa_batches_per_pass=len(train),replay_batches_per_pass=replayn))
 with GroundedBatches(ROOT,TOK,sha(ROOT/'schedule.json')) as batches:
  if batches.counts(len(batches))!=(total,supervised):raise ValueError('Joint accounting differs')
 save(ROOT/'preparation.json',dict(creator='Navneet Prabhakar',complete=True,train_dialogues=len(train),train_article_components=len({r['split_group'] for r in train}),assistant_turns_per_pass=3*len(train),replay_families=len(replay),remaining_retention_families=len(remaining)-len(replay),qa_positions_per_pass=writer.processed,qa_supervised_per_pass=writer.supervised,replay_positions_per_pass=verified,two_pass_physical_positions=total,two_pass_supervised=supervised,total_batches=len(schedule),accumulation16_updates=(len(schedule)+15)//16,all_qa_numeric_batches_reconstructed=len(train),all_replay_nexttoken_pairs_reconstructed=verified,admission_sha256=sha(ROOT/'admission.json'),schedule_sha256=sha(ROOT/'schedule.json'),no_new_gradients=True))
 print((ROOT/'preparation.json').read_text())
if __name__=='__main__':main()
