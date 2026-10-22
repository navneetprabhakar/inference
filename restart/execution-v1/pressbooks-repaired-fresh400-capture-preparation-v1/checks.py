"""Synthetic adapter and exact rawJSON/text source capture; no retained inputs."""
import copy,gzip,hashlib,json,sqlite3,tempfile
from pathlib import Path
import adapter,capture,inventory
N=0
def ok(v):
 global N;assert v;N+=1
def refuse(f):
 global N
 try:f()
 except (ValueError,KeyError):N+=1;return
 raise AssertionError('expected refusal')
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp).resolve();out=d/'out';out.mkdir();parts=[];by={};frame=sqlite3.connect(d/'frame.sqlite');frame.executescript(inventory.SCHEMA);off=0;lh=hashlib.sha256();draws=[]
 for i in range(1,201):
  text=f'Original full synthetic English unit {i}; quotation and credits remain untouched.';u=f'https://example.pressbooks.pub/book/chapter/u{i}/';obj={'id':u,'text':text,'source':'pressbooks','added':'2024-01-01T00:00:00','created':'01-01-2024','metadata':{'license':'CC BY https://creativecommons.org/licenses/by/4.0/','url':u,'book_url':'https://example.pressbooks.pub/book/front-matter/introduction/','title':'Book','author':'Author','institution':'Example','subject':'Instruction'}};raw=(json.dumps(obj)+'\n').encode();h=hashlib.sha256(raw).digest();r,_=inventory.row(i,off,len(raw),True,h,raw);frame.execute('INSERT INTO records VALUES('+','.join(['?']*21)+')',r);by[(1,i)]={'source_id':1,'ordinal':i,'line_offset':off,'line_bytes':len(raw),'ends_LF':1,'line_SHA256':h.hex(),'text_SHA256':r[17].hex(),'text_UTF8_bytes':r[18],'existing_flags':r[5],'identity_holds':0,'lead_status':1};parts.append(raw);lh.update(json.dumps([i,off,len(raw),1,h.hex()],separators=(',',':')).encode()+b'\n');off+=len(raw)
  draws.append({'mode':'UNIFORM_DISTINCT_RAW_SHA_WITHOUT_REPLACEMENT','draw':i,'text_SHA256':r[17].hex(),'capture_source_id':1,'capture_ordinal':i,'UTF8_bytes':r[18],'M1_content_tokens':20+i})
 frame.commit();frame.close();first=draws[0]
 for i in range(1,201):draws.append({**first,'mode':'TOKEN_WEIGHTED_WITH_REPLACEMENT_NOT_BYTES','draw':i})
 selection={'status':'FROZEN_PRE_REVIEW_CANDIDATE_QUALITY_AUDIT_SELECTION_NOT_M2_ACCEPTANCE','draws':draws,'unique_drawn_raw_SHA':200,'unique_capture_UTF8_bytes':sum(v['text_UTF8_bytes'] for v in by.values()),'unique_capture_M1_content_tokens':sum(20+i for i in range(1,201)),'largest_selected_UTF8_bytes':max(v['text_UTF8_bytes'] for v in by.values())}
 result=adapter.adapt(selection,lambda s,o:by[(s,o)]);ok(adapter.verify_derived(result)==result['stats']);ok(len(result['selected_capture_occurrences'])==200);ok(sum(len(r['draw_roles']) for r in result['selected_capture_occurrences'])==400);ok(len(result['selected_capture_occurrences'][0]['draw_roles'])==201)
 (d/'selection.json').write_text(json.dumps(result));source=d/'source.gz';source.write_bytes(gzip.compress(b''.join(parts)))
 def binding(p):
  s=p.stat();return {'path':str(p),'stat':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
 sb={**binding(source),'bytes':source.stat().st_size,'SHA256':hashlib.sha256(source.read_bytes()).hexdigest()};fb={**binding(d/'frame.sqlite'),'rows':200,'ordered_line_locator_SHA256':lh.hexdigest()}
 report=capture.run({'selection':str(d/'selection.json'),'sources':[{'source_id':1,'raw':sb,'frame':fb,'known_holds':[]}]},out,lambda extra=0:None);ok(report['draw_count']==400 and report['unique_captured_raw_SHA']==200);ok(report['raw_JSON_to_text_inverse_exact']);ok(len(list(out.glob('*.text.utf8')))==200);ok(len(list(out.glob('*.source.json')))==200);full=json.loads((out/'records.json').read_text());ok(sum(len(r['draw_roles']) for r in full['sources'][0]['captures'])==400);ok(hashlib.sha256((out/'records.json').read_bytes()).hexdigest()==report['records_SHA256'])
 # Actual production worker path with full synthetic gzip reader + saved JSON/text inverse.
 import pilot,os,argparse,signal
 from unittest.mock import patch
 workerout=d/'worker-out';workerout.mkdir()
 for name,cap in pilot.SLOTS.items():(workerout/name).write_bytes(b' '*cap)
 a=argparse.Namespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='synthetic-profile',code_pins_sha256='synthetic-code')
 (workerout/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'shared_start':a.start,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}))
 workerprofile={'output':str(workerout),'selection':str(d/'selection.json'),'sources':[{'source_id':1,'raw':sb,'frame':fb,'known_holds':[]}]}
 with patch.object(pilot,'verify',return_value=workerprofile) as verifier,patch.object(pilot,'guard',return_value=None):
  pilot.worker(a);ok(verifier.call_count==2)
 wr=json.loads((workerout/'result.json').read_text());ok(wr['status']=='COMPLETE_FRESH400_DRAW_WHOLE_ORIGINAL_PRESSBOOKS_CAPTURE_NO_ADMISSION');ok(wr['unique_captured_raw_SHA']==200);ok(wr['draw_count']==400);ok(wr['raw_JSON_to_text_inverse_exact']);ok(wr['artifacts']['records.json']['SHA256']==hashlib.sha256((workerout/'records.json').read_bytes()).hexdigest());ok(len(list(workerout.glob('*.text.utf8')))==200)
 signal.setitimer(signal.ITIMER_REAL,0)
 for change in ['partial','lessdraws','duprole','uniformdup','badsha','repeatcontext','cost','locator']:
  s=copy.deepcopy(selection);lookup=lambda sid,o:by[(sid,o)]
  if change=='partial':s['status']='PARTIAL'
  if change=='lessdraws':s['draws'].pop()
  if change=='duprole':s['draws'][1]['draw']=1
  if change=='uniformdup':s['draws'][1]['text_SHA256']=s['draws'][0]['text_SHA256']
  if change=='badsha':s['draws'][0]['text_SHA256']='notSHA'
  if change=='repeatcontext':s['draws'][-1]['UTF8_bytes']+=1
  if change=='cost':s['unique_capture_UTF8_bytes']+=1
  if change=='locator':lookup=lambda sid,o:{**by[(sid,o)],'line_bytes':4000001}
  refuse(lambda:adapter.adapt(s,lookup))
 for change in ['lostrole','wrongparent','badcost']:
  bad=copy.deepcopy(result)
  if change=='lostrole':bad['selected_capture_occurrences'][0]['draw_roles'].pop()
  if change=='wrongparent':bad['selected_capture_occurrences'][0]['draw_roles'][0]['text_SHA256']='f'*64
  if change=='badcost':bad['stats']['original_JSON_bytes']+=1
  refuse(lambda:adapter.verify_derived(bad))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'retained_candidate_or_source_reads':0,'actual_synthetic_captures':200,'draw_roles_preserved':400}))
