"""Bounded first-complete-frame metadata-only URL/family/version diagnosis."""
import time
START=time.clock_gettime(time.CLOCK_MONOTONIC)
import collections,hashlib,ipaddress,json,os,re,signal,sqlite3,stat,sys,unicodedata
from pathlib import Path
from urllib.parse import urlsplit,unquote
HERE=Path(__file__).resolve().parent
SECTIONS={'chapter','front-matter','back-matter','part'}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def deadline(*a):raise TimeoutError('30sec_metadata_only_bound')
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def public(value):
 if type(value) is not str or len(value)>4096 or any(c.isspace() or unicodedata.category(c) in {'Cc','Cf'} for c in value) or '\\' in value:raise ValueError('URL_chars_or_bound')
 u=urlsplit(value)
 if u.scheme not in {'https','http'} or not u.hostname or u.username or u.password or u.port not in (None,443 if u.scheme=='https' else 80):raise ValueError('URL_scheme_host_credentials_port')
 try:ip=ipaddress.ip_address(u.hostname)
 except ValueError:
  if not re.fullmatch(r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',u.hostname) or u.hostname.endswith(('.localhost','.local','.internal')):raise ValueError('not_public_hostname_syntax')
 else:
  if not ip.is_global:raise ValueError('not_public_IP')
 segments=[x for x in u.path.split('/') if x]
 if any(unquote(s) in {'.','..'} or '/' in unquote(s) or '\\' in unquote(s) for s in segments):raise ValueError('ambiguous_encoded_path_segment')
 return u,segments

def lead(book,url):
 try:b,bs=public(book);u,us=public(url)
 except (ValueError,TypeError):return {'kind':'INVALID_OR_AMBIGUOUS_PUBLIC_URL','root':None,'pattern':'invalid_public_URL'}
 origin=(b.scheme,b.hostname,b.port or (443 if b.scheme=='https' else 80))
 other=(u.scheme,u.hostname,u.port or (443 if u.scheme=='https' else 80))
 if origin!=other:return {'kind':'ORIGIN_MISMATCH_NEEDS_ALIAS_EVIDENCE','root':None,'pattern':'different_origin'}
 bi=next((i for i,s in enumerate(bs) if s in SECTIONS),None);ui=next((i for i,s in enumerate(us) if s in SECTIONS),None)
 pattern=f'book_section_at_{bi};page_section_at_{ui};bookdepth_{len(bs)};pagedepth_{len(us)}'
 uncertainties=['Structural metadata lead only; source engine/domain ownership, complete book, aliases and cross-source ancestry not verified.']
 if b.query or u.query or b.fragment or u.fragment:uncertainties.append('Query/fragment preserved raw; only path used for proposed lead, not equivalence proof.')
 if bi is not None and ui is not None and bs[:bi]==us[:ui]:
  prefix=bs[:bi];kind='SHARED_LITERAL_PREFIX_BEFORE_BOOK_SECTION' if prefix else 'HOST_ONLY_SECTION_PATTERN_UNVERIFIED_BOOK'
 elif bi is None and ui is not None and bs==us[:ui]:prefix=bs;kind='EXPLICIT_BOOK_PATH_PLUS_SECTION_PATH' if prefix else 'HOST_ONLY_HOME_AND_SECTION_UNVERIFIED_BOOK'
 else:return {'kind':'NO_UNAMBIGUOUS_SHARED_BOOK_PREFIX','root':None,'pattern':pattern}
 root=b.scheme+'://'+b.netloc+'/'+('/'.join(prefix)+'/' if prefix else '')
 return {'kind':kind,'root':root,'pattern':pattern,'uncertainty':uncertainties}

def old_without_hostname(book,url):
 try:
  b=urlsplit(book);u=urlsplit(url)
  if b.scheme not in ('http','https') or b.username or b.password or not b.hostname or b.hostname!=u.hostname or not u.hostname:return None
  parts=b.path.split('/');slug=parts[1] if len(parts)>1 else ''
  if not slug or slug in SECTIONS or len(slug)>512:return None
  if len(parts)>2 and parts[2] not in ('',*SECTIONS):return None
  if not u.path.startswith('/'+slug+'/') and u.path!='/'+slug:return None
  return b.scheme+'://'+b.hostname+'/'+slug+'/'
 except (ValueError,TypeError):return None

def checks():
 a='https://opentextbc.ca/book/front-matter/about/';b='https://opentextbc.ca/book/chapter/c/'
 assert lead(a,b)['root']=='https://opentextbc.ca/book/' and old_without_hostname(a,b) is not None
 assert lead('https://host.example/','https://host.example/chapter/c/')['kind']=='HOST_ONLY_HOME_AND_SECTION_UNVERIFIED_BOOK'
 for u in ['http://127.0.0.1/a','https://localhost/a','https://u:p@host.example/a','https://host.example/a%2fb/chapter/c','https://host.example/a\u200b']:
  try:public(u)
  except ValueError:pass
  else:raise AssertionError(u)
 assert lead(a,'https://different.example/book/chapter/c/')['root'] is None
 return {'status':'PASS_SYNTHETIC_ONLY','controls':8}

def main():
 if '--checks' in sys.argv:print(json.dumps(checks()));return
 signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,max(.001,30-(clk()-START)))
 p=json.loads((HERE/'profile.json').read_text());source=Path(p['frame']['path']);expected=p['frame']['stat'];fd=None;db=None
 def custody():
  if source.is_symlink() or str(source.resolve())!=str(source) or ident(source.stat())!=expected or (fd is not None and ident(os.fstat(fd))!=expected):raise ValueError('completed_frame_stat_custody')
 custody();fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('regular_frame_required')
  custody();db=sqlite3.connect(source.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA mmap_size=0');db.execute('PRAGMA temp_store=MEMORY');db.set_progress_handler(lambda:0 if clk()-START<30 else 1,10000)
  kinds=collections.Counter();hosts=collections.Counter();patterns=collections.Counter();samples={};only_host=0;bytes_total=0;unresolved=0
  for ordinal,id,url,book,created,added,textsha,textbytes,flags in db.execute('SELECT ordinal,id,url,book_url,created,added,text_SHA256,text_UTF8_bytes,flags FROM records WHERE (flags&64)!=0 ORDER BY ordinal'):
   unresolved+=1;bytes_total+=textbytes or 0;result=lead(book,url);kinds[result['kind']]+=1
   try:host=urlsplit(book or '').hostname or '<missing>'
   except ValueError:host='<malformed>'
   hosts[host]+=1;key=(host,result['pattern'],result['kind']);patterns[key]+=1
   if old_without_hostname(book,url) is not None and 'pressbooks' not in host:only_host+=1
   group=samples.setdefault(key,[])
   if len(group)<2:group.append({'ordinal':ordinal,'id':id,'url':url,'book_url':book,'created':created,'added':added,'text_SHA256':textsha.hex() if textsha else None,'text_UTF8_bytes':textbytes,'existing_flags':flags,'proposed_structural_lead':result})
  duplicate_counts=db.execute('SELECT count(*),sum(n) FROM (SELECT count(*)n FROM records WHERE id IS NOT NULL GROUP BY id HAVING count(*)>1)').fetchone()
  conflicting=db.execute('SELECT id,count(*),count(DISTINCT text_SHA256) FROM records WHERE id IS NOT NULL GROUP BY id HAVING count(DISTINCT text_SHA256)>1 ORDER BY id').fetchall();conflicts=[]
  for id,n,versions in conflicting:
   rows=db.execute('SELECT ordinal,line_offset,line_bytes,line_SHA256,id,source,added,created,license,url,book_url,title,author,institution,subject,text_SHA256,text_UTF8_bytes,text_chars,derived_book_root,flags FROM records WHERE id=? ORDER BY ordinal',(id,)).fetchall();keys=['ordinal','line_offset','line_bytes','line_SHA256','id','source','added','created','license','url','book_url','title','author','institution','subject','text_SHA256','text_UTF8_bytes','text_chars','derived_book_root','flags'];variants=[{k:(v.hex() if isinstance(v,bytes) else v) for k,v in zip(keys,row)} for row in rows]
   conflicts.append({'id':id,'occurrences':n,'distinct_text_SHA256':versions,'variants':variants,'disposition':'Retain every occurrence. created/added are captured metadata, not authoritative revision chronology; no canonical selection or evidence of corruption from differing textSHA alone.','shared_metadata_fields':[k for k in ['created','license','book_url','title','author','institution','subject'] if len({r[k] for r in variants})==1],'varying_metadata_fields':[k for k in ['added','created','license','book_url','title','author','institution','subject','text_UTF8_bytes'] if len({r[k] for r in variants})>1]})
  custody();result={'status':'COMPLETE_FIRST_FRAME_METADATA_DIAGNOSIS_NO_FAMILY_CLEARANCE','rows_examined_unresolved':unresolved,'unresolved_text_UTF8_bytes':bytes_total,'rows_old_other_checks_pass_and_only_hostname_substring_rejects':only_host,'proposed_structural_lead_categories':dict(kinds),'top_unresolved_book_hosts':hosts.most_common(50),'top_patterns_with_exact_raw_pairs':[{'host':k[0],'pattern':k[1],'kind':k[2],'rows':n,'first2_ordinal_metadata_examples_not_sample':samples[k]} for k,n in patterns.most_common(50)],'all_duplicate_ID_groups_and_occurrences':duplicate_counts,'conflicting_duplicate_ID_group_count':len(conflicts),'conflicting_groups':conflicts,'proposal':['Remove hostname brand-substring requirement only in a new derived-family-lead view, not in frozen frames; use strict public URL syntax and same-origin literal prefix before explicit book-section paths. Preserve exact raw pairs and all source occurrences.','Nonempty shared bookslug prefixes are structural candidate leads on custom domains, not certified PressBooks ownership or complete books. Host-only roots remain explicitly uncertain; mismatched origins/ambiguous paths need evidence, no guessed family merges.','Full two-shard union must reconcile duplicate IDs/texts, raw dates/version ambiguity, aliases/adaptations, held-ID/textSHA propagation and cross-source ancestry before split/admission; no metadata license URL clearance.'],'family_assignments_modified':False,'source_body_or_live_second_frame_read':False,'new_admitted_documents':0,'elapsed_seconds':clk()-START}
  raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode();assert len(raw)<=4000000
  if (HERE/'result.json').exists():raise ValueError('once_only_result')
  (HERE/'result.json').write_bytes(raw);print(json.dumps({'status':result['status'],'rows':unresolved,'hostname_only':only_host,'categories':dict(kinds),'duplicate_counts':duplicate_counts,'conflicts':len(conflicts),'output_bytes':len(raw),'elapsed_seconds':clk()-START}))
 finally:
  if db is not None:db.close()
  if fd is not None:os.close(fd)
  signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()
