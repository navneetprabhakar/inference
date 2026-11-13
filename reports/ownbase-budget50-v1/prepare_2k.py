"""Derive complete2K sessions from the already fully reviewed immutable corpus."""
import sys,json,hashlib,collections
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from cloud_training.nano_sft import load_manifest,JsonlConversations,BestFitConversations,NATIVE_IGNORE
base=Path('runs/long-context-corpus-v3');out=Path('runs/ownbase-budget50-v1/sft-2k');assert not out.exists();out.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bm=json.loads((base/'manifest.json').read_text());load_manifest(base/'manifest.json',bm['tokenizer_sha256'],4096)
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');manifest={k:bm[k] for k in ['schema','training_admitted','tokenizer_sha256','format_version']};manifest['context_tokens']=2048;exclusions={};checks={}
for split in ['train','validation']:
 kept=[];excluded=[]
 for line in (base/(split+'.jsonl')).read_bytes().splitlines(keepends=True):
  row=json.loads(line);encoded=encode_conversation(tok,row['messages'],policies=row.get('policies'),context=4096)
  if len(encoded['ids'])<=2048:kept.append(line)
  else:excluded.append({'row_sha256':hashlib.sha256(line).hexdigest(),'tokens':len(encoded['ids'])})
 path=out/(split+'.jsonl');path.write_bytes(b''.join(kept));d=JsonlConversations(path,tok,sha(path),context=2048);pack=BestFitConversations(d);targets=0
 while True:
  try:x,y=pack.next_row()
  except StopIteration:break
  assert len(x)==len(y)==2048;targets+=sum(z!=NATIVE_IGNORE for z in y)
 assert targets==sum(d.target_counts);checks[split]={'packed_rows':pack.rows,'targets':targets,'max_tokens':max(d.lengths)};exclusions[split]=excluded
 manifest[split]={'file':path.name,'sha256':sha(path),'bytes':path.stat().st_size,'sessions':len(kept),'assistant_targets':targets}
receipt={'schema':1,'training_admitted':True,'context_tokens':2048,'format_version':bm['format_version'],'tokenizer_sha256':bm['tokenizer_sha256'],'jsonl_sha256':[manifest[s]['sha256'] for s in ['train','validation']],'parent_manifest':str(base/'manifest.json'),'parent_manifest_sha256':sha(base/'manifest.json'),'policy':'Only whole previously reviewed admitted sessions fitting2048; verbatim bytes, originalsplit, no truncation or newsemantic admission','excluded_long_sessions':exclusions,'actual_trained_targets':0,'limitations':['Small2K diagnostic curriculum, not a comprehensive generalSFT corpus','Existing development is exposed; no acceptance claim']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');load_manifest(out/'manifest.json',bm['tokenizer_sha256'],2048);(out/'verification.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
