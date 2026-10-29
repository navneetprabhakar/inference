import json,hashlib
from pathlib import Path
from sentencepiece import SentencePieceProcessor
P=Path(__file__).resolve().parent;R=P.parents[2]
sp=SentencePieceProcessor(model_file=str(R/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
g=json.loads((P/'grounded_choices.json').read_text());grammar=json.loads((P/'grammar_contrasts.json').read_text());n=0
for x in g+grammar:
 groups=[x['joint_encoding']]
 if 'controls' in x:groups += [v for k,v in x['controls'].items() if k.endswith('joint_encoding')]
 for z in groups:
  assert z['prefix_ids'][0]==sp.bos_id();assert z['suffix_start']==len(z['prefix_ids'])
  for ids in z['full_ids']:
   assert ids[:z['suffix_start']]==z['prefix_ids'];assert len(ids)>z['suffix_start'];assert len(ids)<=256
   # A teacher-forced logit at index t predicts token t+1. The first suffix target is boundary b, hence logit b-1.
   b=z['suffix_start'];indices=list(range(b-1,len(ids)-1));assert len(indices)==len(ids)-b
   fake=[-float(i+1) for i in range(len(ids)-1)]
   assert sum(fake[k] for k in indices)==sum(fake[b-1:])
   n+=1
v=json.loads((P/'author_validation.json').read_text());old=json.loads((P/'author_validation_v1.json').read_text())
r={'status':'SINGLE_REPAIR_COMPLETE_NOT_ADMITTED','revision_batches_used':1,'original_payload_hashes':old['hashes'],'repaired_payload_hashes':v['hashes'],'changes':['BOS prepended to joint prefix and full sequences, boundaries reverified','Fixed prospective sum suffix log-probability rule, consistent with historical sum; includes punctuation, excludes BOS/prefix and does not append EOS','Rewrote procedural/explanatory/narrative passages in actual declared registers; retained30 event clusters/120questions','Instructions requiring full sentences now have full sentence references'],'joint_candidate_sequences_verified':n,'synthetic_suffix_index_checks':'PASS; not model inference or runner integration test','development_function_labels_in_prompts':False,'context_max':v['max_worst_history_tokens'],'admitted':False,'independent_full_benchmark_review_complete':False,'campaign_status':'STOP_DATA_ADMISSION reported by parent; no second repair authorized'}
(P/'repair_v2.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
