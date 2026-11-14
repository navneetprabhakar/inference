"""Decode every raw action for full review; no filtering or answer rewriting."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat.tokenizer import RustBPETokenizer
P=Path(__file__).parent;tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
for name in sys.argv[1:]:
 path=P/name;report=json.loads(path.read_text());rows=[]
 for record in report['records']:
  row={k:record.get(k) for k in ('session','turn','user','policy','rubric','reply_budget','assessment')}
  row['result']=record.get('result')
  row['decoded_actions']=[tok.decode(e['raw_ids']) for e in (record.get('result') or {}).get('events',[]) if 'raw_ids' in e]
  rows.append(row)
 output={'raw_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':report['status'],'records':rows}
 path.with_name(path.stem+'-decoded.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
 print(name,report['status'],len(rows))
