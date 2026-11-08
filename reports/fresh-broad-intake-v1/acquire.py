"""Sequential, byte-bounded acquisition of four pinned FineWeb-Edu raw shards."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/fresh-broad-intake-v1'
REV='87f09149ef4734204d70ed1d046ddc9ca3f2b8f9'
SHARDS=[
 ('002_00000.parquet',2151796315,'547ae182d132c9f06b6ce63149567208ea9f57630bfd9b1a2938e504f0c9ebd7'),
 ('003_00000.parquet',2152437524,'22184e6eb25759ddd97783751ffc73e1705dfa2542e630dae1f2a8bac8ee6ddb'),
 ('004_00000.parquet',2152338550,'33557ddd87a07a4ae6fcaf7a4789c7b484e5cc0c273ca12a65b74200e6d8748b'),
 ('005_00000.parquet',2152189947,'e08d79927ecb377786572cd854817c748ceb8880878b1a0eb91abf8c85d505ea')]


def main():
    start=time.monotonic();assert not DATA.exists();DATA.mkdir()
    plan=dict(state='raw_acquisition_only_not_training_admission',dataset='HuggingFaceFW/fineweb-edu',
              revision=REV,files=[dict(file=n,bytes=b,sha256=h) for n,b,h in SHARDS],
              max_bytes=sum(b for _,b,_ in SHARDS),seconds_limit=2700,parallel_downloads=1,
              source_metadata_url=f'https://huggingface.co/api/datasets/HuggingFaceFW/fineweb-edu/tree/{REV}/sample/10BT?limit=100')
    (DATA/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (Path(__file__).parent/'acquisition-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    receipts=[]
    for name,size,expected in SHARDS:
        url=f'https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu/resolve/{REV}/sample/10BT/{name}?download=true'
        temp=DATA/(name+'.partial');h=hashlib.sha256();count=0
        with urllib.request.urlopen(url,timeout=30) as response,temp.open('xb') as out:
            while True:
                assert time.monotonic()-start<2700
                assert not (ROOT/'runs/STOP').exists() and not (DATA/'STOP').exists()
                assert shutil.disk_usage(ROOT).free>20*1024**3
                chunk=response.read(1024**2)
                if not chunk:break
                count+=len(chunk);assert count<=size
                out.write(chunk);h.update(chunk)
        assert count==size and h.hexdigest()==expected
        temp.rename(DATA/name)
        receipts.append(dict(file=name,bytes=count,sha256=expected,url=url))
        (DATA/'progress.json').write_text(json.dumps(dict(completed=receipts,seconds=time.monotonic()-start),indent=2)+'\n')
        print(json.dumps(dict(completed=name,bytes=count,seconds=time.monotonic()-start)),flush=True)
    receipt=dict(state='verified_raw_shards_not_admitted',files=receipts,seconds=time.monotonic()-start,
                 training_admitted=False,pending=['Source filtering and domain split custody','Full historical/private and public overlap screening','Quality review','Deduplication and token packing','Independent verification and root source admission'])
    (DATA/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (Path(__file__).parent/'acquisition-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
