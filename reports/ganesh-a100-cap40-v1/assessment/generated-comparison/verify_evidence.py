"""Verify complete local diagnostic evidence without loading model weights."""
import hashlib,json,sys
from pathlib import Path
from cloud_training.nano_chat_format import encode_conversation,parse_generated
P=Path(__file__).resolve().parent
receipt=json.loads((P/'input-receipt.json').read_text())
for f,h in receipt['inputs'].items():assert hashlib.sha256((P/f).read_bytes()).hexdigest()==h,f
for ck,v in receipt['retained_checkpoints'].items():assert hashlib.sha256((Path(v['path'])/'manifest.json').read_bytes()).hexdigest()==v['manifest_sha256'],ck
sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
panel=json.loads((P/'panel.json').read_text());expected={(x['id'],i):r for x in panel['pairs'] for i,r in enumerate(x['variants'])}
checks={}
for ck in receipt['retained_checkpoints']:
 for suffix,count in [('',192),('-rollouts',72)]:
  file=ck+suffix+'.jsonl';rows=[json.loads(l) for l in (P/file).read_text().splitlines()];assert len(rows)==count
  keys=set()
  for r in rows:
   key=(r['pair'],r['variant'],r['mode'],r.get('turn'));assert key not in keys;keys.add(key)
   assert r['checkpoint_manifest_sha256']==receipt['retained_checkpoints'][ck]['manifest_sha256']
   assert len(r['raw_ids'])<=64 and tok.decode(r['raw_ids'])==r['raw_text']
   if not suffix:
    prompt=expected[(r['pair'],r['variant'])]['prompt'];assert r['prompt']==prompt
    prefix=tok.encode(prompt+'\nAnswer:',prepend=tok.get_bos_token_id()) if r['mode']=='plain' else encode_conversation(tok,[{'role':'user','content':prompt}],policies=[{'permit_calls':False,'allowed_names':[]}],context=2048,for_generation=True,reply_budget=64)['ids']
    assert prefix==r['prefix_ids']
    assert parse_generated(tok,r['raw_ids'],reply_budget=64)==r['parsed']
   elif r['mode']=='chat':
    actions=[x for x in r['result']['events'] if x['kind']=='model_action'];assert r['raw_ids']==(actions[0]['raw_ids'] if actions else [])
    if r['result'].get('error_code')=='session_blocked':assert not r['raw_ids']
  checks[file]={'records':count,'sha256':hashlib.sha256((P/file).read_bytes()).hexdigest()}
(P/'verification.json').write_text(json.dumps({'passed':True,'scope':'input/checkpoint manifest identities, exact serialized prefixes, complete raw counts and IDs, parser equivalence; not semantic acceptance','files':checks},indent=2)+'\n')
print('PASS: 576 panel + 216 rollout records; exact inputs/IDs/parser and retained identities verified.')
