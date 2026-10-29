"""Prospective paired SFT curriculum; no contrastive loss or model execution."""
import sys,json,random,copy,collections
from pathlib import Path
P=Path(__file__).resolve().parent;OLD=P.parent/'phase-a-2026-10-28';sys.path.insert(0,str(OLD))
from tasks import FAMILIES,QUERIES,oracle
from build import serial,sp
ITEMS=['bottle','notebook','helmet','scarf','lantern','wallet','suitcase','ribbon']
NEW_ITEMS=['vase','candle','pouch','racket','ladle','glove','kite','folder']
COLORS=['red','blue','green','yellow','white','black','pink','purple']
PLACES=['desk','shelf','table','bench','cabinet','drawer','basket','chair']
VENUES=['office','studio','ballroom','lobby','kitchen','library','lounge','auditorium']
NEW_PLACES=['alcove','foyer','cellar','veranda','loft','courtyard','archive','vestibule']
FIRST=['Alice','Bruno','Celia','Damon','Ethan','Freya','Gavin','Hazel','Isaac','Julia','Kiran','Luca','Mabel','Nolan','Opal','Pavel']
LAST=['Adler','Benton','Carver','Dalton','Ellis','Foster','Grant','Hart','Irwin','Jensen','Keller','Lane','Morris','Nash','Orton','Price']
NEW_FIRST=['Zelia','Quirin','Veda','Hollis','Tobin','Neriah','Xenia','Yara']
NEW_LAST=['Aldwick','Brinlow','Cavell','Dunsley','Eldmere','Fenwick','Gorse','Huxley']
NEW_QUERY={'name':'From the supplied facts, whose name is listed as owner of the {item}? Give that full name only.','time':'Read the stated meeting time and reproduce HH:MM only.','location':'According to the record, on what place is the {item}? Give only the place word.','distractor':'Use the facts to return just the color attached to the {item}.','state':'Read the current facts and give just the color of the {item}.','missing':'Give the supplied full owner name for the {item}, or Unknown if none is supplied.','clarification':'Ask for the unspecified meeting {slot}; do not invent a value.','format':'State the supplied color of the {item}. {style}'}

