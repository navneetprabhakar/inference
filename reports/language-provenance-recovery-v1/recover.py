"""Restore only historical exact-hash TinyStories raw parents. No data admission."""
import hashlib,json,pathlib,resource,shutil,signal,tarfile,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
REV='f54c09fd23315a6f9c86f9dc80f725de7d8f9c64';EXPECTED='26cf7605aca15bc4ea6fa637256400d9d01317b28ed296172b2d1dd160cd7699';SIZE=1608001638
URL=f'https://huggingface.co/datasets/roneneldan/TinyStories/resolve/{REV}/TinyStories_all_data.tar.gz'
MAX_BYTES=4*1024**3;SECONDS=1200;START=time.monotonic();written=0
manifest=ROOT/'data/language-mixture-v1/partial-candidate-manifest.json';m=json.loads(manifest.read_text());members=[x for x in m['source_files'] if x['source']=='stories'];parent=ROOT/'data/language-source-recovery-v1/TinyStories_all_data';archive=parent.with_suffix('.tar.gz')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def check():
 if any(p.exists() for p in [ROOT/'runs/STOP',ROOT/'data/language-mixture-v1/STOP',HERE/'STOP']):raise RuntimeError('STOP')
 if time.monotonic()-START>SECONDS or written>MAX_BYTES:raise RuntimeError('recovery ceiling')
 if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('disk floor')
def alarm(*args):raise TimeoutError('hard recovery wall cap')
signal.signal(signal.SIGALRM,alarm);signal.alarm(SECONDS)
originals=[manifest,ROOT/'data/language-mixture-v1/candidates.sqlite',ROOT/'data/language-mixture-v1/candidate-verification.json',ROOT/'data/language-mixture-v1/custody.json'];pins={str(p):sha(p) for p in originals}
plan={'state':'frozen_exact_identity_recovery','url':URL,'revision':REV,'archive_sha256':EXPECTED,'archive_bytes':SIZE,'archive_destination':str(archive),'members':members,'limits':{'total_new_bytes':MAX_BYTES,'seconds':SECONDS,'disk_floor_bytes':20*1024**3},'preserve':pins,'code_sha256':sha(pathlib.Path(__file__))}
with (HERE/'plan.json').open('x') as f:json.dump(plan,f,indent=2)
result={'state':'incomplete_not_admitted','restored':[]};failure=None
try:
 check();assert not archive.exists() and all(not (parent/pathlib.Path(x['path']).name).exists() for x in members),'never overwrite existing raw files'
 assert shutil.disk_usage(ROOT).free>=20*1024**3+SIZE+sum(x['bytes'] for x in members),'forecast disk floor'
 archive.parent.mkdir(parents=True,exist_ok=True);partial=archive.with_suffix(archive.suffix+'.recovery-partial');h=hashlib.sha256();received=0
 request=urllib.request.Request(URL,headers={'User-Agent':'local-exact-provenance-recovery/1.0'})
 with urllib.request.urlopen(request,timeout=30) as source,partial.open('xb') as out:
  header=source.headers.get('Content-Length')
  if header is not None:assert int(header)==SIZE,'unexpected content length'
  while True:
   check();chunk=source.read(1024**2)
   if not chunk:break
   received+=len(chunk);written+=len(chunk);assert received<=SIZE,'archive size cap';out.write(chunk);h.update(chunk)
 assert received==SIZE and h.hexdigest()==EXPECTED,'archive identity mismatch'
 check();partial.rename(archive);parent.mkdir(exist_ok=True)
 byname={pathlib.Path(x['path']).name:x for x in members};seen=set()
 with tarfile.open(archive,mode='r|gz') as tar:
  for member in tar:
   check();name=pathlib.Path(member.name).name
   if name not in byname:continue
   entry=byname[name];assert name not in seen and member.isfile() and member.size==entry['bytes'],'member shape'
   target=parent/name;temp=target.with_suffix('.json.recovery-partial');n=0;h=hashlib.sha256()
   with tar.extractfile(member) as source,temp.open('xb') as out:
    while True:
     check();chunk=source.read(1024**2)
     if not chunk:break
     n+=len(chunk);written+=len(chunk);assert n<=entry['bytes'];out.write(chunk);h.update(chunk)
   assert n==entry['bytes'] and h.hexdigest()==entry['sha256'],'member identity'
   check();temp.rename(target);seen.add(name);result['restored'].append(dict(original_path=entry['path'],recovered_path=str(target),bytes=n,sha256=h.hexdigest()))
   if len(seen)==len(byname):break
 assert len(seen)==4 and all(sha(pathlib.Path(p))==h for p,h in pins.items()),'incomplete recovery or changed original artifacts'
 result.update(state='PASS_exact_raw_provenance_restored_not_admitted',archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,candidate_database_unchanged=True,training_admitted=False)
except BaseException as e:
 failure=e;result.update(state='FAIL_incomplete_provenance_recovery_not_admitted',error=type(e).__name__+': '+str(e))
finally:
 signal.alarm(0);result.update(seconds=time.monotonic()-START,total_written_bytes=written,plan_sha256=sha(HERE/'plan.json'),code_sha256=sha(pathlib.Path(__file__)))
 with (HERE/'receipt.json').open('x') as f:json.dump(result,f,indent=2)
 print(json.dumps(result),flush=True)
if failure:raise failure
