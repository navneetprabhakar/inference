"""Pinned-file fallback after viewer outage, with the original global intake ledger."""
# Creator: Navneet Prabhakar
import json,os,resource,shutil
from pathlib import Path
from dataclasses import asdict
from slm.data.intake_ledger import IntakeLedger
from slm.data.intake_cache import IntakeCache
from slm.data.intake_transport import once
from slm.data.parquet_ranges import BoundedParquet,ExactRanges,Limits
from slm.data.schema import digest
from slm.data.stream_hash import sha
OLD=Path('data/conversation-corpus-intake-v1');ROOT=Path('data/conversation-parquet-intake-v3')

def main():
 if ROOT.exists():raise FileExistsError('Retain previous pinned-file attempt')
 p=json.loads(Path('configs/conversation-corpus-intake-v1.json').read_text());failure=json.loads(Path('data/conversation-corpus-continuation-v2/failure.json').read_text())
 if failure['message']!='Too many transport failures; no endless source attempts':raise ValueError('Retained viewer outage required')
 ledger=IntakeLedger(OLD/'ledger',p);ROOT.mkdir();cache=IntakeCache(ROOT/'cache',ledger)
 before=ledger.snapshot();attempted=[int(x['key'].rsplit('-',1)[1]) for x in before['attempts'] if x['key'].startswith('train-page-')]
 limits=Limits(network_bytes=64*1024**2,requests=32,footer_bytes=4*1024**2,group_compressed_bytes=8*1024**2,group_declared_uncompressed_bytes=32*1024**2,group_decoded_bytes=32*1024**2,group_rows=1000)
 output=[];groups=[];base=0
 try:
  for item in sorted(json.loads((OLD/'payloads/tree.json').read_text()),key=lambda x:x['path']):
   if not item['path'].startswith('data/train-'):continue
   ledger.check_time()
   if shutil.disk_usage(ROOT).free<40*1024**3 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>8*1024**3:raise ValueError('Original local resource guards')
   url='https://huggingface.co/datasets/'+p['source']+'/resolve/'+p['revision']+'/'+item['path']
   class Transport(ExactRanges):
    def get(self,start,length):return once(cache,'parquet/'+item['path']+'/'+str(start)+'/'+str(length),length,lambda:super(Transport,self).get(start,length))
   transport=Transport(url,item['size'],'"'+item['xetHash']+'"',limits);reader=BoundedParquet(transport);local=0
   for i in range(reader.metadata.num_row_groups):
    g=reader.metadata.row_group(i);cols=[g.column(j) for j in range(g.num_columns)];spans=[(c.dictionary_page_offset if c.has_dictionary_page else c.data_page_offset,c.total_compressed_size) for c in cols]
    declared=sum(c.total_uncompressed_size for c in cols);n=g.num_rows;global_start=base+local
    overlap=global_start<200 or any(global_start<a+100 and a<global_start+n for a in attempted)
    compatible=n<=1000 and 0<=declared<=32*1024**2 and max(s+l for s,l in spans)-min(s for s,l in spans)<=8*1024**2 and not overlap
    groups.append(dict(file=item['path'],group=i,rows=n,global_start=global_start,declared_bytes=declared,compatible=compatible,prior_attempted_page_overlap=overlap));local+=n
   output.append(dict(**item,rows=reader.metadata.num_rows,global_start=base,groups=reader.metadata.num_row_groups));base+=reader.metadata.num_rows
   print(item['path'],'rows',reader.metadata.num_rows,flush=True)
  if base!=460341 or len(output)!=4:raise ValueError('All pinned four-file train identities required')
  chosen=[]
  for item in output:
   pool=[g for g in groups if g['file']==item['path'] and g['compatible']]
   chosen+=sorted(pool,key=lambda g:digest([p['selection_seed'],'pinned-file-groups-v3',g['file'],g['group']]))[:5]
  if len(chosen)!=20 or sum(g['rows'] for g in chosen)>20000:raise ValueError('Finite distributed group sample required')
  report=dict(creator='Navneet Prabhakar',complete=True,files=output,groups=groups,selected=chosen,limits=asdict(limits),original_attempted_api_offsets_excluded=attempted,ledger=ledger.snapshot(),old_config_sha256=sha('configs/conversation-corpus-intake-v1.json'),viewer_failure_sha256=sha('data/conversation-corpus-continuation-v2/failure.json'),training_approved=False,scope='Pinned-file metadata fallback only, no row decode; same original body/request/row/output caps and absolute deadline, failed viewer charges retained. All attempted viewer row intervals excluded from new group selection.')
  (ROOT/'metadata.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 except BaseException as e:
  (ROOT/'metadata-failure.json').write_text(json.dumps(dict(complete=False,error_type=type(e).__name__,message=str(e),ledger=ledger.snapshot()),indent=2,sort_keys=True)+'\n');raise
 finally:ledger.close()
if __name__=='__main__':main()