def save(name,obj):(P/name).write_text(json.dumps(obj,indent=2)+'\n')
def world(i,f,dev=False):
 j=i//8;item_index=(i%8+i//16)%8;item=(NEW_ITEMS if dev else ITEMS)[item_index];rr=random.Random(291029+i)
 color=COLORS[j%8];place=PLACES[(j+3*(j//8))%8]
 first,last=(NEW_FIRST,NEW_LAST) if dev and i>=32 else (FIRST,LAST)
 name=first[i%len(first)]+' '+last[(i//len(first))%len(last)]
 return dict(family=f,item=item,other=(NEW_ITEMS if dev else ITEMS)[(item_index+1+j//8)%8],color=color,other_color=rr.choice(COLORS),new_color=COLORS[(j+3)%8],new_other_color=rr.choice(COLORS),name=name,other_name=FIRST[(i+7)%16]+' '+LAST[(i//16+3)%16],time=f'{(18+i//60 if dev else i//60)%24:02d}:{i%60:02d}',other_time=f'{(i//60+11)%24:02d}:{(i+17)%60:02d}',place=(NEW_PLACES[i%8] if dev else VENUES[(j+3*(j//8))%8]) if f=='clarification' else place,other_place=rr.choice(PLACES),present=bool(j%2),sentence=bool((j//2)%2),slot='time' if j%2==0 else 'location',world_id=('dev-' if dev else 'train-')+str(i))

def changed(s,i):
 t=copy.deepcopy(s);f=s['family'];j=i//8
 if f=='name':t['name']=FIRST[(i+5)%16]+' '+LAST[(i//16+7)%16]
 elif f=='time':t['time']=f'{(int(s["time"][:2])+6)%24:02d}:{(int(s["time"][3:])+23)%60:02d}'
 elif f=='location':t['place']=PLACES[(PLACES.index(s['place'])+1+j//8)%8]
 elif f in ['distractor','format']:t['color']=COLORS[(j%8+1+j//8)%8]
 elif f=='state':t['color'],t['new_color']=s['new_color'],s['color']
 elif f=='missing':t['present']=not s['present']
 else:
  if s['slot']=='time':t['time']=f'{(int(s["time"][:2])+9)%24:02d}:{(int(s["time"][3:])+31)%60:02d}'
  else:t['place']=VENUES[(VENUES.index(s['place'])+3)%8]
 assert oracle(s)!=oracle(t)
 return t

def render(s,wording,style,scope,question_first,target_first,dev=False):
 f=s['family'];ctx={**s,'style':'Answer with exactly one sentence: The ITEM is COLOR.' if s['sentence'] else 'Answer with the color word only.'}
 q=(NEW_QUERY[f] if dev else QUERIES[f][wording]).format(**ctx)
 owner=s['name'] if f!='missing' or s['present'] else 'not supplied'
 if f=='clarification':facts='Meeting time: not supplied. Meeting place: not supplied.'
 elif scope=='single':
  if f in ['name','missing']:facts=f"{s['item']}: owner {owner}." if style=='kv' else (f"The {s['item']} belongs to {owner}." if owner!='not supplied' else f"The owner of the {s['item']} is not supplied.")
  elif f=='location':facts=f"{s['item']}: on the {s['place']}." if style=='kv' else f"The {s['item']} is on the {s['place']}."
  elif f=='time':facts=f"Meeting: {s['time']}." if style=='kv' else f"The meeting is at {s['time']}."
  else:facts=f"{s['item']}: {s['color']}." if style=='kv' else f"The {s['item']} is {s['color']}."
 else:
  if style=='kv':
   a=f"{s['item']}: {s['color']}; owner {owner}; on the {s['place']}.";b=f"{s['other']}: {s['other_color']}; owner {s['other_name']}; on the {s['other_place']}.";extra=f" Meeting: {s['time']}. Delivery: {s['other_time']}."
  else:
   a=f"The {s['item']} is {s['color']}, with owner {owner}, on the {s['place']}.";b=f"The {s['other']} is {s['other_color']}, with owner {s['other_name']}, on the {s['other_place']}.";extra=f" The meeting is at {s['time']}; delivery is at {s['other_time']}."
  facts=' '.join([a,b] if target_first else [b,a])+extra
 users=[q+' '+facts if question_first else facts+' '+q]
 if f=='state':users.extend([f"Correction: the {s['item']} is {s['new_color']}, not {s['color']}. What color is the {s['item']} now?",f"The {s['other']} is now {s['new_other_color']}. What color is the {s['item']} now?"])
 if f=='clarification':users.append(f"The meeting is at {s['time']}. Now write the reminder." if s['slot']=='time' else f"The meeting is in the {s['place']}. Now write the reminder.")
 return [m for u,a in zip(users,oracle(s)) for m in [{'role':'user','content':u},{'role':'assistant','content':a}]]

def record(s,i,side,view,dev=False):
 # Within each pair, presentation is identical. Across passes, both fact style and query change.
 style=['kv','sentence'][(i//64+view)%2];scope=['full','single'][(i//128+view)%2];qfirst=bool(((i//32)+view)%2);tfirst=bool(((i//16)+view)%2);wording=(i+7*view)%20
 if dev:
  rr=random.Random(310029+i);style=rr.choice(['kv','sentence']);scope=rr.choice(['full','single']);qfirst=bool(rr.randrange(2));tfirst=bool(rr.randrange(2))
 msgs=render(s,wording,style,scope,qfirst,tfirst,dev);ids,mask=serial(msgs)
 return dict(id=f'{s["family"]}-{i:03}-{side}',pair=f'{s["family"]}-{i:03}',side=side,scenario=s,view=view,wording=wording,style=style,scope=scope,question_first=qfirst,target_first=tfirst,messages=msgs,ids=ids,mask=mask)

def main():
 assert not (P/'freeze.json').exists()
 views=[[],[]]
 for f in FAMILIES:
  for i in range(256):
   a=world(i,f);b=changed(a,i)
   for view in [0,1]:
    views[view]+=[record(a,i,'before',view),record(b,i,'after',view)]
 for view in [0,1]:save(f'private/view-{view}.json',views[view])
 schedule=[]
 for view in [0,1]:
  deck=list(range(256));random.Random(291029+view).shuffle(deck)
  for i in deck:
   for side in [0,1]:schedule.append({'view':view,'indices':[fi*512+2*i+side for fi in range(8)]})
 save('private/schedule.json',schedule)
 dev=[]
 for f in FAMILIES:
  for i in range(64):dev.append(record(world(i,f,True),i,'dev',0,True))
 save('private/unscored-development-candidate.json',dev)
 print('4096 semantic records,2 presentation views,1024 proposed batches;512 unscored development candidates.')
if __name__=='__main__':main()
