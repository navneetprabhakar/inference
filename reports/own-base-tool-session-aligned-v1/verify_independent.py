"""Fresh stream reload with independent current-turn mask construction."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import array,collections,hashlib,json,pathlib,sqlite3,sys,time
import build as b
from dialogue import _frames,HEADERS
from tokenizer import load
os.nice(10);D=b.D;f=b.read(D/'freeze.json');start=f['started'];b.check(start);b.verify_inputs(f);receipt=b.read(D/'receipt.json');assert receipt['freeze_sha256']==b.sha(D/'freeze.json')
for name,pin in receipt['outputs'].items():assert b.sha(D/name)==pin['sha256'] and (D/name).stat().st_size==pin['bytes']
tok=load();con=b.conn();ex=b.excluded();seen=set();families={};counts=collections.defaultdict(collections.Counter);positions=collections.Counter();totalrows=0

def decode(raw):
 a=array.array('H');a.frombytes(raw)
 if sys.byteorder!='little':a.byteswap()
 return list(a)
for split in ('train','exposed-development'):
 offset=0;previous=None;adapted=None;turn=0
 with (D/f'{split}.inputs.u16').open('rb') as inp,(D/f'{split}.labels.u16').open('rb') as lab,(D/f'{split}.index.jsonl').open() as index:
  for line in index:
   if totalrows%20==0:b.check(start)
   item=json.loads(line);did=item['doc_id'];assert did not in ex and item['split']==split and item['source']=='own-base-tool-session-extension'
   if previous!=did:
    if previous is not None:assert turn==len(adapted)
    assert did not in seen;seen.add(did);d=con.execute('select * from documents where doc_id=?',(did,)).fetchone();assert d is not None and d['split']==split;assert families.setdefault(d['family'],split)==split;adapted=json.loads(d['adapted_json']);original=json.loads(d['original_lesson_json']);assert hashlib.sha256(b.canon(original).encode()).hexdigest()==did;turn=0;previous=did;counts[split]['histories']+=1
   assert item['turn']==turn and item['family']==d['family'] and item['original_lesson_sha256']==did and item['original_history_sha256']==hashlib.sha256(b.canon(original['history']).encode()).hexdigest()
   h=adapted[turn]['history'];ids,target,expected=_frames(tok,h);assert expected=='user' and len(ids)-1<=1024
   last=max(i for i,x in enumerate(h) if x['role']=='user');old,_,_=_frames(tok,h[:last]);labels=[token if flag and position>=len(old) else 65535 for position,(token,flag) in enumerate(zip(ids[1:],target[1:]),1)]
   for j,msg in enumerate(h):
    if msg['role']!='assistant':continue
    prefix,_,expect=_frames(tok,h[:j]);assert expect=='assistant';prefix+=tok.encode(HEADERS['assistant']).ids;complete,_,_=_frames(tok,h[:j+1]);assert complete[:len(prefix)]==prefix and 0<len(complete)-len(prefix)<=256 and len(prefix)+256<=1024
   assert item['offset']==offset and item['length']==len(ids)-1
   n=item['length'];inputs=decode(inp.read(2*n));stored=decode(lab.read(2*n));assert inputs==ids[:-1] and stored==labels;assert all(0<=x<=50256 for x in inputs);assert all(x==65535 or 0<=x<=50256 for x in stored)
   pos=collections.Counter()
   for i,x in enumerate(stored):
    if x!=65535:lo=((i+1)//256)*256;pos[f'{lo}..{lo+255}']+=1
   assert dict(pos)==item['position_exposure'] and sum(pos.values())==item['target_count'];positions.update(pos);counts[split]['targets']+=item['target_count'];counts[split]['rows']+=1;offset+=n;turn+=1;totalrows+=1
  if previous is not None:assert turn==len(adapted)
  assert inp.read()==b'' and lab.read()==b'' and offset==receipt['stream_tokens'][split]
refused=[json.loads(l) for l in open(D/'refused.jsonl')];assert not refused,'Any refusal needs separately inspected complete-lesson fit diagnosis'
eligible={d[0] for d in con.execute('select doc_id from documents') if d[0] not in ex};assert seen==eligible
for split,c in counts.items():
 rc=receipt['counts']['own-base-tool-session-extension:'+split];assert c['histories']==rc['accepted_histories'] and c['rows']==rc['rows'] and c['targets']==rc['aligned_targets']
assert counts['train']['histories']==29 and counts['train']['targets']==6073 and counts['exposed-development']['histories']==8 and counts['exposed-development']['targets']==1678;assert dict(positions)==receipt['position_exposure'];b.verify_inputs(f);b.check(start)
out=dict(state='PASS_independent_stream_reload_diagnostic_only',training_admitted=False,receipt_sha256=b.sha(D/'receipt.json'),counts=dict(counts),position_exposure=dict(positions),refused_lessons=0,exclusion_absence=True,family_disjoint=True,mask_method='Independent shifted labels from dialogue._frames and raw-token current-user boundary, not last_turn_row',seconds_since_freeze=time.time()-start);b.write(D/'independent-verification.json',out);print(json.dumps(out))
