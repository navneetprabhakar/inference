"""Compare actual packed arrays to independently concatenated real-tokenizer rows."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_sft import JsonlConversations,FiniteEpochDataset,BestFitConversations
P=Path(__file__).parent;source=ROOT/'reports/english-first-v1/fit-train.jsonl';tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
data=JsonlConversations(source,tok,hashlib.sha256(source.read_bytes()).hexdigest());epochs=FiniteEpochDataset(data,64,seed=103,diagnostic_only=True)
a=BestFitConversations(epochs,buffer_size=1);b=BestFitConversations(epochs,buffer_size=1);rows=0;targets=0;padding=0
while True:
 try:indices=a.next_indices()
 except StopIteration:break
 ids=[];mask=[]
 for i in indices:
  x,m=epochs.get(i);ids+=x;mask+=m
 pad=a.capacity-len(ids);ids += [tok.get_bos_token_id()]*pad;mask += [0]*pad
 expected_x=ids[:-1];expected_y=[t if m else -1 for t,m in zip(ids[1:],mask[1:])]
 x,y=b.next_row()
 if x!=expected_x or y!=expected_y:raise ValueError('Packed sequence/label mismatch')
 if pad and any(v!=-1 for v in y[-pad:]):raise ValueError('Padding supervised')
 rows+=1;targets+=sum(v!=-1 for v in y);padding+=pad
Path(P/'padding-checks.json').write_text(json.dumps({'status':'pass','rows':rows,'assistant_targets':targets,'masked_padding_positions':padding,'scope':'All real64epoch packed rows; no model training'},indent=2)+'\n');print(rows,targets,padding)
