"""Fresh bounded corpus and tokenizer from retained raw data; no legacy trainer."""
import argparse,hashlib,json,re,sqlite3,time,unicodedata
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer,models,normalizers,pre_tokenizers,decoders,trainers

def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def normalized(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def prepare(out,archive):
    out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():raise RuntimeError('Prepared corpus already exists; choose a new output')
    db=out/'documents.sqlite';c=sqlite3.connect(db,check_same_thread=False)
    c.execute('CREATE TABLE IF NOT EXISTS docs(hash TEXT PRIMARY KEY,source TEXT,split TEXT,text TEXT)')
    c.execute('CREATE INDEX IF NOT EXISTS by_source_split ON docs(source,split)')
    counts={};start=time.time()
    def add(text,source,group=None):
        if not isinstance(text,str):return
        text=unicodedata.normalize('NFC',text).strip()
        if not 200<=len(text)<=80000 or '\ufffd' in text:return
        letters=[ch for ch in text if ch.isalpha()]
        if not letters or sum(ch.isascii() for ch in letters)/len(letters)<.95:return
        h=digest(normalized(text));key=group or h
        split='validation' if int(digest(key)[:8],16)%100==0 else 'train'
        c.execute('INSERT OR IGNORE INTO docs VALUES(?,?,?,?)',(h,source,split,text))
    fine=archive/'restart/execution-v1/m2-intake/raw/b393f51fefab26cd6f4c8f65707c1924f6666c4961a0ebebe04bb57f7ec832de.parquet'
    for batch in pq.ParquetFile(fine).iter_batches(batch_size=512,columns=['text','url','language']):
        for row in batch.to_pylist():
            if row['language']!='en':continue
            u=urlsplit(row['url']);add(row['text'],'fineweb',urlunsplit((u.scheme,u.netloc.lower(),u.path,'','')))
        c.commit()
    tiny=archive/'restart/mac15m-feasibility-v1/upstream/data/TinyStories_all_data'
    for file in sorted(tiny.glob('*.json'))[:2]:
        for row in json.loads(file.read_text()):add(row['story'],'tinystories')
        c.commit()
    print('documents ready',time.time()-start,flush=True)
    tokenizer=Tokenizer(models.BPE(unk_token='<|unk|>'))
    tokenizer.normalizer=normalizers.NFC();tokenizer.pre_tokenizer=pre_tokenizers.ByteLevel(add_prefix_space=False);tokenizer.decoder=decoders.ByteLevel()
    trainer=trainers.BpeTrainer(vocab_size=16384,min_frequency=2,initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),special_tokens=['<|unk|>','<|endoftext|>','<|system|>','<|user|>','<|assistant|>','<|tool_call|>','<|tool_result|>'],show_progress=False)
    def samples():
        for source in ['fineweb','tinystories']:
            for (text,) in c.execute("SELECT text FROM docs WHERE source=? AND split='train' ORDER BY hash LIMIT 10000",(source,)):yield text[:16000]
    tokenizer.train_from_iterator(samples(),trainer=trainer);tokenizer.save(str(out/'tokenizer.json'))
    print('tokenizer ready',time.time()-start,flush=True)
    eos=tokenizer.token_to_id('<|endoftext|>');manifest={'sources':{},'vocab_size':tokenizer.get_vocab_size(),'eos':eos,'train_mix':{'fineweb':.8,'tinystories':.2},'split':'1% deterministic group-hash; FineWeb canonical URL; TinyStories normalized text; global exact-text dedup before tokenization','limits':'No semantic near-dedup or universal benchmark decontamination; validation is diagnostic only. ASCII language heuristic is not comprehensive English quality assessment. Tokenizer fitted only on training documents.','raw_sources':[str(fine),str(tiny/'data00.json'),str(tiny/'data01.json')]}
    for source in ['fineweb','tinystories']:
        for split in ['train','validation']:
            cap=(100_000_000 if source=='fineweb' else 30_000_000) if split=='train' else 1_000_000
            path=out/f'{source}-{split}.bin';total=0;docs=0
            with path.open('wb') as f:
                cur=c.execute('SELECT text FROM docs WHERE source=? AND split=? ORDER BY hash',(source,split))
                while total<cap:
                    rows=cur.fetchmany(128)
                    if not rows:break
                    for enc in tokenizer.encode_batch([r[0] for r in rows]):
                        ids=enc.ids+[eos]
                        if total+len(ids)>cap:continue
                        np.asarray(ids,dtype=np.uint16).tofile(f);total+=len(ids);docs+=1
                    if cap-total<512:break
            assert total>100_000,(source,split,total)
            h=hashlib.sha256(path.read_bytes()).hexdigest()
            manifest['sources'][f'{source}-{split}']={'tokens':total,'documents':docs,'sha256':h,'path':path.name}
            print(source,split,total,flush=True)
    manifest['document_counts']=[{'source':r[0],'split':r[1],'documents':r[2]} for r in c.execute('SELECT source,split,count(*) FROM docs GROUP BY source,split')]
    manifest['tokenizer_sha256']=hashlib.sha256((out/'tokenizer.json').read_bytes()).hexdigest();manifest['seconds']=time.time()-start
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');c.close();print(json.dumps(manifest,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('data/pilot-v1'));p.add_argument('--archive',type=Path,default=Path('../inference-archive-20261029'));a=p.parse_args();prepare(a.output,a.archive.resolve())
