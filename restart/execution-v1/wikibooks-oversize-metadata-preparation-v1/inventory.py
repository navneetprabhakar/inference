"""Narrow 29-record metadata supplement using the frozen streaming tar reader."""
import argparse,hashlib,importlib.util,json,os,re,sqlite3,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;E=HERE.parent;UP=E/'wikibooks-identity-frame-preparation-v1';sys.path.insert(0,str(UP))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
u=load('frozen_identity_reader',UP/'inventory.py');c=load('frozen_canonical_rules',E/'wikibooks-canonical-preparation-v1/canonical.py')
from shared_clock import shared_clock
CAPS=dict(u.CAPS,decoded_bytes=6_000_000_000,output_bytes=10_000_000,seconds=180,parsed_record_bytes=32_000_000,rss_hard_bytes=1_000_000_000)
FREE_RESERVE=20*1024**3+32_000_000_000;TERMINAL_RESERVE=u.TERMINAL_RESERVE;INTAKE_ROOT=u.INTAKE_ROOT;PROCESSED_CEILING=u.PROCESSED_CEILING;output_size=u.output_size;terminal_write=u.terminal_write;check_processed_reservation=u.check_processed_reservation
FRAME=INTAKE_ROOT/'wikibooks-complete-identity-frame-v1/inventory.sqlite3';CANON=INTAKE_ROOT/'wikibooks-canonical-candidates-v1/canonical.sqlite3';PIN_PATH=HERE/'code-pins.json';ARCHIVE_SHA256=u.ARCHIVE_SHA256
file_sha=u.file_sha
REQUIRED={str(p.resolve()) for p in [HERE/'inventory.py',HERE/'supervisor.py',HERE/'check_offline.py',HERE/'policy.json',HERE/'shared_clock.py',UP/'inventory.py',UP/'supervisor.py',UP/'shared_clock.py',E/'wikibooks-canonical-preparation-v1/canonical.py',FRAME,CANON]}
def check_pins():
 expected=os.environ.get('WIKIBOOKS_SUPPLEMENT_PINS_SHA256','');assert re.fullmatch('[0-9a-f]{64}',expected) and file_sha(PIN_PATH)==expected
 p=json.loads(PIN_PATH.read_text());assert set(p['sha256'])==REQUIRED
 for name,h in p['sha256'].items():assert file_sha(Path(name))==h,name
 assert p['sha256'][str(FRAME)]=='a27a5c6f2fe085e19968bde850fd45ace824e141be45e595037c6278ae5bd1f3'
 return p
def reconcile(loc,old):
 for k in ['member','member_ordinal','line','member_uncompressed_byte_offset','record_bytes','record_sha256']:assert loc[k]==old[k],k

