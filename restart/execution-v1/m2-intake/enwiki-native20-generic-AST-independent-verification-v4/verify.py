from pathlib import Path
import json,hashlib,time,signal
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];ROOT=BASE/'m2-intake';SRC=ROOT/'enwiki-native-20row-capture-v1';OUT=ROOT/'enwiki-native20-generic-AST-development-v4';PREP=BASE/'enwiki-generic-AST-runner-preparation-v4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def H(s):return hashlib.sha256(s.encode()).hexdigest()
def run():
 start=time.monotonic();signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('verification30s')));signal.alarm(30)
 try:
  reg=PREP/'code-pins.json';assert sha(reg)=='28a6197b40d7a09e515ab42d2febfc631ede7601e0c4242398de4b719d176681'
  pins=json.loads(reg.read_text())['files']
  for p,h in pins.items():assert sha(Path(p))==h
  prior=json.loads((SRC/'all20-native-decisions.json').read_text());w=json.loads((OUT/'result.json').read_text());s=json.loads((OUT/'supervisor.json').read_text());assert w['status']=='COMPLETE_NATIVE20_DEVELOPMENT_AST_SECTIONS_ONLY' and s['status']=='COMPLETE_DEVELOPMENT_ONLY' and s['worker_exit_code']==0 and s['worker_receipt_SHA256']==sha(OUT/'result.json');assert len(w['records'])==20
  assert s['elapsed_seconds']<60 and s['peak_observed_tree_RSS_bytes']<=1000000000 and sum(q.stat().st_size for q in OUT.rglob('*') if q.is_file())<=5000000
  results=[];roles={'redirect':0,'nonarticle':0,'pending':0};ns=0
  for p in prior:
   row=p['selected_index_row']['row_ordinal'];q=OUT/f'row-{row}.json';r=json.loads(q.read_text());wr=next(z for z in w['records'] if z['row']==row);assert wr['SHA256']==sha(q)
   assert (r['native_page_ID'],r['native_revision_ID'],r['native_title'],r['prior_status'],r['prior_holds'],r['source_text_SHA256'])==(p['native_page_id'],p['native_revision']['id'],p['native_title'],p['status'],p['holds'],p['source_text']['local_SHA256'])
   role='redirect' if p['native_redirect_attributes'] is not None else 'nonarticle' if p['native_ns']!='0' else 'pending';assert r['preserved_role']==role and r['no_admission'];roles[role]+=1
   rec={'row':row,'role':role,'output_SHA256':sha(q)}
   if role!='pending':assert 'frame' not in r;rec['no_extraction']=True
   else:
    raw=(SRC/p['source_text_file']).read_bytes();text=raw.decode();assert len(raw)==p['source_text']['bytes'] and hashlib.sha256(raw).hexdigest()==p['source_text']['local_SHA256'];f=r['frame'];assert f['source_SHA256']==H(text);a=ba=0;nodeidx=0
    for k,u in enumerate(f['sections']):
     assert u['section_ordinal']==k and u['source_char_span'][0]==a and u['source_byte_span'][0]==ba
     a,b=u['source_char_span'];ba,bb=u['source_byte_span'];assert text[a:b]==u['raw'] and raw[ba:bb]==u['raw'].encode() and H(u['raw'])==u['raw_SHA256'];pos=a;bp=ba
     for node in u['top_nodes']:
      x,y=node['source_char_span'];bx,by=node['source_byte_span'];assert x==pos and bx==bp and node['top_node_path']==[nodeidx] and text[x:y]==node['raw'] and raw[bx:by]==node['raw'].encode() and node['raw_SHA256']==H(node['raw']);nodeidx+=1;pos=y;bp=by
     assert pos==b and bp==bb and ''.join(z['raw'] for z in u['top_nodes'])==u['raw'];assert u['preview'] is None and u['preview_SHA256'] is None and u['holds'] and u['no_admission'];a=b;ba=bb;ns+=1
    assert a==len(text) and ba==len(raw) and ''.join(u['raw'] for u in f['sections']).encode()==raw;rec.update({'complete_sections':len(f['sections']),'top_nodes':nodeidx,'source_bytes':len(raw),'exact_inverse':True})
   results.append(rec)
  assert roles=={'redirect':9,'nonarticle':6,'pending':5} and ns==27
  for p,h in pins.items():assert sha(Path(p))==h
  result={'status':'PASS_INDEPENDENT_SAVEDOUTPUT_SOURCE_INVERSE_TERMINAL_ONLY_NO_RERUN','records':results,'preserved_roles':roles,'complete_sections':ns,'structurally_held_sections':27,'provisional_preview_bytes':0,'scope':'Structural dependencies, NOT semanticqualityfailure oradmittedyield. No sourceextractor/detector/tokenizer rerun; no fullXML/livepartial/network/globalledger/model.','all138_input_code_runtime_pins_unchanged':True,'elapsed_seconds':time.monotonic()-start,'worker_receipt_SHA256':sha(OUT/'result.json'),'supervisor_receipt_SHA256':sha(OUT/'supervisor.json'),'new_admitted_documents':0,'new_admitted_tokens':0};(HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'manifest.json').write_text(json.dumps({'files':{q.name:sha(q) for q in sorted(HERE.iterdir()) if q.is_file() and q.name!='manifest.json'}},indent=2)+'\n');print('verification',sha(HERE/'verification.json'));print('manifest',sha(HERE/'manifest.json'))
 finally:signal.alarm(0)
if __name__=='__main__':run()
