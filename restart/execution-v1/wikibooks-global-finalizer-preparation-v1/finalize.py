"""Global immutable-shard reconciliation. Preparation only; no admission gate.

Input recipe is an explicit NEW internal protocol documented in README, not an
invented source schema. Real launch requires a parent-frozen recipe after source
identity reconciliation and complete rendering. Text is never rewritten here.
"""
import argparse,hashlib,json,os,pathlib,resource,shutil,sqlite3,sys,time
CAPS={'seconds':900,'output_bytes':1_000_000_000,'rss_bytes':1_000_000_000,'free_floor_bytes':20*1024**3,'weights_bytes':16_000_000_000,'processed_bytes':64_000_000_000}
TERMINAL=1_048_576
EXPECTED_CANONICAL_SHA='7ff5023543d3f69ce1963ee0b0f7e15fc60eaad6e28896aa7556251dd379a6bd'
EXPECTED_CANDIDATES=89758
BASE=pathlib.Path(__file__).resolve().parents[1]

def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def ro(p):return sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True)
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def holds_for(row,active=True):
 h=set(row.get('structural_holds',[]))|set(row.get('prior_v3_holds',[]))
 if not active:h.add('excluded_by_parent_reconciled_identity_manifest')
 return h
class Guard:
 def __init__(self,out,start):self.out=out;self.start=start
 def check(self,extra=0):
  if clk()-self.start>=CAPS['seconds']:raise RuntimeError('900_second_cap')
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
  if sys.platform!='darwin':rss*=1024
  if rss>CAPS['rss_bytes']:raise RuntimeError('observed_self_RSS_cap')
  if size(self.out)+extra>CAPS['output_bytes']-TERMINAL:raise RuntimeError('output_byte_cap')
  if shutil.disk_usage(self.out).free<CAPS['free_floor_bytes']+CAPS['weights_bytes']+extra:raise RuntimeError('disk_weights_reserve')
def receipt(out,r):
 p=out/'result.json';b=(json.dumps(r,indent=2,sort_keys=True)+'\n').encode()
 if len(b)>TERMINAL:raise RuntimeError('terminal_receipt_too_large')
 if not p.exists():
  with p.open('xb') as f:f.write(b' '*TERMINAL)
 with p.open('r+b') as f:f.write(b+b' '*(TERMINAL-len(b)));f.flush();os.fsync(f.fileno())
def schema(d):
 d.execute('pragma journal_mode=DELETE');d.execute('pragma synchronous=FULL');d.execute('pragma cache_size=-4096');d.execute('pragma temp_store=MEMORY');d.execute('pragma max_page_count=100000')
 d.executescript('''
 create table pages(source_ordinal integer primary key,page_id integer,revision_id integer,family text,title text,depth integer,text_sha256 text,characters integer,utf8_bytes integer,holds text,active integer);
 create table blocks(source_ordinal integer,ordinal integer,family text,hash text,characters integer,primary key(source_ordinal,ordinal)) without rowid;
 create index block_hash on blocks(hash);
 create index page_order on pages(depth desc,title collate binary,page_id,source_ordinal);
 create table owners(family text,hash text,source_ordinal integer,primary key(family,hash)) without rowid;
 create table exact_owners(hash text primary key,source_ordinal integer);
 create table final_pages(source_ordinal integer primary key,holds text,exact_owner integer);
 create table overlaps(source_ordinal integer,block_ordinal integer,hash text,owner_source_ordinal integer,primary key(source_ordinal,block_ordinal));
 create table exact_duplicate_groups(hash text primary key,occurrences integer,families integer);
 create table cross_family_block_groups(hash text primary key,occurrences integer,families integer);
 ''');d.commit()
