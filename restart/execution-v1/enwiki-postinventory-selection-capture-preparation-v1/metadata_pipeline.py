"""Future terminal-only metadata selection execution API. Never run on live frame."""
import json,os,hashlib
from pathlib import Path
import select_core,source_view,capture_pipeline

def derive(ctx,check):
 source_view.context(ctx);b=ctx['binding'];expected=ctx['expected']
 # Already SHA-bound by parent + independent verifier. Small codec rehash only.
 entry=b['codec'];path=source_view.pathcheck(entry);select_core.need(entry['stat'][2]<=1000000,'codec_preallocation_cap');raw=path.read_bytes();select_core.need(len(raw)<=1000000 and hashlib.sha256(raw).hexdigest()==entry['SHA256'],'codec_dictionary_SHA_bound');codec=json.loads(raw)
 with source_view.metadata_db(ctx,'frame',check) as db,source_view.metadata_db(ctx,'index',check) as index:
  pages=db.execute('SELECT '+','.join(select_core.FIELDS)+' FROM pages ORDER BY row_ordinal');groups=db.execute('SELECT * FROM groups ORDER BY group_ordinal')
  selection=select_core.scan_pages(pages,groups,expected,check);selection=select_core.enrich_selected(db,index,selection,codec['models'],check)
 entry=b['group_receipts'];path=source_view.pathcheck(entry);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  select_core.need(source_view.identity(os.fstat(fd))==entry['stat'],'group_metadata_FD_custody')
  with os.fdopen(os.dup(fd),'rb') as f:
   def lines():
    total=0
    while True:
     check();raw=f.readline(65537)
     if not raw:break
     total+=len(raw);select_core.need(len(raw)<=65536 and total<=256000000,'metadata_transcript_bounds');yield raw
    select_core.need(total==entry['stat'][2],'metadata_transcript_exact_EOF_bytes')
   selection=select_core.attach_groups(lines(),selection,entry['SHA256'],expected['groups'],check)
  select_core.need(source_view.identity(os.fstat(fd))==entry['stat'],'group_metadata_FD_after');source_view.pathcheck(entry)
 finally:os.close(fd)
 selection['capture_plan']=capture_pipeline.plan(selection);selection['terminal_frame_SHA256']=b['frame']['SHA256'];selection['terminal_scope']='RETAINED_PREFIX_FRAGMENT_NOT_WHOLE_PUBLISHER_ARCHIVE';selection['new_usable_documents']=0
 return selection
