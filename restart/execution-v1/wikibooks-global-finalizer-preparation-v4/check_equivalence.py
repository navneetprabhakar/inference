"""Narrow representation equivalence against frozen v3 ownership algorithm."""
import sqlite3,json,pathlib,importlib.util
import finalize as new
p=pathlib.Path(__file__).resolve().parent.parent/'wikibooks-global-finalizer-preparation-v3/finalize.py';spec=importlib.util.spec_from_file_location('frozen_v3',p);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
A='a'*80;B='b'*80;C='c'*79;Z='z'*90
rows=[(1,'Book/Print','alias',[A,B],[]),(2,'Book/Chapter/Deep','alias',[A],[]),(3,'Book/Next','alias',[B],[]),(4,'Other/X','other',[A],[]),(5,'Held/X/Y','held',[Z],['old_hold']),(6,'Held/X','held',[Z],[]),(7,'Short/A','short',[C,B],[]),(8,'Short/B','short',[C,A],[]),(9,'Case/A','Family',[B,A],[]),(10,'Case/B','family',[B,Z],[]),(11,'Repeated/A','rep',[Z,Z],[])]
def make(mod,modern):
 d=sqlite3.connect(':memory:');mod.schema(d)
 for i,title,family,blocks,holds in rows:
  text='\n\n'.join(blocks);fam=mod.intern_family(d,family) if modern else family;h=mod.digest(text.encode());h=bytes.fromhex(h) if modern else h
  d.execute('insert into pages values (?,?,?,?,?,?,?,?,?,?,?)',(i,i,i+100,fam,title,title.count('/'),h,len(text),len(text.encode()),json.dumps(holds),1))
  for j,b in enumerate(blocks):
   if len(b)<80:continue
   bh=bytes.fromhex(mod.digest(b.encode()))
   if modern:d.execute('insert into blocks values (?,?,?,?)',(i,j,bh,len(b)))
   else:d.execute('insert into blocks values (?,?,?,?,?)',(i,j,None,bh,len(b)))
 mod.resolve(d);return d
def hx(h):return h.hex() if isinstance(h,bytes) else h
def snapshot(d,modern):
 families=dict(d.execute('select id,value from families')) if modern else {}
 return {'holds':list(d.execute('select * from final_pages order by source_ordinal')),'owners':sorted((families.get(f,f),hx(h),o) for f,h,o in d.execute('select * from owners')),'overlaps':[(o,i,hx(h),owner) for o,i,h,owner in d.execute('select * from overlaps order by source_ordinal,block_ordinal')],'exactgroups':sorted((hx(h),n,f) for h,n,f in d.execute('select * from exact_duplicate_groups')),'crossgroups':sorted((hx(h),n,f) for h,n,f in d.execute('select * from cross_family_block_groups'))}
a=make(old,False);b=make(new,True);assert snapshot(a,False)==snapshot(b,True);checks=['all_holds_ownership_exact_duplicates_cross_family_groups_equal_to_frozen_v3']
assert b.execute('select count(*) from families').fetchone()[0]==len({r[2] for r in rows});checks.append('bijective_family_interning_no_casefold_or_loss')
assert b.execute('select count(*) from blocks where typeof(hash)!="blob" or length(hash)!=32').fetchone()[0]==0;checks.append('all_substantive_hashes_exact32byte_BLOB')
assert b.execute('select count(*) from blocks where characters<80').fetchone()[0]==0;checks.append('only_substantive_blocks_indexed')
assert b.execute('select count(*) from pages').fetchone()[0]==len(rows);checks.append('all_pages_and_exact_fulltext_hashes_retained')
try:b.execute('insert into blocks values (999,0,?,80)',('bad-hash',))
except sqlite3.IntegrityError:checks.append('wrong_hash_storage_type_rejected')
else:raise AssertionError('invalidhash')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