def write(output,name,value,guards):
 b=(json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode();guards.check(len(b))
 with (output/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def build(archive,output,start):
 limits=dict(CAPS,seconds=170);g=u.Guards(output,start,limits,FREE_RESERVE);stats={'members':[],'encountered_records':0,'parsed_source_records':0,'record_bytes':0,'tar_end_blocks_verified':False,'gzip_eof_crc_verified':False};db=None
 try:
  check_pins();check_processed_reservation(output,CAPS['output_bytes']);assert file_sha(archive)==ARCHIVE_SHA256;g.check()
  source=sqlite3.connect(FRAME.as_uri()+'?mode=ro',uri=True);canon=sqlite3.connect(CANON.as_uri()+'?mode=ro',uri=True);source.row_factory=sqlite3.Row;canon.row_factory=sqlite3.Row
  targets={r['ordinal']:json.loads(r['data']) for r in source.execute('select ordinal,data from records where page_id is null')};assert len(targets)==29 and sum(x['record_bytes'] for x in targets.values())==202851696 and max(x['record_bytes'] for x in targets.values())==15850709
  assert all(x['identity_holds']==['oversize_record_not_parsed'] for x in targets.values());rows=[];original=source.execute('select ordinal,data from records order by ordinal');records=iter(original)
  for loc in u.tar_records(archive,g,stats):
   g.check();old=next(records);prior=json.loads(old['data']);reconcile(loc,prior);stats['encountered_records']+=1;stats['record_bytes']+=loc['record_bytes'];assert old['ordinal']==stats['encountered_records']
   if old['ordinal'] in targets:
    assert loc['raw'] is not None;row=u.identity(loc['raw'],loc,ARCHIVE_SHA256);assert row['page_id'] is not None and row['revision_id'] is not None;row.update(source_ordinal=old['ordinal'],source_frame_sha256='a27a5c6f2fe085e19968bde850fd45ace824e141be45e595037c6278ae5bd1f3',original_frame_holds=prior['identity_holds'],render_holds=['original_oversize_record_not_rendered'],training_admitted=False);rows.append(row);stats['parsed_source_records']+=1
  assert next(records,None) is None and stats['encountered_records']==89951 and stats['parsed_source_records']==29 and stats['record_bytes']==5333780260
  assert stats['tar_end_blocks_verified'] and stats['gzip_eof_crc_verified'] and stats['actual_decoded_bytes']==5333783552;deltas=[]
  for row in rows:
   g.check();page=row['page_id'];existing=[dict(json.loads(x['data']),source_ordinal=x['ordinal']) for x in source.execute('select ordinal,data from records where page_id=?',(page,))];supp=[x for x in rows if x['page_id']==page];old_selected=canon.execute('select source_ordinal,revision_id,family from candidates where page_id=?',(page,)).fetchone();aug=[dict(x,identity_holds=x['identity_holds']+['original_oversize_record_render_hold']) for x in supp];selected,disposition=c.resolve_group(existing+aug);aliases=[dict(x) for x in canon.execute('select source_ordinal,page_id,title,url,book_root,family from aliases where page_id=? or title=? or url=?',(page,row['title'],row['url']))];rt=c.root(row['title']) if isinstance(row['title'],str) else None;rootfamilies=[dict(x) for x in canon.execute('select distinct book_root,family from aliases where book_root=?',(rt,))]
   deltas.append({'supplement_source_ordinal':row['source_ordinal'],'page_id':page,'supplement_revision':row['revision_id'],'existing_same_page_occurrences':[{'ordinal':x['source_ordinal'],'revision':x['revision_id'],'title':x['title'],'url':x['url']} for x in existing],'existing_canonical':dict(old_selected) if old_selected else None,'proposed_selection_with_original_oversize_hold':selected,'existing_selection_changes':bool(old_selected and selected!=old_selected['source_ordinal']),'shadowed_existing_maximum':bool(existing and row['revision_id']>=max(x['revision_id'] or -1 for x in existing)),'same_page_or_title_URL_alias_candidates':aliases,'book_root':rt,'existing_book_root_families':rootfamilies,'supplement_group_disposition':disposition,'supplement_remains_render_held':True})
  write(output,'metadata29.json',rows,g);write(output,'canonical-delta.json',deltas,g);db=sqlite3.connect(output/'inventory.sqlite3');db.execute('create table supplemental_metadata (source_ordinal integer primary key,page_id integer,revision_id integer,data text)');db.executemany('insert into supplemental_metadata values (?,?,?,?)',[(x['source_ordinal'],x['page_id'],x['revision_id'],json.dumps(x,ensure_ascii=True)) for x in rows]);db.commit();assert db.execute('pragma integrity_check').fetchone()[0]=='ok';db.close();db=None;source.close();canon.close();check_pins();assert file_sha(archive)==ARCHIVE_SHA256;g.check()
  result={'status':'COMPLETE_IDENTITY_FRAME_NO_ADMISSION','scope':'SUPPLEMENTAL29_METADATA_ONLY_ORIGINAL_RENDER_HOLDS_PRESERVED','archive_sha256':ARCHIVE_SHA256,'original_frame_sha256':file_sha(FRAME),'original_canonical_sha256':file_sha(CANON),'inventory_sha256':file_sha(output/'inventory.sqlite3'),'stats':stats,'supplement_records':29,'new_page_IDs':len({r['page_id'] for r in rows}),'existing_same_page_ID_matches':sum(bool(x['existing_same_page_occurrences']) for x in deltas),'shadowed_existing_maximum_records':sum(x['shadowed_existing_maximum'] for x in deltas),'existing_canonical_selection_changes':sum(x['existing_selection_changes'] for x in deltas),'same_page_title_URL_alias_candidate_records':sum(bool(x['same_page_or_title_URL_alias_candidates']) for x in deltas),'existing_book_root_family_records':sum(bool(x['existing_book_root_families']) for x in deltas),'limits':limits,'elapsed_seconds':shared_clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0}
  return terminal_write(output/'worker-result.json',result,CAPS['output_bytes'])
 except BaseException as exc:
  if db:db.close()
  terminal_write(output/'worker-result.json',{'status':'PARTIAL_IDENTITY_FRAME_NO_ADMISSION','reason':str(exc),'stats':stats,'new_admitted_documents':0,'new_admitted_tokens':0},CAPS['output_bytes']);raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--supervisor-pid',type=int,required=True);p.add_argument('--start-monotonic',type=float,required=True);a=p.parse_args();assert os.getppid()==a.supervisor_pid and 0<=shared_clock()-a.start_monotonic<170;build(a.archive,a.output,a.start_monotonic)
if __name__=='__main__':main()
