"""Synthetic SQL, metadata selection, fullnative capture/SAX and terminal guards."""
import bz2,hashlib,json,sqlite3,tempfile,copy,os,contextlib
from pathlib import Path
from unittest.mock import patch
import select_core as sel,capture_pipeline as cap,terminal_guard as gate,source_view
N=0
B=Path(__file__).resolve().parent.parent;SEM=B/'enwiki-semantic-SAX-metadata-preparation-v3/semantic.py'
def ok(v):
 global N;assert v;N+=1
def no(fn):
 global N
 try:fn()
 except (ValueError,KeyError,sqlite3.Error,OSError):N+=1;return
 raise AssertionError('expected refusal')
h=lambda b:hashlib.sha256(b).hexdigest()
def gmeta(g,start,first,last):return {'group_ordinal':g,'compressed_start':start,'compressed_end_exclusive':start+100,'decoded_bytes':3000000,'first_page_ordinal':first,'last_page_ordinal':last,'page_count':last-first+1,'raw_SHA256':hashlib.sha256(str(g).encode()).digest()}
def row(i):return dict(zip(sel.FIELDS,(i,100+i,10000+i,4 if i%11==0 else 0,1 if i%9==0 else 64 if i%7==0 else 0,1,1,100,i%20*2,1000001 if i%5==0 else 200,hashlib.sha256(str(i).encode()).digest())))
rows=[row(i) for i in range(1,101)];groups=[gmeta(i,(i-1)*100,(i-1)*20+1,i*20) for i in range(1,6)];result=sel.scan_pages(rows,groups,{'pages':100,'groups':5},lambda:None)
want=[]
for x in rows:
 if x['namespace']==0 and not x['flags']&1:
  r=dict(x);r['raw_SHA256']=r['raw_SHA256'].hex();want.append(r)
