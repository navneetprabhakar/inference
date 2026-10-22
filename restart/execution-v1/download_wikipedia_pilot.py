"""One deterministic pinned Wikipedia English shard for candidate-pipeline research."""
import hashlib,json,os,pathlib,shutil,time,urllib.request
from acquire_sources import ROOT,CONTRACT,IntakeLedger
O=pathlib.Path(__file__).resolve().parent

def main():
    metadata=json.loads((ROOT/'source-metadata.json').read_text())['sources']['wikipedia-api']
    inventory=json.loads((ROOT/'wikipedia-en-inventory.json').read_text())
    chosen=min(inventory,key=lambda x:hashlib.sha256(('m2-wikipedia-pilot-v1:'+x['path']).encode()).digest())
    size=chosen['size'];expected=chosen['lfs']['oid'];revision=metadata['revision']
    url='https://huggingface.co/datasets/'+metadata['id']+'/resolve/'+revision+'/'+chosen['path']
    key='wikipedia-pilot-shard:'+revision+':'+chosen['path']
    rawdir=ROOT/'raw';rawdir.mkdir(exist_ok=True)
    target=rawdir/(expected+'.parquet');partial=target.with_suffix('.partial')
    if target.exists() or partial.exists():raise FileExistsError('Existing or uncertain payload; no automatic replay')
    disk=json.loads((O/'disk-budget.json').read_text())
    reserve=disk['weights_checkpoints_reserved_bytes']+disk['scratch_cap_bytes']+disk['free_disk_floor_bytes']
    if shutil.disk_usage(ROOT).free<size+reserve:raise ValueError('Weights/scratch/free-space reserve would be violated')
    ledger=IntakeLedger(ROOT/'charges',CONTRACT);start=time.monotonic();written=0;digest=hashlib.sha256()
    try:
        ledger.reserve(key,requests=1,body_bytes=size+1,output_bytes=size)
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
            with urllib.request.urlopen(request,timeout=30) as response,partial.open('xb') as out:
                if response.headers.get('Content-Length') not in (None,str(size)):raise ValueError('Pinned size mismatch')
                while True:
                    if time.monotonic()-start>1800:raise TimeoutError('Pilot download deadline')
                    ledger.check_time()
                    if shutil.disk_usage(ROOT).free<reserve+4*1024**2:raise ValueError('Reserved disk headroom reached')
                    raw=response.read(min(4*1024**2,size+1-written))
                    if not raw:break
                    written+=len(raw)
                    if written>size:raise ValueError('Response exceeded pinned size')
                    out.write(raw);digest.update(raw)
                    if written//(128*1024**2)!=(written-len(raw))//(128*1024**2):print(json.dumps({'downloaded_bytes':written,'total_bytes':size,'elapsed_seconds':round(time.monotonic()-start,1)}),flush=True)
                out.flush();os.fsync(out.fileno())
            if written!=size or digest.hexdigest()!=expected:raise ValueError('Pinned file size/hash mismatch')
            os.rename(partial,target)
            fd=os.open(rawdir,os.O_RDONLY);os.fsync(fd);os.close(fd)
            ledger.db.execute('UPDATE attempts SET state=?,actual_bytes=?,body_sha256=? WHERE key=? AND state=?',('complete',written,expected,key,'pending'))
            receipt={'status':'DOWNLOADED_NOT_ADMITTED','source':metadata['id'],'revision':revision,'upstream_path':chosen['path'],'local_file':str(target),'sha256':expected,'bytes':written,'elapsed_seconds':time.monotonic()-start,'selection':'minimum SHA256(m2-wikipedia-pilot-v1:path) across pinned 41 English snapshot shards; not a full-source representative quality claim','license_review':'Pinned card labels CC-BY-SA-3.0/GFDL; current Wikimedia terms require attribution and applicable share-alike. Preserve page IDs, URLs, notices and transformations. Snapshot-specific license reconciliation remains an admission prerequisite; download for investigation only.','reserved_download_bytes':ledger.totals()['body_bytes']}
            (ROOT/'wikipedia-pilot-download.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2),flush=True)
        except BaseException as exc:
            ledger.finish(key,raw=None)
            (ROOT/'wikipedia-pilot-download-failure.json').write_text(json.dumps({'status':'FAILED','exception_type':type(exc).__name__,'bytes_written':written,'charged_bytes':size+1,'partial_file':str(partial),'automatic_retry':False},indent=2)+'\n')
            raise RuntimeError('Bounded pilot download failed; see local failure receipt, no automatic retry') from None
    finally:ledger.close()
if __name__=='__main__':main()
