"""Finite fallback heading diagnostic contexts, no fullbook semantic claim/bodycopy."""
from pathlib import Path
import json,hashlib,os,stat,re,sys
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
rows=[json.loads(z) for z in (BASE/'m2-intake/gutenberg-20-structural-unit-discovery-v1/records.jsonl').read_text().splitlines()];profile=json.loads((BASE/'gutenberg-20-structural-unit-preparation-v1/profile.json').read_text());fallback=[(i,r) for i,r in enumerate(rows) if r['structural_discovery']['whole_envelope_fallback']];idx=int(sys.argv[1]);recordindex,r=fallback[idx];s=r['structural_discovery'];src=r['source_file'];p=Path(profile['source_output'])/src['path'];ident=lambda x:[x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns];st=p.stat(follow_symlinks=False);assert not p.is_symlink() and stat.S_ISREG(st.st_mode) and ident(st)==src['dev_ino_size_mtime_ns_ctime_ns'];fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
try:
 assert ident(os.fstat(fd))==ident(st);parts=[];hh=hashlib.sha256();n=0
 while True:
  b=os.read(fd,1048576)
  if not b:break
  n+=len(b);assert n<=2400000;hh.update(b);parts.append(b)
 assert n==src['bytes'] and hh.hexdigest()==src['SHA256'];raw=b''.join(parts);raw.decode('utf8');a,z=s['envelope']['start_byte'],s['envelope']['end_byte'];body=raw[a:z];candidates=[]
 def point(pos,kind):candidates.append((max(a,pos-170),min(z,pos+330),kind))
 point(a,'envelope_first');point(min(z,a+1200),'early_print_context');point(max(a,z-200),'envelope_terminal_boundary')
 for key in ['chapter_heading_candidates','unsupported_chapter_like_lines','structure_heading_hints']:
  hs=s[key]
  for j in sorted({0,1,len(hs)//2,max(0,len(hs)-2),len(hs)-1}):
   if hs and 0<=j<len(hs):point(hs[j]['start_byte'],key+':'+str(j))
 hs=s['chapter_heading_candidates']
 for j in [j for j in range(1,len(hs)) if hs[j]['number']!=hs[j-1]['number']+1][:6]:point(hs[j]['start_byte'],'number_reset_or_gap:'+str(j))
 patterns={'bare_Roman_or_Arabic':rb'(?m)^[ \t]*(?:[IVXLCDM]{1,12}|[0-9]{1,3})[.)]?[ \t]*\r?$', 'spelled_or_part_heading':rb'(?mi)^[ \t]*(?:(?:CHAPTER|BOOK|PART|VOLUME)[ \t]+(?:[A-Z0-9-]+)(?:[ .:-]+[^\r\n]{0,100})?)[ \t]*\r?$','spaced_roman_heading':rb'(?m)^[ \t]*[IVXLCDM]{1,12}\.[ \t]+[^\r\n]{1,100}\r?$'}
 inventories={}
 for kind,pat in patterns.items():
  hits=list(re.finditer(pat,body));assert len(hits)<=4096;inventories[kind]={'count':len(hits),'sample_lines':[]}
  for j in sorted({0,1,len(hits)//2,max(0,len(hits)-2),len(hits)-1}):
   if hits and 0<=j<len(hits):
    m=hits[j];point(a+m.start(),kind+':'+str(j));inventories[kind]['sample_lines'].append({'start_byte':a+m.start(),'line':m.group().decode('utf8'),'SHA256':hashlib.sha256(m.group()).hexdigest()})
 # Merge overlap without losing any requested label, then bounded wholecontexts only.
 merged=[]
 for lo,hi,kind in sorted(candidates):
  if merged and lo<=merged[-1][1]:merged[-1][1]=max(hi,merged[-1][1]);merged[-1][2].append(kind)
  else:merged.append([lo,hi,[kind]])
 assert sum(hi-lo for lo,hi,_ in merged)<=12000
 prior=[json.loads(x) for x in (HERE/'progress.jsonl').read_text().splitlines()] if (HERE/'progress.jsonl').exists() else [];assert idx not in {x['fallback_index'] for x in prior};total=sum(x['displayed_context_bytes'] for x in prior)+sum(hi-lo for lo,hi,_ in merged);assert total<=200000
 info={'fallback_index':idx,'record_index':recordindex,'ebook_ID':r['ebook_ID'],'source_file':src,'source_raw_hash_FD_verified':True,'old_holds':s['chapter_sequence_holds'],'canonical_sequence':[h['number'] for h in hs],'inventories':inventories,'displayed_context_bytes':sum(hi-lo for lo,hi,_ in merged),'contexts':[]}
 for lo,hi,kinds in merged:info['contexts'].append({'byte_span':[lo,hi],'SHA256':hashlib.sha256(raw[lo:hi]).hexdigest(),'roles':kinds})
 print(json.dumps(info,ensure_ascii=False,indent=2))
 for lo,hi,kinds in merged:print('\nCONTEXT',lo,hi,kinds,'\n'+raw[lo:hi].decode('utf8','replace'))
 assert ident(os.fstat(fd))==ident(st)==ident(p.stat(follow_symlinks=False))
 with (HERE/'progress.jsonl').open('a') as f:f.write(json.dumps(info,ensure_ascii=False)+'\n')
finally:os.close(fd)