def resolve(d,check=lambda extra=0:None):
 """Deterministic global ownership; held pages never acquire content ownership."""
 finalized=0
 for ordinal,family,texthash,rawholds in d.execute('select source_ordinal,family,text_sha256,holds from pages order by depth desc,title collate binary,page_id,source_ordinal'):
  check(131072);holds=set(json.loads(rawholds));overlaps=[];exact_owner=None
  if not holds:
   exact=d.execute('select source_ordinal from exact_owners where hash=?',(texthash,)).fetchone()
   if exact:exact_owner=exact[0];holds.add('exact_text_duplicate_global')
   else:
    for index,h,chars in d.execute('select ordinal,hash,characters from blocks where source_ordinal=? order by ordinal',(ordinal,)):
     if chars<80:continue
     owner=d.execute('select source_ordinal from owners where family=? and hash=?',(family,h)).fetchone()
     if owner:overlaps.append((ordinal,index,h,owner[0]))
    if overlaps:holds.add('substantive_block_duplicates_canonical_chapter')
    else:
     d.execute('insert into exact_owners values (?,?)',(texthash,ordinal))
     for h,chars in d.execute('select hash,characters from blocks where source_ordinal=?',(ordinal,)):
      if chars>=80:d.execute('insert or ignore into owners values (?,?,?)',(family,h,ordinal))
  d.executemany('insert into overlaps values (?,?,?,?)',overlaps)
  d.execute('insert into final_pages values (?,?,?)',(ordinal,json.dumps(sorted(holds)),exact_owner));finalized+=1
  if finalized%100==0:d.commit();check()
 d.execute('insert into exact_duplicate_groups select text_sha256,count(*),count(distinct family) from pages group by text_sha256 having count(*)>1')
 d.execute('insert into cross_family_block_groups select b.hash,count(*),count(distinct p.family) from blocks b join pages p on p.source_ordinal=b.source_ordinal where b.characters>=80 group by b.hash having count(distinct p.family)>1')
 d.commit();check();return finalized

