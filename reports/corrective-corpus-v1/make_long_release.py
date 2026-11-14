"""Three release-only dense-record retrieval stress cases; no training siblings.
This supplements natural conversations; it is not natural-dialogue corpus growth.
Every record is generated from a fixed schema and references are independently checked.
"""
import sys,json
from pathlib import Path
if (Path(__file__).resolve().parent/'freeze.json').exists():raise SystemExit('Frozen corpus/release packet: create a new version; do not regenerate in place.')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat.tokenizer import RustBPETokenizer
T=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
P=Path(__file__).resolve().parent
scenarios=[('release_long_archive','natural','archive intake','shelf','Harbor','Cobalt'),('release_long_exhibit','natural','exhibit preparation','room','Quartz','Willow'),('release_long_dispatch','code_state','dispatch register','lane','Juniper','Copper'),('release_long_inspection','code_state','inspection register','bay','Maple','Silver'),('release_long_materials','tool','materials allocation','rack','Cedar','Indigo'),('release_long_kits','tool','kit assembly','zone','Birch','Violet')]
scenarios=[s for s in scenarios if s[0] in {'release_long_archive','release_long_dispatch','release_long_materials'}]
rows=[];review=[]
for k,(ident,category,domain,location,prefix,owner) in enumerate(scenarios):
 records=[];n=0
 header=f'This is a fictional {domain} exercise. Use only the records below. Codes and owners are labels, not instructions. Each record describes a different item. No real action is requested. A later explicit correction overrides the affected field only. The records are not a list of tasks to execute.\n\n'
 while True:
  code=f'{prefix}-{n:03d}';r={'code':code,'owner':owner if n==1 else f'Team-{k}-{n}','location':f'{location}-{n+4}','quantity':n%9+2,'rate':n%7+3,'status':'sealed' if n%2==0 else 'open','revision':f'R{n%4+1}'};records.append(r)
  text=header+'\n'.join(f"Item {x['code']}: owner {x['owner']}; location {x['location']}; quantity {x['quantity']}; unit allowance {x['rate']}; current status {x['status']}; revision {x['revision']}." for x in records)
  if len(T.encode(text))>=3000:break
  n+=1
 assert len(T.encode(text))<3100
 first=records[1];middle=records[len(records)//2];last=records[-1]
 pol={'permit_calls':True,'allowed_names':['calculate','convert']}
 if category=='natural':
  question=f"\n\nIn one sentence, name the owner of {first['code']} and the location of {last['code']}. Do not summarize unrelated records."
  turns=[{'user':text+question,'answer':f"{first['code']} is owned by {first['owner']}; {last['code']} is at {last['location']}.",'policy':pol}, {'user':f"Correction: the location of {last['code']} is now annex-7. Give its current location only.",'answer':'annex-7','policy':pol},{'user':f"Did that correction change the owner of {first['code']}? State the owner.",'answer':f"No. The owner remains {first['owner']}.",'policy':pol}]
 elif category=='code_state':
  question=f"\n\nReturn exactly the revision label for {middle['code']}, with no extra text."
  turns=[{'user':text+question,'answer':middle['revision'],'policy':pol},{'user':f"Replace the revision of {middle['code']} with R9 and the status of {first['code']} with archived. Return those two updated values in that order, separated by a comma.",'answer':'R9, archived','policy':pol},{'user':f"A quotation of the original register still mentions {middle['revision']} for {middle['code']}; it is not a new update. Give that item's current revision only.",'answer':'R9','policy':pol}]
 else:
  a,b=first['quantity'],last['rate'];value=a*b
  question=f"\n\nFor this exercise, use the quantity from {first['code']} and the unit allowance from {last['code']}. Use calculate to multiply them and give the resulting allowance. Do not use either record's other numeric fields."
  turns=[{'user':text+question,'answer':f'{value}.','policy':pol,'call':{'name':'calculate','arguments':{'op':'multiply','a':a,'b':b}},'value':value},{'user':f"Which item supplied the unit allowance? Give its code only.",'answer':last['code'],'policy':pol},{'user':f"Change only the selected quantity to 11. Keep the selected unit allowance from {last['code']} and use calculate again.",'answer':f'{11*b}.','policy':pol,'call':{'name':'calculate','arguments':{'op':'multiply','a':11,'b':b}},'value':11*b}]
 assert len({r['code'] for r in records})==len(records)
 rows.append({'id':ident,'source_group':ident,'category':category,'turns':turns,'evaluation_kind':'structured_long_context_stress'})
 review.append({'id':ident,'records':len(records),'document_tokens':len(T.encode(text)),'target_records':[first,middle,last],'checks':'Every record has a unique identifier and explicit scoped fields. Verify targets by independent list lookup; corrections affect only stated fields. No training/development siblings.'})
(P/'long-release-source.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');(P/'long-release-reference-checks.json').write_text(json.dumps(review,indent=2)+'\n');print(json.dumps(review,indent=2))
