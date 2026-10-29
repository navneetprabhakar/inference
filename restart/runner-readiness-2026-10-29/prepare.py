import json,hashlib,random,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;PROJECT=P.parents[1];OLD=P.parent/'phase-a-2026-10-28';COMP=P.parent/'phase-a-completion-2026-10-29'
sys.path.insert(0,str(OLD));from build import serial

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert not (P/'freeze.json').exists()
 replay=PROJECT/'restart/conversation-improvement-v1/private/replay.npy';a=np.load(replay,mmap_mode='r');assert a.shape==(400,8,257) and a.dtype==np.uint16
 assert int(a.min())>=0 and int(a.max())<32000
 rng=random.Random(291026);indices=[]
 for _ in range(3):
  deck=list(range(400));rng.shuffle(deck);indices.extend(deck)
 indices=indices[:1000]
 save('replay.json',{'path':str(replay.relative_to(PROJECT)),'sha256':sha(replay),'shape':list(a.shape),'dtype':str(a.dtype),'indices':indices,'selection':'Three seeded shuffled passes, truncated to1000 batches; all arms share exact replay order. 400 historical native-token batches reused, not new broad corpus.','targets_per_update':2048,'targets_per_replay_arm':2048000})
 rows=[];items=['cup','bag','box','hat'];colors=['red','blue','green','white'];places=['desk','shelf','bench','chair']
 for f in ['color','location','missing','correction']:
  for i in range(16):
   item=items[i%4];color=colors[(i//4+i)%4];place=places[(i//4+2*i)%4];nextc=colors[(colors.index(color)+1)%4]
   if f=='color':u=[f'The {item} is {color}. Which color was given?',f'According to the label, this {item} is {color}. State its color.',f'What color is the {item}? The record says {color}.',f'For the {item}, the listed color is {color}. Return that color.'][i%4];turns=[(u,color)]
   elif f=='location':u=[f'The {item} rests on the {place}. Where is it?',f'Location of the {item}: {place}. Give that location.',f'Where was the {item} put? It was put on the {place}.',f'The note places the {item} on the {place}. Name the place.'][i%4];turns=[(u,place)]
   elif f=='missing':turns=[(f'The {item} is {color}, but no owner is named. Who owns it?','Not supplied.')]
   else:turns=[(f'The {item} is {color}. Give its color.',color),(f'Correction: the {item} is {nextc}. Give its current color.',nextc)]
   messages=[{'role':role,'content':text} for pair in turns for role,text in zip(['user','assistant'],pair)];ids,mask=serial(messages)
   rows.append({'id':f'preserve-{f}-{i:02}','family':f,'messages':messages,'ids':ids,'mask':mask})
 save('private/preservation.json',rows)
 spec=json.loads((COMP/'experiment-spec.json').read_text());spec.update({'status':'IMPLEMENTED_NOT_TRAINING_AUTHORIZED','data_dir':str((OLD/'private/prepared-v2').relative_to(PROJECT)),'source':'restart/foundation-resolution-v1/B/checkpoint.pt','precision':'bf16 compute; fp32 master weights and moments','dropout':0,'replay_manifest':'replay.json','preservation':'private/preservation.json','evaluation_scope':'source baseline and each sentinel/endpoint: preservation; sentinel at250/500; matrix+counterfactual at1000','futility_stop':'Disabled until independently reviewed intelligibility metric exists; numeric/resource/implementation stops remain mandatory.'});save('config.json',spec)
 print('Prepared 1000 replay batch indices and64 preservation conversations /80 turns.')
if __name__=='__main__':main()
