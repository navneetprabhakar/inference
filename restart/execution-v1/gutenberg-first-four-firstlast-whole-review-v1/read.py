"""Source-bound whole-unit visible chunks; write metadata evidence only, no bodycopy."""
from pathlib import Path
import json,hashlib,os,stat,sys
HERE=Path(__file__).resolve().parent
sha=lambda x:hashlib.sha256(x).hexdigest()
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
plan=json.loads((HERE/'selection.json').read_text());u=plan['units'][int(sys.argv[1])];entry=u['source_file'];p=Path(plan['source_root'])/entry['path'];s=p.stat(follow_symlinks=False);assert stat.S_ISREG(s.st_mode) and not p.is_symlink() and ident(s)==entry['dev_ino_size_mtime_ns_ctime_ns'];fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
try:
 assert ident(os.fstat(fd))==ident(s);os.lseek(fd,u['start_byte'],os.SEEK_SET);raw=os.read(fd,u['bytes']);assert len(raw)==u['bytes'] and sha(raw)==u['SHA256'];text=raw.decode('utf8','strict');k=int(sys.argv[2]);a=k*9000;b=min(len(text),a+9000);assert 0<=a<b
 emit={'unit_index':int(sys.argv[1]),'unit_ID':u['unit_ID'],'chapter_number':u['chapter_number'],'chunk':k,'characters':[a,b],'UTF8_relative':[len(text[:a].encode()),len(text[:b].encode())],'absolute_source_UTF8':[u['start_byte']+len(text[:a].encode()),u['start_byte']+len(text[:b].encode())],'SHA256':sha(text[a:b].encode()),'whole_unit_characters':len(text),'whole_unit_bytes':len(raw),'source_raw_SHA256':entry['SHA256']}
 if k==0:
  contexts=[]
  for boundary in [u['start_byte'],u['end_byte']]:
   lo=max(0,boundary-768);hi=min(s.st_size,boundary+768);os.lseek(fd,lo,os.SEEK_SET);context=os.read(fd,hi-lo);scontext=context.decode('utf8','replace');contexts.append({'raw_byte_span':[lo,hi],'SHA256':sha(context),'text_display_UTF8_replacement_if_boundary_splits_codepoint':scontext})
  emit['boundary_contexts']=contexts
 assert ident(os.fstat(fd))==ident(s)==ident(p.stat(follow_symlinks=False));print(json.dumps(emit,ensure_ascii=False,indent=2));print(text[a:b])
 evidence={k:v for k,v in emit.items() if k!='boundary_contexts'}
 if 'boundary_contexts' in emit:evidence['boundary_contexts']=[{k:v for k,v in c.items() if k!='text_display_UTF8_replacement_if_boundary_splits_codepoint'} for c in emit['boundary_contexts']]
 with (HERE/'read-progress.jsonl').open('a') as f:f.write(json.dumps(evidence)+'\n')
finally:os.close(fd)
