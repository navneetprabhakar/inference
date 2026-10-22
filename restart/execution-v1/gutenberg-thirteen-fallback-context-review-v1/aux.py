from pathlib import Path
import json,os,hashlib,stat,re
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;rows=[json.loads(x) for x in (BASE/'m2-intake/gutenberg-20-structural-unit-discovery-v1/records.jsonl').read_text().splitlines()];prof=json.loads((BASE/'gutenberg-20-structural-unit-preparation-v1/profile.json').read_text());out=[]
for eid,mode in [(38871,'tail'),(17086,'end'),(34000,'volumes'),(2164,'prefix')]:
 r=next(x for x in rows if x['ebook_ID']==eid);src=r['source_file'];p=Path(prof['source_output'])/src['path'];identity=lambda z:[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns];s=p.stat(follow_symlinks=False);assert not p.is_symlink() and stat.S_ISREG(s.st_mode) and identity(s)==src['dev_ino_size_mtime_ns_ctime_ns'];fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  assert identity(os.fstat(fd))==identity(s);a=r['structural_discovery']['envelope']['start_byte'];z=r['structural_discovery']['envelope']['end_byte']
  if mode=='tail':spans=[(z-700,z)]
  elif mode=='end':h=r['structural_discovery']['literal_ending_hints'][0];spans=[(h['start_byte']-250,h['end_byte']+900)]
  elif mode=='prefix':spans=[(a,a+3200)]
  else:
   os.lseek(fd,0,0);raw=os.read(fd,s.st_size);assert hashlib.sha256(raw).hexdigest()==src['SHA256'];spans=[(m.start()-120,m.end()+180) for m in re.finditer(rb'(?mi)^VOL\.[ \t]+[IVXLCDM]+\.',raw)];assert len(spans)==2
  for lo,hi in spans:
   os.lseek(fd,lo,0);raw=os.read(fd,hi-lo);x={'ebook_ID':eid,'mode':mode,'source_SHA256':src['SHA256'],'byte_span':[lo,hi],'SHA256':hashlib.sha256(raw).hexdigest()};out.append(x);print(json.dumps(x));print(raw.decode('utf8','replace'))
  assert identity(os.fstat(fd))==identity(s)==identity(p.stat(follow_symlinks=False))
 finally:os.close(fd)
prior=sum(json.loads(x)['displayed_context_bytes'] for x in (HERE/'progress.jsonl').read_text().splitlines());assert prior+sum(x['byte_span'][1]-x['byte_span'][0] for x in out)<=200000
(HERE/'aux-contexts.json').write_text(json.dumps({'contexts':out,'displayed_bytes':sum(x['byte_span'][1]-x['byte_span'][0] for x in out),'total_displayed_context_bytes':prior+sum(x['byte_span'][1]-x['byte_span'][0] for x in out)},indent=2)+'\n')
