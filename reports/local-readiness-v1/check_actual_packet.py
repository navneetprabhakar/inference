"""Read-only real-tokenizer packing and restart audit; never runs a model or cloud VM."""
import collections,hashlib,json,sys,datetime
from pathlib import Path
sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_sft import JsonlConversations,FiniteEpochDataset,BestFitConversations,load_manifest,batch_recipe
from cloud_training.nano_corpus_guard import verify_freeze
P=Path('reports/corrective-corpus-v1');out=Path('reports/local-readiness-v1')
freeze=verify_freeze(P);contract=json.loads((P/'quality-contract.json').read_text())
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
m=load_manifest(P/'candidate-4k/manifest.json',contract['tokenizer_sha256'],4096)
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'freeze':freeze,'splits':{}}
for split in ['train','validation']:
 d=JsonlConversations(m[split]['_file'],tok,m[split]['sha256'],4096)
 source=[json.loads(l) for l in Path(m[split]['_file']).read_text().splitlines()]
 finite=FiniteEpochDataset(d,2,seed=103) if split=='train' else d
 pack=BestFitConversations(finite,buffer_size=1 if split=='train' else 100);seen=[];labels=0;restart_checks=0;families=collections.Counter();first_ten=collections.Counter();first_targets=0
 while True:
  state=json.loads(json.dumps(pack.state_dict()));other=BestFitConversations(finite,buffer_size=1 if split=='train' else 100);other.load_state_dict(state)
  try:indices=pack.next_indices()
  except StopIteration:break
  assert indices==other.next_indices();restart_checks+=1
  for index in indices:
   raw=finite.order[index] if split=='train' else index
   seen.append(index);families[source[raw]['family']]+=d.target_counts[raw]
   if split=='train' and pack.rows<=80:
    first_ten[source[raw]['family']]+=d.target_counts[raw];first_targets+=d.target_counts[raw]
  # Independently render the same restored row and verify shift/mask target count.
  other.load_state_dict(state);x,y=other.next_row()
  assert len(x)==len(y)==4096
  count=sum(v!=-1 for v in y)
  assert count==sum(finite.target_counts[i] for i in indices)
  labels+=count
 assert sorted(seen)==list(range(len(finite))) and labels==sum(finite.target_counts)
 report['splits'][split]={'sessions':len(d),'packed_rows':pack.rows,'assistant_targets':labels,'restart_boundaries_checked':restart_checks,'every_conversation_once_per_declared_epoch':True,'family_target_mass':dict(families),'first_10_updates_family_targets':dict(first_ten),'first_10_updates_targets':first_targets}
report['recipe']={**batch_recipe(32768,1,4096),'packing_buffer_size':1,'epochs':2,'seed':103,'max_updates':10,'lr_multiplier':0.125,'eval_rows':512,'eval_every_updates':5}
report['limitations']=['CPU packing/restart only; no CUDA optimizer equivalence or GPU memory proof.','Fresh 4K extension uses native RoPE; usable long-context behavior remains unproven.']
(out/'actual-packet-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
