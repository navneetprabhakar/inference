"""M2 bounded public-source metadata intake using the durable global ledger."""
import hashlib,json,pathlib,shutil,urllib.request
from slm.data.intake_ledger import IntakeLedger
O=pathlib.Path(__file__).resolve().parent
ROOT=O/'m2-intake'
CONTRACT={'version':1,'scope':'M2 source investigation; owner authorized up to 80 GB downloads','limits':{'requests':100000,'body_bytes':80000000000,'rows':100000000,'output_bytes':80000000000},'wall_seconds':30*24*3600,'minimum_free_disk_bytes':20*1024**3,'paid_budget':0}
SOURCES={
 'fineweb-edu-api':'https://huggingface.co/api/datasets/HuggingFaceFW/fineweb-edu',
 'fineweb-api':'https://huggingface.co/api/datasets/HuggingFaceFW/fineweb',
 'wikipedia-api':'https://huggingface.co/api/datasets/wikimedia/wikipedia',
}
def fetch(ledger,key,url,cap=2000000):
    payload=ROOT/'metadata'/key
    if payload.exists():
        row=ledger.db.execute('SELECT state,body_sha256 FROM attempts WHERE key=?',(key,)).fetchone()
        if not row or row[0]!='complete' or hashlib.sha256(payload.read_bytes()).hexdigest()!=row[1]:raise ValueError('Unverified existing payload')
        return payload.read_bytes()
    disk=json.loads((O/'disk-budget.json').read_text())
    protected=disk['free_disk_floor_bytes']+disk['weights_checkpoints_reserved_bytes']+disk['scratch_cap_bytes']
    if shutil.disk_usage(ROOT).free<protected+cap:raise ValueError('Weights/scratch/free-space headroom insufficient')
    ledger.reserve(key,requests=1,body_bytes=cap,output_bytes=cap)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
        with urllib.request.urlopen(req,timeout=30) as response:
            if response.headers.get('Content-Length') and int(response.headers['Content-Length'])>=cap:raise ValueError('Response exceeds bounded acquisition')
            raw=response.read(cap)
            if len(raw)>=cap:raise ValueError('Response hit bound; refused')
        payload.parent.mkdir(parents=True,exist_ok=True);payload.write_bytes(raw)
        ledger.finish(key,raw=raw)
        return raw
    except BaseException:
        ledger.finish(key,raw=None);raise

def main():
    ROOT.mkdir(exist_ok=True)
    (ROOT/'contract.json').write_text(json.dumps(CONTRACT,indent=2)+'\n')
    ledger=IntakeLedger(ROOT/'charges',CONTRACT)
    try:
        results={}
        for key,url in SOURCES.items():
            api=json.loads(fetch(ledger,key,url));revision=api['sha'];repo=api['id']
            card=fetch(ledger,key+'-card-'+revision,'https://huggingface.co/datasets/'+repo+'/resolve/'+revision+'/README.md')
            results[key]={'id':repo,'revision':revision,'metadata_file':key,'card_file':key+'-card-'+revision,'license_labels':api.get('cardData',{}).get('license'),'parquet_files':[s['rfilename'] for s in api.get('siblings',[]) if s['rfilename'].endswith('.parquet')]}
        receipt={'sources':results,'reserved':ledger.totals(),'actual_successful_body_bytes':ledger.db.execute('SELECT coalesce(sum(actual_bytes),0) FROM attempts').fetchone()[0],'training_admitted':False,'scope':'pinned metadata/card collection only'}
        (ROOT/'source-metadata.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({k:{x:v[x] for x in ['id','revision','license_labels']}|{'parquet_file_count':len(v['parquet_files'])} for k,v in results.items()},indent=2));print('budgets',receipt['reserved'],'actual',receipt['actual_successful_body_bytes'])
    finally:ledger.close()
if __name__=='__main__':main()
