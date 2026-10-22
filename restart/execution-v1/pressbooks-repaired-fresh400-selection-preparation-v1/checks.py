"""Sampling and capture-role fixtures only. No retained metadata/source reads."""
import sqlite3,hashlib,json,copy
import select_core,adapter
n=0
def ok(v):
 global n
 assert v;n+=1
c=sqlite3.connect(':memory:');c.execute('CREATE TABLE texts(text_SHA256 BLOB,M1_content_tokens,UTF8_bytes,first_source,first_ordinal,fresh_population)')
for i in range(1,501):c.execute('INSERT INTO texts VALUES(?,?,?,?,?,?)',(hashlib.sha256(str(i).encode()).digest(),i,3*i,1,i,int(i>10)))
ctx=lambda s,o:{'book_url':'https://book/'+str(o%5),'family_uncertainty':True}
a=select_core.select(c,'FROZEN_SYNTHETIC_SEED',200,lambda:None,ctx);b=select_core.select(c,'FROZEN_SYNTHETIC_SEED',200,lambda:None,ctx)
ok(a==b);ok(len(a['draws'])==400);ok(a['fresh_population_distinct_raw_SHA']==490);ok(a['fresh_population_M1_content_tokens']==sum(range(11,501)))
u=[r for r in a['draws'] if r['mode'].startswith('UNIFORM')];w=[r for r in a['draws'] if r['mode'].startswith('TOKEN')];ok(len({r['text_SHA256'] for r in u})==200);ok([r['draw'] for r in w]==list(range(1,201)))
rows=list(c.execute('SELECT text_SHA256,M1_content_tokens,UTF8_bytes,first_source,first_ordinal FROM texts WHERE fresh_population=1 ORDER BY text_SHA256'));h=hashlib.sha256()
for row in rows:h.update(select_core.transcript([row[0].hex(),*row[1:]]))
ok(h.hexdigest()==a['ordered_fresh_frame_SHA256']);ranks=sorted(rows,key=lambda r:(hashlib.sha256(b'FROZEN_SYNTHETIC_SEED\nUNIFORM\n'+r[0]).digest(),r[0]));ok([r['text_SHA256'] for r in u]==[r[0].hex() for r in ranks[:200]])
for r in w:
 p=select_core.integer('FROZEN_SYNTHETIC_SEED',r['draw'],a['fresh_population_M1_content_tokens']);cum=0
 for row in rows:
  if cum<=p<cum+row[1]:ok(r['text_SHA256']==row[0].hex());break
  cum+=row[1]
lookup=lambda s,o:{'source_id':s,'ordinal':o,'text_SHA256':hashlib.sha256(str(o).encode()).hexdigest(),'text_UTF8_bytes':3*o,'line_bytes':3*o+100,'line_SHA256':'1'*64,'line_offset':o*10000,'ends_LF':1}
d=adapter.adapt(a,lookup);ok(sum(len(r['draw_roles']) for r in d['selected_capture_occurrences'])==400);ok(adapter.verify_derived(d)==d['stats']);ok(d['draws']==a['draws'])
ok(len({r['context']['book_url'] for r in a['draws']})==5);ok(all(r['capture_ordinal']>10 for r in a['draws']))
for change in ['missingrole','badstats','nonfreshstatus','locatorcost']:
 x=copy.deepcopy(a);f=lookup
 if change=='missingrole':x['draws'].pop()
 if change=='badstats':x['unique_capture_UTF8_bytes']+=1
 if change=='nonfreshstatus':x['status']='PARTIAL'
 if change=='locatorcost':f=lambda s,o:{**lookup(s,o),'line_bytes':4000001}
 try:adapter.adapt(x,f)
 except ValueError:n+=1
 else:raise AssertionError(change)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_NO_ACTUAL_DRAW','controls':n,'retained_metadata_or_text_reads':0}))
# Exercise the actual metadata-only engine against synthetic closed databases.
import tempfile,os
from pathlib import Path
import engine,source_guard
with tempfile.TemporaryDirectory() as z:
 root=Path(z);db=sqlite3.connect(root/'candidate');family=sqlite3.connect(root/'family');frame=sqlite3.connect(root/'frame')
 db.executescript('CREATE TABLE texts(text_SHA256 BLOB,UTF8_bytes,M1_content_tokens,candidate,fresh_population,first_source,first_ordinal,language_pass,explicit_known_hold,generic_mask,queue_mask,prior_reviewed_or_held,source_flags,family_uncertainty,occurrences);CREATE TABLE occurrences(source_id,ordinal,text_SHA256 BLOB,line_offset,line_bytes,line_SHA256 BLOB,source_flags,identity_holds,lead_status,lead_root_id);')
 family.executescript('CREATE TABLE rows(source_id,ordinal,lead_status,existing_flags,identity_holds,id_id,url_id,book_url_id,lead_root_id);CREATE TABLE strings(string_id PRIMARY KEY,value);');family.execute('INSERT INTO strings VALUES(1,?)',('https://synthetic/book',))
 frame.execute('CREATE TABLE records(ordinal,line_offset,line_bytes,ends_LF,line_SHA256 BLOB,flags,text_SHA256 BLOB,text_UTF8_bytes)')
 for i in range(1,211):
  h=hashlib.sha256(str(i).encode()).digest();line=hashlib.sha256(b'JSON'+str(i).encode()).digest()
  db.execute('INSERT INTO texts VALUES('+','.join('?'*15)+')',(h,3*i,i,1,1,1,i,1,0,0,0,0,0,1,1));db.execute('INSERT INTO occurrences VALUES('+','.join('?'*10)+')',(1,i,h,i*10000,3*i+100,line,0,0,1,1));family.execute('INSERT INTO rows VALUES(?,?,?,?,?,?,?,?,?)',(1,i,1,0,0,1,1,1,1));frame.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?)',(i,i*10000,3*i+100,1,line,0,h,3*i))
 for d in [db,family,frame]:d.commit();d.close()
 item=lambda n:{'path':str(root/n),'stat':source_guard.ident((root/n).stat())}
 p={'candidate_frame':item('candidate'),'family_frame':item('family'),'sources':[{'source_id':1,'frame':item('frame')}],'expected_fresh':[210,sum(range(1,211)),3*sum(range(1,211))],'sampling_seed':'SYNTHETIC_ACTUAL_ENGINE'}
 out=root/'out';out.mkdir();r=engine.run(p,out,lambda extra=0:None);ok(r['status'].startswith('COMPLETE'));ok(r['draw_roles']==400);ok(r['source_body_reads']==0);s=json.loads((out/'fresh-review-selection.json').read_text());derived=json.loads((out/'capture-selection.json').read_text());ok(adapter.verify_derived(derived)==r['stats']);ok(len(s['draws'])==400);ok(all(v['context']['family_uncertainty']==1 and len(v['context']['raw_occurrences'])==1 for v in s['draws']));ok(len(list(out.iterdir()))==3)
 p['expected_fresh'][0]+=1;other=root/'refuse';other.mkdir()
 try:engine.run(p,other,lambda extra=0:None)
 except ValueError:ok(not list(other.iterdir()))
 else:raise AssertionError('incorrect_population_accepted')
print(json.dumps({'status':'PASS_SYNTHETIC_SAMPLING_AND_ACTUAL_ENGINE','controls':n,'retained_metadata_or_text_reads':0}))
