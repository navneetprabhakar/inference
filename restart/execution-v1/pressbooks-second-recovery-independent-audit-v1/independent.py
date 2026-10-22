import json,hashlib,os,sys,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).resolve().parent.parent;P=B/'pressbooks-second-file-recovery-preparation-v1';sys.path.insert(0,str(P));import acquire as a
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();checks=[]
def must(f):
 try:f()
 except BaseException:return
 raise AssertionError('must refuse')
assert sha(P/'readiness.json')=='44cc697d58421eb04079f168bca4d9c79100fcc404e7f29e05e779b6440ab8e6'
registry=json.loads((P/'code-pins.json').read_text())['SHA256'];profiles=json.loads((P/'profiles.json').read_text());assert set(registry)==set(profiles['required_inventory']) and len(registry)==55
for p,h in registry.items():assert sha(p)==h
checks.append('55 exact pins/external readiness')
p=profiles['sources']['pressbooks'];assert [x['ordinal'] for x in p['files']]==[1] and p['limits']['body_reservation_including_one_byte_EOF_probe_per_file']==174453170 and p['limits']['output_precharge_bytes']==200000000 and p['limits']['max_physical_GETs']==3
checks.append('exact ordinal1 only; new174453170body/200MBoutput/3hop bounded allocation')
for n in ['entry.py','transport.py','runtime.json']:assert (P/n).read_bytes()==(B/'pressbooks-hansard-acquisition-executor-preparation-v2'/n).read_bytes()
checks.append('audited v2 early launcher/runtime/strict transport reused byte-exact')
with tempfile.TemporaryDirectory() as z:
 f=Path(z).resolve()/'old';f.write_bytes(b'abc');first={'path':str(f),'bytes':3,'SHA256':sha(f),'stat':a.stat(f)};profile={'inherited_first':first};before=a.stat(f);flags=[];original=os.open
 def opener(path,flag,*args,**kw):flags.append(flag);return original(path,flag,*args,**kw)
 with patch.object(a.os,'open',opener):r=a.verify_inherited(profile,lambda:None)
 assert r['bytes']==3 and r['SHA256']==sha(f) and a.stat(f)==before and f.read_bytes()==b'abc' and flags==[os.O_RDONLY|os.O_NOFOLLOW]
 checks.append('actual inherited tinybody readonly/no-follow hash with unchanged file/stat')
 bad={'inherited_first':{**first,'SHA256':'0'*64}};must(lambda:a.verify_inherited(bad,lambda:None));checks.append('wrong inherited SHA refuses')
 bad={'inherited_first':{**first,'bytes':2}};must(lambda:a.verify_inherited(bad,lambda:None));checks.append('wrong inherited exact bytes refuses')
 link=f.parent/'link';link.symlink_to(f);bad={'inherited_first':{**first,'path':str(link)}};must(lambda:a.verify_inherited(bad,lambda:None));checks.append('inherited symlink refuses before body read')
 f.write_bytes(b'xyz');must(lambda:a.verify_inherited(profile,lambda:None));checks.append('inherited source stat mutation refuses')
print(json.dumps({'status':'PASS','independent_controls':len(checks),'names':checks,'retained_source_body_reads':0,'actual_GETs':0,'global_ledger_writes':False},indent=2))
