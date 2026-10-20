"""Read exactly the frozen20Parquet groups under the original durable intake budget."""
# Creator: Navneet Prabhakar
import json,os,resource,shutil
from pathlib import Path
from slm.data.intake_ledger import IntakeLedger
from slm.data.intake_cache import IntakeCache
from slm.data.intake_transport import once
from slm.data.parquet_ranges import BoundedParquet,ExactRanges,Limits
from slm.data.stream_hash import sha
OLD=Path('data/conversation-corpus-intake-v1');ROOT=Path('data/conversation-parquet-intake-v3');CONFIG=Path('configs/conversation-parquet-intake-v4.json')

def main():
 p=json.loads(CONFIG.read_text())
 for name,h in p['inputs'].items():
  if sha(name)!=h:raise ValueError('Pinned group intake input changed: '+name)
 if (ROOT/'intake-start.json').exists():raise FileExistsError('Retain previous actual group attempt')
 m=json.loads((ROOT/'metadata.json').read_text());original=json.loads(Path('configs/conversation-corpus-intake-v1.json').read_text())
 ledger=IntakeLedger(OLD/'ledger',original);cache=IntakeCache(ROOT/'cache',ledger);parts=[];count=0
 (ROOT/'intake-start.json').write_text(json.dumps(dict(parent=os.getpid(),original_deadline=ledger.deadline,config_sha256=sha(CONFIG)))+'\n')
 try:
  for item in m['files']:
   url='https://huggingface.co/datasets/'+original['source']+'/resolve/'+original['revision']+'/'+item['path']
   class Transport(ExactRanges):
    def get(self,start,length):return once(cache,'parquet/'+item['path']+'/'+str(start)+'/'+str(length),length,lambda:super(Transport,self).get(start,length))
   reader=BoundedParquet(Transport(url,item['size'],'"'+item['xetHash']+'"',Limits(**m['limits'])))
   for g in [x for x in m['selected'] if x['file']==item['path']]:
    ledger.check_time()
    if shutil.disk_usage(ROOT).free<40*1024**3 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>8*1024**3:raise ValueError('Original local resource guards')
    key='decode/'+item['path']+'/'+str(g['group']);ledger.reserve(key,rows=g['rows'],output_bytes=8*1024**2)
    table=reader.read_group(g['group']);rows=table.to_pylist();del table
    if len(rows)!=g['rows']:raise ValueError('Pinned complete group row count differs')
    lines=[]
    for i,row in enumerate(rows):
     if set(row)!={'messages','source'}:raise ValueError('Original source columns required')
     lines.append(json.dumps(dict(official_split='train',row_index=g['global_start']+i,source_file=item['path'],row_group=g['group'],offset_within_group=i,**row),ensure_ascii=False)+'\n')
    raw=''.join(lines).encode()
    if len(raw)>8*1024**2:raise ValueError('Bounded decoded group publication')
    path=ROOT/('rows-'+str(len(parts)).zfill(2)+'.jsonl')
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    ledger.finish(key,raw=b'');parts.append(dict(file=str(path),sha256=sha(path),rows=len(rows),source_file=item['path'],row_group=g['group'],global_start=g['global_start']));count+=len(rows)
    (ROOT/'progress.json').write_text(json.dumps(dict(groups=len(parts),new_rows=count,old_rows=100,upstream_test_rows=24229))+'\n');print('groups',len(parts),'new rows',count,flush=True)
  if count!=sum(g['rows'] for g in m['selected']):raise ValueError('Complete selected finite cohort required')
  sources=[OLD/'train.jsonl',*[Path(x['file']) for x in parts]];size=sum(x.stat().st_size for x in sources);ledger.reserve('combined-conversation-candidates',output_bytes=size)
  with (ROOT/'train.jsonl').open('xb') as f:
   for path in sources:
    with path.open('rb') as s:shutil.copyfileobj(s,f,1024**2)
  ledger.finish('combined-conversation-candidates',raw=b'')
  ids=[json.loads(x)['row_index'] for x in (ROOT/'train.jsonl').read_text().splitlines()]
  if len(ids)!=len(set(ids))!=0:raise ValueError('Source row duplication')
  report=dict(creator='Navneet Prabhakar',complete=True,new_group_rows=count,retained_prior_successful_rows=100,total_candidate_rows=count+100,source_test_rows=24229,source_test_path=str(OLD/'upstream-test.jsonl'),source_test_sha256=sha(OLD/'upstream-test.jsonl'),parts=parts,train_sha256=sha(ROOT/'train.jsonl'),metadata_sha256=sha(ROOT/'metadata.json'),config_sha256=sha(CONFIG),ledger=ledger.snapshot(),training_approved=False,scope='Complete selected pinned-file groups, excluding all earlier viewer attempt row intervals. Original200prefix excluded. Original failed viewer charges/deadline retained; raw original100successful rows cloned. No candidate filtering or corpus admission.')
  (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 except BaseException as e:
  (ROOT/'failure.json').write_text(json.dumps(dict(complete=False,error_type=type(e).__name__,message=str(e),ledger=ledger.snapshot()),indent=2,sort_keys=True)+'\n');raise
 finally:ledger.close()
if __name__=='__main__':main()
