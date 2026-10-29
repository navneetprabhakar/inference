"""Bounded pinned source acquisition. Downloading does not admit training text."""
import hashlib,json,urllib.request,time
from pathlib import Path
P=Path(__file__).resolve().parent
SITES=['lifehacks','interpersonal','workplace','crafts','cooking']
CAP=512*1024**2
def save(path,x): path.write_text(json.dumps(x,indent=2)+'\n')
def main():
    api=json.loads((P/'stackexchange-api.json').read_text())
    selected=[s['rfilename'] for s in api['siblings'] if any(s['rfilename'].startswith(site+'.stackexchange.com/documents/') for site in SITES)]
    policy={'source':'common-pile/stackexchange','revision':api['sha'],'files':selected,'compressed_download_cap_bytes':CAP,'per_file_cap_bytes':100*1024**2,'sites':SITES,'metadata_requests_already_completed':2,'probe_files_already_completed':1,'purpose':'Everyday household/interpersonal/workplace accounts and advice candidates; not all site content fits domain','no_training':True,'admitted_tokens':0}
    if (P/'acquisition-policy.json').exists(): assert json.loads((P/'acquisition-policy.json').read_text())==policy
    else: save(P/'acquisition-policy.json',policy)
    receipt=P/'download-receipt.json';rows=json.loads(receipt.read_text()) if receipt.exists() else []
    for f in selected:
        dest=P/'private'/f.replace('/','__')
        if any(r['file']==f and r['status']=='COMPLETE' for r in rows):continue
        if f=='lifehacks.stackexchange.com/documents/00000_se.jsonl.gz' and (P/'private/lifehacks-0.jsonl.gz').exists():
            raw=(P/'private/lifehacks-0.jsonl.gz').read_bytes();dest.write_bytes(raw);rows.append(dict(file=f,status='COMPLETE',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),probe_reused=True));save(receipt,rows);continue
        used=sum(r.get('bytes',0) for r in rows)
        allowance=min(policy['per_file_cap_bytes'],CAP-used)
        if allowance<=0: raise RuntimeError('download ceiling exhausted')
        url='https://huggingface.co/datasets/'+policy['source']+'/resolve/'+api['sha']+'/'+f
        row=dict(file=f,status='STARTED',url=url,reserved_bytes=allowance);rows.append(row);save(receipt,rows)
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-source-preparation/2.0'})
            with urllib.request.urlopen(req,timeout=45) as response:
                raw=response.read(allowance+1)
            row['bytes']=len(raw)
            if len(raw)>allowance:raise RuntimeError('file cap reached; no admission')
            dest.write_bytes(raw);row.update(status='COMPLETE',sha256=hashlib.sha256(raw).hexdigest());save(receipt,rows)
            print(f,len(raw),flush=True)
        except BaseException as e:
            row.update(status='FAILED',error=str(e));save(receipt,rows);raise
        time.sleep(.2)
    print('Acquisition complete; no admission.',flush=True)
if __name__=='__main__':main()
