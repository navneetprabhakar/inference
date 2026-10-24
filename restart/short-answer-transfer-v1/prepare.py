"""Freeze matched curriculum/control batches and private fresh probes; no model operations."""
import hashlib,importlib.util,json,random
from collections import Counter
from pathlib import Path
import numpy as np
from sentencepiece import SentencePieceProcessor
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];PRIVATE=ROOT/'private'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 if (ROOT/'freeze.json').exists():raise RuntimeError('Do not refreeze')
 sp=SentencePieceProcessor(model_file=str(PROJECT/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
 core=read(PROJECT/'restart/conversation-memorization8-v1/examples.json')
 broad=read(PROJECT/'restart/sol-conversation-sft-diagnostic-v1/attempt-3/private/datasets.json')['train']
 assert len(core)==8 and len(broad)==62
 for r in core:r['stage']='short';r['family']=r['category']
 for r in broad:r['stage']='broader'
 training=core+broad
 spec=importlib.util.spec_from_file_location('sft_prepare_helper',PROJECT/'restart/sol-conversation-sft-diagnostic-v1/runner.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
 for row in training:
  ids,mask,spans=s.serialize(sp,row['messages']);assert len(ids)<=257
  row['ids']=ids.tolist();row['mask']=mask.tolist()
  for i,span in enumerate(spans):assert s.prompt(sp,row['messages'][:2*i+1])==list(ids[:span['start']])
 banks={name:read(PRIVATE/(name+'-cases.json')) for name in ['development','test']}
 def norm(t):return ' '.join(__import__('re').findall(r'\w+',t.lower()))
 trainprompts={norm(m['content']) for r in training for m in r['messages'] if m['role']=='user'}
 evalprompts={name:{norm(m['content']) for r in rows for m in r['messages'] if m['role']=='user'} for name,rows in banks.items()}
 assert not trainprompts&evalprompts['development'] and not trainprompts&evalprompts['test'] and not evalprompts['development']&evalprompts['test']
 for name,rows in banks.items():
  for r in rows:
   ids,mask,spans=s.serialize(sp,r['messages']);assert len(ids)<=257
   r['ids']=ids.tolist();r['mask']=mask.tolist()
   for i,span in enumerate(spans):assert s.prompt(sp,r['messages'][:2*i+1])==list(ids[:span['start']])
   # Two-turn free histories may contain a 24-token failed first answer; reserve for that too.
   if len(r['messages'])==4:assert len(s.prompt(sp,[r['messages'][0],dict(role='assistant',content='word '*24),r['messages'][2]]))+24<=256
 rng=random.Random(24102463);curriculum=[]
 for i in range(50):curriculum.append(list(range(8)))
 stream=[]
 while len(stream)<150*8:
  cycle=list(range(8,70));rng.shuffle(cycle);stream+=cycle
 for i in range(150):curriculum.append(stream[i*8:i*8+8])
 permutation=list(range(200));random.Random(24102464).shuffle(permutation);control=[curriculum[i] for i in permutation]
 assert Counter(i for b in curriculum for i in b)==Counter(i for b in control for i in b)
 save(PRIVATE/'training.json',training)
 for name,rows in banks.items():save(PRIVATE/(name+'-encoded.json'),rows)
 save(PRIVATE/'schedules.json',dict(curriculum=curriculum,shuffled_control=control))
 spec=importlib.util.spec_from_file_location('replay_support',PROJECT/'restart/foundation-stage3-v1/engine_support.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 replay=mod.Stream('train',skip_sequences=1610240);data=[];files=set()
 for i in range(200):
  data.append(replay.batch(8));files.add(str(replay.tokens.filename))
 replay_array=np.stack(data).astype(np.uint16);assert replay_array.shape==(200,8,257)
 np.save(PRIVATE/'replay.npy',replay_array)
 token_files=sorted((PROJECT/'restart/mac15m-feasibility-v1/upstream/data/TinyStories_all_data').glob('*.bin'))
 assert str(token_files[0]) not in files
 hashes={str(Path(f).relative_to(PROJECT)):sha(f) for f in sorted(files)}
 files_to_freeze=[PRIVATE/'training.json',PRIVATE/'schedules.json',PRIVATE/'development-encoded.json',PRIVATE/'test-encoded.json',PRIVATE/'replay.npy',ROOT/'prepare.py',ROOT/'run.py',PROJECT/'restart/sol-conversation-sft-diagnostic-v1/runner.py']
 save(ROOT/'freeze.json',dict(files={str(p.relative_to(PROJECT)):sha(p) for p in files_to_freeze},replay_source_files=hashes))
 save(ROOT/'data-receipt.json',dict(training_conversations=70,short_training_conversations=8,broader_training_conversations=62,broader_provenance='Existing directly reviewed GPT-6 Sol demonstrations; no new teacher calls',assistant_content_tokens=sum(len(sp.encode(m['content'])) for r in training for m in r['messages'] if m['role']=='assistant'),supervised_targets_unique=sum(int(sum(r['mask'])) for r in training),format='Existing segmented BOS/User:/Assistant:/assistant/EOS; assistant+EOS-only masking',development_conversations=12,development_turns=16,test_conversations=40,test_turns=48,counterfactual_test_pairs=16,probes='New self-authored synthetic prompts frozen before model execution; test is never used for checkpoint selection. Not a sealed independent benchmark.',quality='All training records were directly reviewed in preceding tests. All fresh probe templates, values and answers reviewed before execution; generated bank checked for role/prefix/context consistency.',exact_prompt_overlap_train_dev=0,exact_prompt_overlap_train_test=0,exact_prompt_overlap_dev_test=0,replay='Existing TinyStories native training split only, seed42 stream, skip1,610,240 sequences; no validation shard',replay_targets_per_arm=200*8*256,replay_same_order_between_arms=True,identical_sft_exposure_multisets_between_arms=True,source_hashes=hashes))
 print(json.dumps(read(ROOT/'data-receipt.json')),flush=True)
if __name__=='__main__':main()
