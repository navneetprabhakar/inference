"""Natural-dialogue-led recovery trial from preserved v3, not template-heavy v7."""
import hashlib,json,random,re
from collections import Counter
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT,encode_episode

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return re.sub(r'\W+',' ',s.casefold()).strip()
def main():
 out=ROOT/'data/eight-hour-improvement-v8-r3';run=ROOT/'runs/eight-hour-improvement-v8'
 out.mkdir(parents=True,exist_ok=True);run.mkdir(parents=True,exist_ok=True)
 if (out/'manifest.json').exists():raise RuntimeError('Already frozen')
 prior=ROOT/'data/author-review-v2/reviewed-candidate.jsonl';smol=ROOT/'data/sft-v3/train.jsonl';v6=ROOT/'data/eight-hour-improvement-v6/records.jsonl';ground=ROOT/'data/eight-hour-grounded-v1/batch-001.jsonl'
 load=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x]
 protected=set()
 for split in ['development','confirmation']:
  for c in load(ROOT/f'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2/{split}.jsonl'):
   protected.update(norm(t['user']) for t in c['turns'])
 groups={'reviewed_natural':[{'id':'v8-'+x['id'],'messages':x['messages'],'provenance':x['source']} for x in load(prior)],'short_upstream':[{'id':'v8-'+x['id'],'messages':x['episode'],'provenance':{'source':'pinned smol-smoltalk existing train split','upstream_source':x['upstream_source'],'review':'structural filtering and sampled assistant inspection, not exhaustive semantic review'}} for x in load(smol) if x['kind']=='chat' and x.get('upstream_source')=='smol-magpie-ultra-short'],'fresh_authored':[x for x in load(v6) if x['training_group']=='fresh_authored'],'positive_tools':[x for x in load(v6) if x['training_group']=='fixture_grounding'],'tool_boundaries':[x for x in load(ground) if x['family'] in ['missing_tool_argument','unavailable_calendar','division_error']]}
 tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));rows=[];ids=[];masks=[];lengths=[];targets=[];indices={k:[] for k in groups};seen=set();excluded=Counter()
 for group,records in groups.items():
  for r in records:
   messages=r['messages']
   if group=='short_upstream':
    opening=next(m['content'] for m in messages if m['role']=='user')
    if re.search(r'you are (?:an? |the |[0-9])|role.?play|role of|pretend|act as|imagine you',opening,re.I):excluded['upstream_roleplay']+=1;continue
    if any(len(m['content'].split())>90 for m in messages if m['role']=='assistant'):excluded['upstream_long_answer']+=1;continue
    if re.search(r'latest|most recent|current (?:version|president|price)',opening,re.I):excluded['upstream_time_sensitive']+=1;continue
    if re.search(r'what programming languages do you support|your (?:capabilities|abilities)',opening,re.I):excluded['upstream_capability_claim']+=1;continue
   fingerprint=json.dumps(messages,sort_keys=True,ensure_ascii=False)
   if fingerprint in seen:excluded['duplicate']+=1;continue
   if any(norm(m['content']) in protected for m in messages if m['role']=='user'):excluded['protected_exact_turn']+=1;continue
   e=encode_episode(tok,messages)
   if e is None:excluded['context_overflow']+=1;continue
   token,mask,n=e
   if not any(m['role']=='user' for m in messages):excluded['no_user']+=1;continue
   seen.add(fingerprint);indices[group].append(len(rows));rows.append({**r,'training_group':group});ids.append(token);masks.append(mask);lengths.append(n);targets.append(int(mask.sum()))
 shares={'reviewed_natural':.60,'short_upstream':.20,'fresh_authored':.10,'positive_tools':.05,'tool_boundaries':.05};rng=random.Random(2026110309);bags={};emitted={k:0 for k in groups};counts={k:0 for k in groups};order=[];inputs=0
 assert all(indices.values()),{k:len(v) for k,v in indices.items()}
 while inputs<4000000:
  k=min(groups,key=lambda k:emitted[k]/shares[k])
  if not bags.get(k):bags[k]=indices[k].copy();rng.shuffle(bags[k])
  i=bags[k].pop();order.append(i);inputs+=lengths[i]-1;emitted[k]+=targets[i];counts[k]+=1
 (out/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));np.savez_compressed(out/'episodes.npz',ids=np.stack(ids),mask=np.stack(masks),length=np.array(lengths,np.int32));(out/'order.json').write_text(json.dumps({'order':order,'seed':2026110309}))
 manifest={'records':len(rows),'group_records':{k:len(v) for k,v in indices.items()},'excluded':dict(excluded),'schedule_input_tokens':inputs,'scheduled_supervised_tokens':emitted,'scheduled_rows':counts,'desired_supervised_token_mix':shares,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [prior,smol,v6,ground]},'files':{n:sha(out/n) for n in ['records.jsonl','episodes.npz','order.json']},'limitation':'No new natural authoring claimed. Previously assistant-reviewed local corpus plus pinned upstream short dialogues, filtered for context/exact held-out prompts. Upstream semantics sampled, not fully reviewed. Template supplements restricted to10% assistant tokens.'}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 cfg={'run_dir':str(run.relative_to(ROOT)),'base_checkpoint':'runs/eight-hour-improvement-v3/training/checkpoint-000000100031-1793645323851575000','data_dir':str(out.relative_to(ROOT)),'deadline_unix':1793672065,'max_nonpadding_input_tokens':1000000,'max_active_seconds':14400,'learning_rate':3e-6,'batch_size':2,'checkpoint_every_steps':1000,'min_free_disk_bytes':15*2**30,'max_mlx_allocator_bytes':12*2**30,'seed':2026110309,'initial_stage_cap':1000000,'potential_continuation_cap':4000000}
 (run/'training-config.json').write_text(json.dumps(cfg,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
