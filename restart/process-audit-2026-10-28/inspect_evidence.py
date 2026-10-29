"""CPU-only independent data/serialization/accounting audit. No student model import."""
from pathlib import Path
import json,re,hashlib,collections,math
import numpy as np
from sentencepiece import SentencePieceProcessor
ROOT=Path(__file__).resolve().parent;P=ROOT.parents[1];C=P/'restart/conversation-improvement-v1';D=C/'private'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sp=SentencePieceProcessor(model_file=str(P/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
def encode(messages):
 ids=[sp.bos_id()];mask=[0]
 for i,m in enumerate(messages):
  part=sp.encode('User: '+m['content']+'\nAssistant:') if i%2==0 else sp.encode(m['content'])+[sp.eos_id()]
  ids.extend(part);mask.extend([i%2]*len(part))
 return ids,mask
out={'method':'CPU-only; reconstructs segmented serializer independently. No weights loaded, inference, gradients, updates, teacher calls or final-bank payload reads.','files':{},'banks':{}}
banks={}
for name in ['grounding','original-rehearsal','teacher','development','cycle12-training']:
 p=D/(name+'.json');a=read(p);banks[name]=a;out['files'][str(p.relative_to(P))]=sha(p)
 bad=[];lengths=[];targets=[];families={};prefix_mismatch=0
 for r in a:
  ids,m=encode(r['messages']);lengths.append(len(ids));targets.append(sum(m))
  if 'ids' in r and (ids!=r['ids'] or m!=r['mask']):bad.append(r['id'])
  for j in range(0,len(r['messages']),2):
   prefix,_=encode(r['messages'][:j+1]);assert ids[:len(prefix)]==prefix
  families.setdefault(r['family'],[]).append(r)
 out['banks'][name]=dict(records=len(a),families={f:dict(records=len(v),distinct_assistant_strings=len({m['content'] for r in v for m in r['messages'] if m['role']=='assistant'}),supervised_targets=sum(sum(encode(r['messages'])[1]) for r in v)) for f,v in families.items()},serialized_length_min=min(lengths),serialized_length_max=max(lengths),serialized_length_median=float(np.median(lengths)),supervised_target_occurrences=sum(targets),EOS_targets=sum(len(r['messages'])//2 for r in a),serialization_mismatches=bad,over_context=sum(n>256 for n in lengths))
 assert not bad
# Prompt templates: replace only exact answer and known item placeholder for name/time.
for name in ['grounding','cycle12-training']:
 out['banks'][name]['name_time_prompt_shapes']={}
 for f in ['name','time']:
  shapes=set()
  for r in banks[name]:
   if r['family']!=f:continue
   text=r['messages'][0]['content'];answer=r['messages'][1]['content'];text=text.replace(answer,'<VALUE>')
   text=re.sub(r'\b(lamp|coat|pen|box|hat|bag|bowl|key|cup|book)\b','<ITEM>',text)
   shapes.add(text)
  out['banks'][name]['name_time_prompt_shapes'][f]=sorted(shapes)
# Exact labels and components, not an invented semantic split.
for f in ['name','time']:
 train={r['messages'][1]['content'] for r in banks['grounding'] if r['family']==f}
 dev=[r for r in banks['development'] if r['family']==f]
 labels=[r['messages'][1]['content'] for r in dev]
 out.setdefault('development_shift',{})[f]=dict(train_labels=len(train),development_labels=len(set(labels)),development_exact_labels_seen=sum(x in train for x in labels),record_number_prefixes=sum(bool(re.search(r'entry \d+',r['messages'][0]['content'])) for r in dev),development_records=len(dev))
 if f=='name':out['development_shift'][f]['development_name_components_seen']=sum(w in {w for x in train for w in x.split()} for x in labels for w in x.split())
# Aggregate observed collapse toward numeric answers on nonnumeric requested tasks.
for cycle,step in [(10,1600),(12,400)]:
 p=D/f'cycle{cycle}-{step}-development-responses.json';a=read(p);dialogue=[r for r in a if r['family'] not in ['name','time','state']]
 out.setdefault('response_diagnostics',{})[f'cycle{cycle}-{step}']=dict(dialogue_turns=len(dialogue),time_shaped_prefixes=sum(bool(re.match(r'^\d{1,2}:',r['response'])) for r in dialogue),digit_bearing_first_dialogue_prompts=sum(bool(re.search(r'\d',r['user'])) for r in dialogue if r['turn']==0),complete_state_conversations=sum(all(x['strict'] for x in a if x['id']==rid) for rid in {x['id'] for x in a if x['family']=='state'}))
 out['files'][str(p.relative_to(P))]=sha(p)
# Prefix repetition in retention.
p=D/'retention.json';a=read(p);prompts=[r['messages'][0]['content'] for r in a];out['retention']=dict(conversations=len(a),turns=sum(len(r['messages'])//2 for r in a),unique_first_prompts=len(set(prompts)))
ledger=read(C/'ledger.json');counts={k:sum(r.get(k,0) for r in ledger['reservations']) for k in ['positions','updates','sft_targets','narrative_targets']};assert all(counts[k]==ledger[k] for k in counts);assert 'active_segment' not in ledger
out['accounting']=dict(counts,model_seconds=ledger['model_seconds'],prior_tracked_updates=614,lifetime_total_claimed=False,final_reservations=sum(e['phase']=='final' for e in ledger['reservations']))
out['architecture']=dict(parameters=15191712,tied_embedding_parameters=32000*288,embedding_share=32000*288/15191712,non_embedding_parameters=15191712-32000*288,context=256,adapter_parameters=262656)
out['preservation']=dict(original_nll=1.3430354408919811,limit=1.3430354408919811*1.05,implied_perplexity_increase=math.exp(1.3430354408919811*.05)-1)
# Finite replay inventory vs consumed exposures.
a=np.load(D/'replay.npy',mmap_mode='r');out['replay']=dict(shape=list(a.shape),positions_in_saved_bank=int(a.size),targets_in_saved_bank=int(np.prod(a.shape[:-1])*(a.shape[-1]-1)))
native=read(P/'restart/mac15m-feasibility-v1/data-receipt.json')
out['native_foundation_inventory']={k:native[k] for k in ['training','validation','split','corpus_position_caveat']}
out['native_foundation_inventory']['retained_foundation_target_exposures']=412221440
out['native_foundation_inventory']['exposure_to_inventory_ratio_not_unique_coverage']=412221440/native['training']['distinct_corpus_positions']
out['source_hashes']={q:sha(P/q) for q in ['restart/mac15m-feasibility-v1/data-receipt.json','restart/foundation-stage3-v1/engine_support.py','restart/conversation-improvement-v1/adapter9.py','restart/teacher-bridge-execution-v1/support.py','restart/sol-conversation-sft-diagnostic-v1/runner.py','restart/foundation-recovery-v2-corrected/D0/semantic-review.json']}
(ROOT/'evidence.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
