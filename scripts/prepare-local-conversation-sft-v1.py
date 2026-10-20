"""Admit a finite narrower private research slice and reconstruct every SFT target."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
import numpy as np
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.data.tokenized import Writer,INDEX,document_tokens,ShardBatches
from slm.data.conversation_research import SOURCES,read_release,ConversationBatches
ROOT=Path('data/local-conversation-sft-v1');REVIEW=Path('data/conversation-review-v2');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 report=json.loads((REVIEW/'report.json').read_text())
 if not report['passed'] or any(not report['strata'][s]['passed'] for s in SOURCES):raise ValueError('Unchanged review gate failed')
 rows=[json.loads(x) for x in (REVIEW/'candidates.jsonl').open()];judgments=[json.loads(x) for x in (REVIEW/'direct-judgments.jsonl').open()];blocked={r['split_group'] for r in judgments if r['judgment']!='consider'}
 eligible=[dict(**r,content_category='unreviewed') for r in rows if r['source'] in SOURCES and r['split_group'] not in blocked]
 # Exact group-disjoint deterministic heldouts within this narrower source slice.
 eligible.sort(key=lambda r:digest(['local-conversation-sft-split-v1',r['split_group']]))
 validation=eligible[:64];test=eligible[64:128];train=eligible[128:]
 if len(train)<1000 or len({r['split_group'] for r in eligible})!=len(eligible):raise ValueError('Finite independent source supply below first-stage floor')
 ROOT.mkdir()
 for name,rr in [('train',train),('validation',validation),('test',test)]:
  with (ROOT/(name+'.jsonl')).open('x') as f:
   for r in rr:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 paths=[REVIEW/'candidates.jsonl',REVIEW/'sample.jsonl',REVIEW/'direct-judgments.jsonl',REVIEW/'report.json',Path('data/conversation-review-v1/direct-judgments.jsonl'),Path('data/conversation-groups-v1/report.json'),Path('data/conversation-screen-v1/report.json'),Path('data/smol-smoltalk-audit-v1/provenance.json'),Path('data/smol-smoltalk-audit-v1/source/source.json'),Path('data/smol-smoltalk-audit-v1/source/license.txt'),Path('data/smol-smoltalk-audit-v1/upstream-card.txt'),Path('data/smol-smoltalk-audit-v1/generator-license.txt'),Path('src/slm/data/conversation_scope.py'),Path('src/slm/data/conversation_research.py'),Path(__file__),TOK/'manifest.json',ROOT/'validation.jsonl',ROOT/'test.jsonl',Path('configs/main-learning-budget-authorization-v2.json'),Path('configs/conversation-recovery-target-v1.json'),Path('configs/english-owner-cloud-hold-v1.json')]
 policy=dict(creator='Navneet Prabhakar',kind='private-local-conversation-research-v1',authorized_by='Navneet Prabhakar',authorization_source='Direct owner instruction to continue local conversation training toward70–75%correctness; no GCP. Delegated expert corpus decision for this new isolated stage; no owner human attestation fabricated.',training_approved=True,human_attestation=False,content_category='unreviewed',cloud_allowed=False,allowed_constituents=sorted(SOURCES),max_physical_passes=2,maximum_new_sft_positions=20000000,maximum_context=768,source_revision='f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc',source_evidence_decision='Only three new synthetic upstream subsets with retained Apache2.0 source-card/license evidence are accepted for this bounded private local research. Mixed existing-source and failed magpie strata are excluded. Retained generator-origin/terms require a separate decision before any model distribution or service; this is not legal clearance or automatic agreement acceptance.',risk_acceptance='Most retained rows remain unread. Passing purposive sample gates and heuristic filters do not certify individual factuality, privacy, semantic family separation or SFW. This first stage mainly contains single-turn instruction/grounded transformation targets and cannot by itself certify broad multi-turn competence.',prohibited_uses=['production','public_model_or_dataset_distribution','cloud_execution','teacher_automatic_admission','sfw_certification','claims_unread_rows_individually_approved'],train_rows=len(train),train_sha256=sha(ROOT/'train.jsonl'),validation_rows=64,test_rows=64,removed_failed_stratum='smol-magpie-ultra-short',input_bindings={str(p):sha(p) for p in paths})
 save(ROOT/'admission.json',policy);checked,_=read_release(ROOT,sha(ROOT/'admission.json'));bpe=BPE.load(TOK);tokens=ROOT/'tokens';tokens.mkdir();writer=Writer(tokens,262144,2000000);lineage=[]
 for r in checked:
  result,reason=document_tokens(bpe,r,'sft',768)
  if reason:raise ValueError('No filtering/truncation during admitted preparation: '+reason)
  ids,mask=result;writer.add(ids[:-1],ids[1:],mask[1:]);lineage.append(dict(example_id='smol:'+str(r['row_index']),record_sha256=digest(r),content_sha256=digest(r['messages']),source=r['source'],source_revision=policy['source_revision'],parent_group_id=r['split_group'],split_group=r['split_group'],split='train',prediction_positions=len(ids)-1,supervised_positions=sum(mask[1:])))
 writer.flush();writer.close()
 with (tokens/'lineage.jsonl').open('x') as f:
  for r in lineage:f.write(json.dumps(r,sort_keys=True)+'\n')
 save(tokens/'report.json',dict(creator='Navneet Prabhakar',objective='sft',retained_records=len(checked),processed_prediction_positions=writer.processed,supervised_positions=writer.supervised,admission_sha256=sha(ROOT/'admission.json'),truncation=False,whole_dialogues=True))
 save(tokens/'manifest.json',dict(version=1,kind='portable-token-shards-v1',split='train',batch_size=1,objective='sft',message_format='plain-dialogue-v1',context_length=768,vocab_size=bpe.vocab_size,tokenizer_hash=sha(TOK/'manifest.json'),batches=writer.batches,processed_tokens=writer.processed,supervised_tokens=writer.supervised,index_dtype=INDEX.descr,shards=writer.shards,lineage_schema='record-content-spans-v2',allowed_categories=['unreviewed'],allowed_sources=sorted(SOURCES),private_conversation_admission_sha256=sha(ROOT/'admission.json'),files={str(p.relative_to(tokens)):sha(p) for p in tokens.rglob('*') if p.is_file()}))
 with ShardBatches(tokens,TOK) as batches:
  for i,r in enumerate(checked):
   (ids,mask),reason=document_tokens(bpe,r,'sft',768);actual=batches[i]
   expected=(np.array([ids[:-1]]),np.array([ids[1:]]),np.array([mask[1:]]))
   if reason or any(not np.array_equal(a,b) for a,b in zip(actual,expected)):raise ValueError('Full numeric source/role/assistant-mask reconstruction failed')
 schedule=[sorted(range(len(train)),key=lambda i:digest(['local-conversation-sft-order-v1',p,train[i]['split_group']])) for p in range(2)]
 save(ROOT/'schedule.json',dict(creator='Navneet Prabhakar',admission_sha256=sha(ROOT/'admission.json'),token_manifest_sha256=sha(tokens/'manifest.json'),schedule=schedule,physical_positions=writer.processed*2,supervised_positions=writer.supervised*2,passes=2,implicit_wraparound=False))
 with ConversationBatches(ROOT,TOK,sha(ROOT/'schedule.json')) as batches:
  assert batches.counts(len(batches))==(writer.processed*2,writer.supervised*2)
 save(ROOT/'preparation.json',dict(creator='Navneet Prabhakar',complete=True,train_rows=len(train),validation_rows=64,test_rows=64,by_source=dict(collections.Counter(r['source'] for r in train)),one_pass_positions=writer.processed,one_pass_supervised=writer.supervised,two_pass_physical_positions=writer.processed*2,two_pass_updates=(len(train)*2+7)//8,all_numeric_batches_reconstructed=len(train),admission_sha256=sha(ROOT/'admission.json'),schedule_sha256=sha(ROOT/'schedule.json'),no_new_gradients=True))
 print((ROOT/'preparation.json').read_text())
if __name__=='__main__':main()
