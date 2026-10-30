"""Read-only independent checks before starting the frozen SFT experiment."""
import json,hashlib,collections
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import *
from train_sft import batch,MILESTONES
p=ROOT/'data/sft-v1';tok=Tokenizer.from_file(str(p/'tokenizer.json'));a=dict(np.load(p/'episodes.npz'));order=np.load(p/'order.npy');seen={};families={};counts={};encoded_targets=collections.Counter()
for split in ['train','dev','test']:
 rows=[json.loads(x) for x in (p/f'{split}.jsonl').read_text().splitlines()];counts[split]=dict(collections.Counter(r['kind'] for r in rows))
 for i,r in enumerate(rows):
  h=hashlib.sha256(render(r['episode']).encode()).hexdigest();assert h not in seen or seen[h]==split;seen[h]=split
  # Chat and no-tool derivatives must stay with the same source family.
  if r['source']=='chat' or r['kind']=='none':
   family=r['family'];assert family not in families or families[family]==split;families[family]=split
  t,m,n=encode_episode(tok,r['episode']);assert np.array_equal(t,a[split+'_ids'][i]);assert np.array_equal(m,a[split+'_mask'][i]);assert n==a[split+'_length'][i]
  assert t[:n].tolist()==tok.encode(render(r['episode'])).ids
  assert m.sum()>0 and not m[n-1:].any();assert t.max()<16384
  for c in r.get('calls',[]):assert execute(c) is not None
  encoded_targets[split]+=int(m.sum())
cursor=0;total=targets=nonpad=0;indices=[]
for endpoint in MILESTONES:
 while total<endpoint:
  n=min(1024,endpoint-total);_,_,supervised,real=batch(a,order,cursor,n);indices.extend(order[cursor:cursor+2].tolist());cursor+=2;total+=n;targets+=supervised;nonpad+=real
assert total==5000000 and cursor<=len(order)
result={'passed':True,'counts_by_kind':counts,'cross_split_exact_episode_overlap':0,'chat_family_cross_split_overlap':0,'mask_roundtrip_and_padding_verified':True,'fixture_targets_executable':True,'per_arm_processed_input_tokens':total,'per_arm_nonpadding_input_tokens':nonpad,'per_arm_supervised_targets':targets,'per_arm_rows':cursor,'per_arm_unique_rows':len(set(indices)),'per_arm_repeated_rows':len(indices)-len(set(indices)),'limits':'Near-duplicate screening applies to chat first-user text; synthetic test case counts are correlated by template and must not be treated as independent natural-language evidence.'}
(ROOT/'reports/sft-v1/data-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
