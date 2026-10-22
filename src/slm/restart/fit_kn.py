"""Supervised M1 train-only five-gram preparation; never reads final-test data."""
import argparse,hashlib,json,os,pathlib,threading,time
import numpy as np
from .kneser_ney import build,windows,Model
from .supervisor import atomic_json

def checked(path,split):
    path=pathlib.Path(path);meta=json.loads((path/'manifest.json').read_text())
    if meta['split']!=split:raise ValueError('Wrong baseline split')
    for name,digest in meta['files'].items():
        if pathlib.Path(name).name!=name:raise ValueError('Invalid data file')
        h=hashlib.sha256()
        with (path/name).open('rb') as f:
            for chunk in iter(lambda:f.read(4*1024**2),b''):h.update(chunk)
        if h.hexdigest()!=digest:raise ValueError('Changed input')
    ids=np.memmap(path/'tokens.u16',dtype='<u2',mode='r')
    index=[json.loads(x) for x in (path/'index.jsonl').read_text().splitlines()]
    if len(ids)!=meta['targets']:raise ValueError('Target count mismatch')
    return meta,ids,index

def main():
    p=argparse.ArgumentParser();p.add_argument('--train',required=True);p.add_argument('--dev',required=True);p.add_argument('--out',required=True);p.add_argument('--heartbeat',required=True);a=p.parse_args()
    stop=threading.Event();hb=pathlib.Path(a.heartbeat)
    def pulse():
        while not stop.is_set():
            atomic_json(hb,{'pid':os.getpid(),'monotonic':time.monotonic()});stop.wait(5)
    t=threading.Thread(target=pulse,daemon=True);t.start();started=time.monotonic()
    try:
        train,ids,index=checked(a.train,'train');dev,dev_ids,dev_index=checked(a.dev,'development')
        if train['tokenizer_manifest_sha256']!=dev['tokenizer_manifest_sha256']:raise ValueError('Tokenizer mismatch')
        highest=windows(ids,index);out=pathlib.Path(a.out)
        meta=build(highest,out,notify=lambda x:print(json.dumps(x),flush=True));del highest
        query=windows(dev_ids,dev_index);trials=[]
        for scale in meta['discount_scale_grid']:
            probability=Model(out,scale).probabilities(query)
            if np.any(probability<=0):raise ValueError('Zero-probability development targets; no silent epsilon floor')
            loss=float(-np.log(probability).sum())
            trials.append({'scale':scale,'development_nll':loss/len(query),'development_bits_per_byte':loss/np.log(2)/dev['scored_utf8_bytes']})
            print(json.dumps(trials[-1]),flush=True)
        chosen=min(trials,key=lambda x:x['development_nll'])
        files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.is_file()}
        receipt={'status':'PASS','scope':'modified Kneser-Ney five-gram baseline; no neural model training','training_targets':len(ids),'development_targets':len(query),'trials':trials,'selected':chosen,'boundary':meta['boundary'],'discounts':meta['discounts'],'files':files,'source_tokenizer_sha256':train['tokenizer_manifest_sha256'],'final_set_read_or_scored':False,'elapsed_seconds':time.monotonic()-started}
        atomic_json(out/'receipt.json',receipt)
    finally:stop.set();t.join(timeout=10)
if __name__=='__main__':main()