def run(recipe_path,out,start=None,precreated=False):
 started=clk() if start is None else start
 if not precreated:out.mkdir(exist_ok=False)
 else:
  if any(p.name not in {'supervisor-result.json','worker.log','ownership.json'} for p in out.iterdir()):raise RuntimeError('precreated_output_not_empty')
 g=Guard(out,started);receipt(out,{'status':'RUNNING_NOT_COMPLETE_NO_ADMISSION'});d=None;pins={};stats={'rows':0,'blocks':0}
 try:
  g.check()
  if shutil.disk_usage(out).free<CAPS['free_floor_bytes']+CAPS['weights_bytes']+CAPS['output_bytes']:raise RuntimeError('preflight_output_reservation')
  intake=BASE/'m2-intake'
  if not out.resolve().is_relative_to(intake.resolve()):raise RuntimeError('output_outside_intake')
  if size(intake)+CAPS['output_bytes']>CAPS['processed_bytes']:raise RuntimeError('processed_intake_64GB')
  recipe=json.loads(recipe_path.read_text())
  if recipe.get('status')!='PARENT_FROZEN_COMPLETE_RENDER_INPUTS_NO_ADMISSION' or recipe.get('oversize_identity_reconciliation_complete') is not True:raise RuntimeError('unapproved_or_incomplete_identity_recipe')
  if recipe.get('source_frame_complete_and_hash_verified') is not True or recipe.get('expected_candidate_count')!=EXPECTED_CANDIDATES or recipe['canonical']['sha256']!=EXPECTED_CANONICAL_SHA:raise RuntimeError('complete_frozen_candidate_frame_required')
  if len(recipe['shards'])>16:raise RuntimeError('too_many_input_shards')
  for item in recipe['shards']+[recipe['canonical'],recipe['identity_reconciliation_receipt']]:
   p=pathlib.Path(item['path']).resolve()
   if sha(p)!=item['sha256']:raise RuntimeError('input_pin_mismatch')
   if str(p) in pins:raise RuntimeError('duplicate_input_path')
   pins[str(p)]=item['sha256'];g.check()
  c=ro(pathlib.Path(recipe['canonical']['path']));expected={o for o, in c.execute('select source_ordinal from candidates')};seen=set();active_seen=set()
  if len(expected)!=EXPECTED_CANDIDATES:raise RuntimeError('canonical_candidate_count_mismatch')
  os.environ['SQLITE_TMPDIR']=str(out);d=sqlite3.connect(out/'finalized.sqlite3');schema(d)
  for item in recipe['shards']:
   source=ro(pathlib.Path(item['path']));bc=iter(source.execute('select source_ordinal,ordinal,kind,hash,characters,start,end from blocks order by source_ordinal,ordinal'));b=next(bc,None)
   for ordinal,page,rev,family,payload in source.execute('select source_ordinal,page_id,revision_id,family,data from rendered order by source_ordinal'):
    g.check(16*len(payload.encode())+131072)
    if ordinal in seen:raise RuntimeError('duplicate_source_ordinal_across_shards')
    seen.add(ordinal);r=json.loads(payload);text=r['text'];active=ordinal in expected
    if active:
     e=json.loads(c.execute('select data from candidates where source_ordinal=?',(ordinal,)).fetchone()[0]);active_seen.add(ordinal)
     for k in ['page_id','revision_id','record_sha256','html_sha256','wikitext_sha256','title','url','license_original_metadata','archive_sha256','line','member_ordinal']:
      if r[k]!=e[k]:raise RuntimeError('effective_canonical_identity_changed:'+k)
     family=e['family_id'] # parent-frozen historical aliases define the common family.
    if r['training_admitted'] is not False or digest(text.encode())!=r['extracted_text_sha256'] or len(text)!=r['text_unicode_characters'] or len(text.encode())!=r['text_UTF8_bytes']:raise RuntimeError('input_text_integrity')
    holds=holds_for(r,active);d.execute('insert into pages values (?,?,?,?,?,?,?,?,?,?,?)',(ordinal,page,rev,family,r['title'],r['title'].count('/'),r['extracted_text_sha256'],len(text),len(text.encode()),json.dumps(sorted(holds)),int(active)))
    index=0;end=0
    while b is not None and b[0]==ordinal:
     _,i,kind,h,chars,start,stop=b
     if i!=index or start!=(0 if index==0 else end+2) or chars!=stop-start or stop<start or stop>len(text) or digest(text[start:stop].encode())!=h:raise RuntimeError('block_offset_or_hash_changed')
     if index and text[end:start]!='\n\n':raise RuntimeError('block_separator_changed')
     if chars>=80:d.execute('insert into blocks values (?,?,?,?,?)',(ordinal,i,None,bytes.fromhex(h),chars))
     stats['blocks']+=1;index+=1;end=stop;b=next(bc,None)
    if end!=len(text) or (b is not None and b[0]<ordinal):raise RuntimeError('block_coverage')
    stats['rows']+=1
    if stats['rows']%100==0:d.commit();g.check()
   if b is not None:raise RuntimeError('orphan_block')
   source.close()
  if active_seen!=expected:raise RuntimeError('incomplete_effective_canonical_union')
  d.commit();stats['finalized_rows']=resolve(d,g.check)
  if d.execute('pragma integrity_check').fetchone()[0]!='ok':raise RuntimeError('output_SQLite_integrity')
  stats['remaining_without_structural_or_duplicate_holds']=d.execute("select count(*) from final_pages where holds='[]'").fetchone()[0]
  stats['cross_family_block_groups']=d.execute('select count(*) from cross_family_block_groups').fetchone()[0]
  stats['exact_duplicate_groups']=d.execute('select count(*) from exact_duplicate_groups').fetchone()[0]
  d.close();d=None;c.close()
  for p,h in pins.items():
   g.check()
   if sha(pathlib.Path(p))!=h:raise RuntimeError('immutable_input_changed')
  g.check();receipt(out,{'status':'COMPLETE_GLOBAL_STRUCTURAL_RECONCILIATION_PROVISIONAL_NO_ADMISSION','stats':stats,'limits':CAPS,'elapsed_seconds':clk()-started,'input_pins':pins,'recipe_sha256':sha(recipe_path),'output_sha256':sha(out/'finalized.sqlite3'),'counts_are_not_usable_or_admitted':True,'token_counts':'not_computed; pending stable filters and pinned tokenizer','remaining_gates':['language','rights and exceptions','factual/readability filter repair and fresh representative review','cross-source leakage and dedup','family split freeze'],'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as exc:
  if d is not None:
   try:d.rollback();d.close()
   except Exception:pass
  receipt(out,{'status':'PARTIAL_GLOBAL_RECONCILIATION_NO_ADMISSION','reason':str(exc)[:2000],'stats':stats,'limits':CAPS,'elapsed_seconds':clk()-started,'new_admitted_documents':0,'new_admitted_tokens':0});raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--recipe',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--supervisor-pid',type=int,required=True);p.add_argument('--start-shared-monotonic',type=float,required=True);p.add_argument('--code-pins-sha256',required=True);p.add_argument('--recipe-sha256',required=True);a=p.parse_args()
 import code_guard
 code_guard.verify(a.code_pins_sha256)
 if sha(a.recipe)!=a.recipe_sha256:raise RuntimeError('parent_reviewed_recipe_digest_mismatch')
 if os.getppid()!=a.supervisor_pid or not 0<=clk()-a.start_shared_monotonic<CAPS['seconds']:raise RuntimeError('live_supervisor_clock_binding_required')
 run(a.recipe,a.output,a.start_shared_monotonic,True)
if __name__=='__main__':main()
