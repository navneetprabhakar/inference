import sys,json,copy
from pathlib import Path
P=Path(__file__).resolve().parent;OLD=P.parent/'phase-a-2026-10-28';sys.path.insert(0,str(OLD))
from tasks import QUERIES,oracle
from build import serial

def facts(s,scope,style):
 f=s['family']
 if scope=='single':
  if f=='name':return f"{s['item']}: owner {s['name']}." if style=='kv' else f"The {s['item']} belongs to {s['name']}."
  if f=='location':return f"{s['item']}: on the {s['place']}." if style=='kv' else f"The {s['item']} is on the {s['place']}."
  if f=='distractor':return f"{s['item']}: {s['color']}." if style=='kv' else f"The {s['item']} is {s['color']}."
  return f"Meeting: {s['time']}." if style=='kv' else f"The meeting is at {s['time']}."
 if style=='kv':
  a=f"{s['item']}: {s['color']}; owner {s['name']}; on the {s['place']}.";b=f"{s['other']}: {s['other_color']}; owner {s['other_name']}; on the {s['other_place']}.";extra=f" Meeting: {s['time']}. Delivery: {s['other_time']}."
 else:
  a=f"The {s['item']} is {s['color']}. The {s['item']} belongs to {s['name']}. The {s['item']} is on the {s['place']}.";b=f"The {s['other']} is {s['other_color']}. The {s['other']} belongs to {s['other_name']}. The {s['other']} is on the {s['other_place']}.";extra=f" The meeting is at {s['time']}. The delivery is at {s['other_time']}."
 return ' '.join([a,b] if s['target_first'] else [b,a])+extra

def query(s,wording,mode):
 if mode=='original':return QUERIES[s['family']][wording].format(**s)
 return {'name':f"Copy the complete owner name of the {s['item']} from the facts. Return the name only.",'location':f"Copy the location of the {s['item']} from the facts. Return the location word only.",'distractor':f"Copy the color of the {s['item']} from the facts. Return the color word only.",'time':'Copy the meeting time from the facts. Return HH:MM only.'}[s['family']]

def main():
 assert not (P/'freeze.json').exists()
 matrix=json.loads((OLD/'private/prepared-v2/matrix.json').read_text());rows=[]
 for r in matrix:
  s=r['scenario']
  if r['cell']!='D' or s['family'] not in ['name','location','distractor','time']:continue
  for scope in ['full','single']:
   for style in ['kv','sentence']:
    for instruction in ['original','copy']:
     q=query(s,r['wording'],instruction);f=facts(s,scope,style);u=q+' '+f if s['question_first'] else f+' '+q
     if (scope,style,instruction)==('full','kv','original'):assert u==r['messages'][0]['content']
     messages=[{'role':'user','content':u}];ids,_=serial(messages);assert len(ids)+32<=256
     rows.append({'id':r['id']+'-'+scope+'-'+style+'-'+instruction,'source_id':r['id'],'family':s['family'],'scenario':s,'scope':scope,'style':style,'instruction':instruction,'messages':messages,'expected':oracle(s)[0],'prompt_tokens':len(ids)})
 assert len(rows)==1024
 (P/'private/probes.json').write_text(json.dumps(rows,indent=2)+'\n')
 (P/'spec.json').write_text(json.dumps({'purpose':'Posthoc diagnostic on128 previously evaluated D scenarios; not independent heldout evidence','checkpoint':'restart/retained-screen-2026-10-29/private/arm-1/checkpoint.pkl','matrix':'2 scopes x2 fact formats x2 query forms','records':1024,'cap':32,'context':256,'limits':{'positions':5000000,'updates':0,'assistant':0,'narrative':0,'seconds':600},'historical_training_ledger':'closed, unchanged; this is separately authorized inference only'},indent=2)+'\n')
 print('Prepared1024 matched probes;128 original prompts match byte-for-byte.')
if __name__=='__main__':main()
