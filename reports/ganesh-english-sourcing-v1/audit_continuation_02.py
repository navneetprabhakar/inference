"""Bounded local audit of b08–b12. No cloud, frozen-release reads or training."""
import collections,hashlib,importlib.util,json,sys,unicodedata
from pathlib import Path
R=Path(__file__).resolve().parent;ROOT=R.parents[1];OUT=ROOT/'runs/ganesh-english-sourcing-v1'
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
payload=(OUT/'reviewed-candidates.jsonl').read_bytes();raw=payload.splitlines();rows=[json.loads(x) for x in raw]
base=json.loads((R/'continuation-02-baseline.json').read_text())
if [hashlib.sha256(x).hexdigest() for x in raw[:base['sessions']]]!=base['row_hashes']:raise ValueError('Prior134 rows changed')
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'));bygroup={r['group']:r for r in rows}
reviews=[];lengths=collections.Counter();family_lengths=collections.defaultdict(collections.Counter);probes=[];newgroups=[]
for batch in ('b08','b09','b10','b11','b12'):
 batchreviews=json.loads((R/f'authored-review-{batch}.json').read_text());reviews.extend(batchreviews)
 for review in batchreviews:
  row=bygroup[review['group']];n=len(row['messages'])//2;lengths[n]+=1;family_lengths[row['family']][n]+=1;newgroups.append(row['group'])
  if 'recall_probe' not in review:continue
  p=review['recall_probe'];support=p['last_supporting_turn'];probe=p['probe_turn']
  for enabled in (False,True):
   policy={'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}
   supported=encode_conversation(tok,row['messages'][:support*2],policies=[policy]*support,context=2048)
   intervening=encode_conversation(tok,row['messages'][:(probe-1)*2],policies=[policy]*(probe-1),context=2048)
   prompt=encode_conversation(tok,row['messages'][:probe*2-1],policies=[policy]*probe,for_generation=True,context=2048,reply_budget=256)
   probes.append(dict(group=row['group'],tools_enabled=enabled,focus=p['probe_focus'],last_supporting_turn=support,probe_turn=probe,intervening_complete_turns=p['intervening_complete_turns'],intervening_serialized_tokens=len(intervening['ids'])-len(supported['ids']),probe_prompt_tokens=len(prompt['ids']),target_positions_after_support_before_probe=sum(intervening['mask'][len(supported['ids']):])))
answers=[' '.join(unicodedata.normalize('NFKC',m['content']).casefold().split()) for r in rows for m in r['messages'] if m['role']=='assistant']
c=collections.Counter(answers);family=json.loads((R/'overlap-check.json').read_text())['family_target_positions']
lag=collections.Counter(p['intervening_complete_turns'] for p in probes if not p['tools_enabled'])
bins=collections.Counter('1536–1792' if p['probe_prompt_tokens']>=1536 else '1024–1535' if p['probe_prompt_tokens']>=1024 else '512–1023' if p['probe_prompt_tokens']>=512 else 'under512' for p in probes if p['tools_enabled'])
report={'status':'candidate_consistency_pass_not_admission','previous_134_rows_byte_identical':True,'new_batches':5,'new_scenarios':len(reviews),'new_assistant_turns_reviewed':sum(r['assistant_turns_reviewed'] for r in reviews),'new_scenario_turn_counts':dict(lengths),'family_turn_counts':{f:dict(c) for f,c in family_lengths.items()},'annotated_memory_probes':len(probes)//2,'intervening_turn_histogram':dict(lag),'enabled_probe_prompt_bins':dict(bins),'memory_probe_measurements':probes,'candidate_sessions':len(rows),'assistant_turns':len(answers),'unique_normalized_assistant_texts':len(c),'repeated_text_excess':sum(n-1 for n in c.values()),'family_target_positions':family,'correction_memory_target_fraction':(family['correction']+family['memory'])/sum(family.values()),'payload_sha256':hashlib.sha256(payload).hexdigest(),'input_hashes':{name:hashlib.sha256((R/name).read_bytes()).hexdigest() for name in ['review_notes_02.json','candidate-validation.json','overlap-check.json']+[f'{prefix}{batch}{suffix}' for batch in ('b08','b09','b10','b11','b12') for prefix,suffix in [('authored_source_','.py'),('authored-review-','.json'),('authoring-plan-','.json')]]},'independent_review':False,'training_admitted':False,'cloud_operations':False,'limitations':['Same-author semantic review, not independent review or current-model evaluation','Probe focus can be a constraint within a composite answer, not necessarily an entire answer recalled from one turn','Repeated contextual cues lower difficulty; annotated gap is not evidence of an isolated memory benchmark','Serialized gaps include policy/control tokens, not just natural-language distractor text','Turn count varies but correction/memory families still correlate with dialogue length','No 3K/4K claim; native2K plus reply reserve only','Broader source/template separation, independent review and held-out curriculum design remain pending']}
(R/'continuation-02-audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('memory_probe_measurements','input_hashes')},indent=2,ensure_ascii=False))