want=sorted(want,key=lambda r:sel.priority(r))[:20];ok([r['row_ordinal'] for r in result['selected']]==[r['row_ordinal'] for r in want]);ok(result['counts']['article_frame_records']==len([r for r in rows if r['namespace']==0 and not r['flags']&1]));ok(result['article_flag_bit_counts']['deleted_text']>0);ok(result['counts']['article_pages_raw_XML_over1MB']>0);ok(result['all_native_rows']==100);ok(len(result['selected'])==20)
no(lambda:sel.scan_pages(rows[:-1],groups,{'pages':100,'groups':5},lambda:None));no(lambda:sel.scan_pages(rows[::-1],groups,{'pages':100,'groups':5},lambda:None));no(lambda:sel.scan_pages(rows[:10],groups[:1],{'pages':10,'groups':1},lambda:None))
# Build tiny readonly-compatible source schema and preserve all selected occurrences.
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);db=sqlite3.connect(d/'frame');index=sqlite3.connect(d/'index');index.row_factory=sqlite3.Row;db.execute('CREATE TABLE revisions(revision_id INTEGER,page_ordinal INTEGER,revision_ordinal INTEGER,PRIMARY KEY(revision_id,page_ordinal,revision_ordinal)) WITHOUT ROWID');index.execute('CREATE TABLE rows(row_ordinal INTEGER PRIMARY KEY,page_id INTEGER,group_ordinal INTEGER,title TEXT,raw_line_sha256 BLOB)')
 for r in rows:
  db.execute('INSERT INTO revisions VALUES(?,?,?)',(r['first_revision_id'],r['row_ordinal'],1));index.execute('INSERT INTO rows VALUES(?,?,?,?,?)',(r['row_ordinal'],r['page_id'],(r['row_ordinal']-1)//20+1,'Café &amp; title '+str(r['row_ordinal']),b'x'*32))
 db.commit();index.commit();tr=[];db.set_trace_callback(tr.append);r=sel.enrich_selected(db,index,copy.deepcopy(result),[{'code':1,'model':'wikitext','format':'text/x-wiki'}],lambda:None);ok(all('Café & title ' in q['expected_semantic_title'] for q in r['selected']));ok(all(q['all_revision_ID_occurrences']==[q['first_revision_id']] for q in r['selected']));ok(len([q for q in tr if q.startswith('SELECT page_ordinal')])==1)
 # Repeated native revisionIDs preserved as distinct ordinal occurrences.
 q=r['selected'][0];db.execute('INSERT INTO revisions VALUES(?,?,?)',(q['first_revision_id'],q['row_ordinal'],2));db.commit();q['revision_count']=2;twice=sel.enrich_selected(db,index,r,[{'code':1,'model':'wikitext','format':'text/x-wiki'}],lambda:None);ok(twice['selected'][0]['all_revision_ID_occurrences']==[q['first_revision_id']]*2)
 index.execute("UPDATE rows SET title='A &copy; B' WHERE row_ordinal=?",(q['row_ordinal'],));index.commit();no(lambda:sel.enrich_selected(db,index,copy.deepcopy(result),[{'code':1,'model':'wikitext','format':'text/x-wiki'}],lambda:None));db.close();index.close()
receipts=[]
for g in groups:
 receipts.append({'group_ordinal':g['group_ordinal'],'compressed_start':g['compressed_start'],'compressed_end_exclusive':g['compressed_end_exclusive'],'compressed_bytes':100,'decoded_bytes':g['decoded_bytes'],'decoded_SHA256':g['raw_SHA256'].hex(),'CRC_EOF_members':1,'trailing_absent':True,'actual_native_identity_SHA256':'a'*64,'frozen_index_identity_SHA256':'a'*64,'compressed_SHA256':'b'*64})
lines=[(json.dumps(r)+'\n').encode() for r in receipts];r=sel.attach_groups(lines,copy.deepcopy(result),h(b''.join(lines)),5,lambda:None);ok(len(r['selected_group_receipts'])<=5);no(lambda:sel.attach_groups(lines[:-1],copy.deepcopy(result),h(b''.join(lines)),5,lambda:None));no(lambda:sel.attach_groups(lines,copy.deepcopy(result),'0'*64,5,lambda:None));broken=copy.deepcopy(receipts);broken[0]['actual_native_identity_SHA256']='c'*64;bad=[(json.dumps(q)+'\n').encode() for q in broken];no(lambda:sel.attach_groups(bad,copy.deepcopy(result),h(b''.join(bad)),5,lambda:None))
# True synthetic XML group:19bounded pages + one1MBoversize, oneunknownmodel,
# one2revision page. Fullselected20 outcomes, onegroupread, no replacements.
HEADER=b'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo><base>https://en.wikipedia.org/wiki/Main_Page</base><namespaces><namespace key="0"/></namespaces></siteinfo>'
def b36(n):
 s='';alphabet='0123456789abcdefghijklmnopqrstuvwxyz'
 while n:n,a=divmod(n,36);s=alphabet[a]+s
 return s or '0'
def page(i):
 text=('long '*210000) if i==1 else 'Full [[A|display]] & café.\n{{unknown}} stays literal.';body=text.encode();digest=b36(int(hashlib.sha1(body).hexdigest(),16));encoded=text.replace('&','&amp;').replace('<','&lt;');model='json' if i==2 else 'wikitext';content=f'<model>{model}</model><format>text/x-wiki</format><text bytes="{len(body)}" sha1="{digest}">{encoded}</text><sha1>{digest}</sha1>';revs=[i+1000,i+1000] if i==3 else [i+1000];revision=''.join(f'<revision><id>{j}</id>{content}</revision>' for j in revs);raw=f'<page><title>A &amp; B{i}</title><ns>0</ns><id>{i}</id>{revision}</page>'.encode();return raw,body,revs,model
native=bytearray();selected=[];expectedtext={}
for i in range(1,21):
 raw,text,revs,model=page(i);a=len(native);native.extend(raw);selected.append({'row_ordinal':i,'page_id':i,'namespace':0,'flags':0,'first_revision_id':revs[0],'revision_count':len(revs),'main_text_bytes':len(text) if len(revs)==1 else -1,'group_decoded_start':a,'raw_XML_bytes':len(raw),'raw_SHA256':h(raw),'expected_model':None if len(revs)>1 else model,'expected_format':None if len(revs)>1 else 'text/x-wiki','all_revision_ID_occurrences':revs,'expected_semantic_title':f'A & B{i}','group':{'group_ordinal':1}});expectedtext[i]=text
compressed=bz2.compress(native);g={'group_ordinal':1,'compressed_start':570,'compressed_end_exclusive':570+len(compressed),'compressed_bytes':len(compressed),'compressed_SHA256':h(compressed),'decoded_bytes':len(native),'decoded_SHA256':h(native),'CRC_EOF_members':1,'trailing_absent':True};selection={'selected':selected,'selected_group_receipts':[{'receipt':g,'receipt_line_SHA256':'x'}]};planned=cap.plan(selection);ok(len(planned['decisions'])==20 and planned['decisions'][0]['precontent_capture_holds']);saved={};reads=[]
def read(g):reads.append(g['group_ordinal']);return compressed
def write(name,raw):assert name not in saved;saved[name]=raw
captured=cap.capture(selection,planned,HEADER,read,write,lambda:None,SEM);ok(reads==[1]);ok(len(captured['records'])==20);ok(captured['records'][0]['outcome']=='HELD_PRECONTENT_BOUNDS_NO_REPLACEMENT');ok(captured['records'][1]['maintext_file'] is None);ok(captured['records'][2]['native_extraction']['native_revision_IDs']==[1003,1003]);ok(captured['records'][2]['maintext_file'] is None);ok(len([n for n in saved if n.endswith('.source-text.utf8')])==17);ok(saved[captured['records'][3]['maintext_file']]==expectedtext[4]);ok(captured['records'][3]['native_extraction']['invented_XML_bytes']==0);ok(captured['whole_publisher_archive_verified'] is False)
no(lambda:cap.capture(selection,planned,HEADER,lambda g:compressed[:-1],lambda *a:None,lambda:None,SEM));no(lambda:cap.capture(selection,planned,b'<!DOCTYPE mediawiki>'+HEADER,read,lambda *a:None,lambda:None,SEM));bad=copy.deepcopy(selection);bad['selected'][3]['expected_semantic_title']='Wrong';no(lambda:cap.capture(bad,cap.plan(bad),HEADER,read,lambda *a:None,lambda:None,SEM));bad=copy.deepcopy(selection);bad['selected'][3]['all_revision_ID_occurrences']=[999];no(lambda:cap.capture(bad,cap.plan(bad),HEADER,read,lambda *a:None,lambda:None,SEM))
small=dict(cap.LIMITS,group_decoded_bytes=100);p=cap.plan(selection,small);ok(not p['groups_read_order'] and all(d['precontent_capture_holds'] for d in p['decisions']));small=dict(cap.LIMITS,compressed_bytes=1);ok(not cap.plan(selection,small)['groups_read_order']);no(lambda:cap.plan({'selected':selected[:-1],'selected_group_receipts':selection['selected_group_receipts']}))
# UNBOUND refuses before any file access/SQL/native opener.
called=[]
no(lambda:gate.validate({'status':'UNBOUND'},lambda x:called.append(x),lambda x:None,lambda p:True));ok(not called)
with patch.object(source_view.sqlite3,'connect',lambda *a,**k:(_ for _ in ()).throw(AssertionError('SQL before terminal gate'))):
 def runbad():
  with source_view.metadata_db({'status':'LIVE'},'frame',lambda:None):pass
 no(runbad)
print(json.dumps({'status':'PASS_SYNTHETIC_POSTINVENTORY_SELECTION_CAPTURE_ONLY','controls':N,'retained_native_body_reads':0,'live_SQL_or_real_selection_operations':0,'network_model_tokenizer_operations':0}))
