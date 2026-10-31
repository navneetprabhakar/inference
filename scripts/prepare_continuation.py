"""Build fresh English continuation text, with bounded duplicate screening."""
import collections,gzip,hashlib,json,pickle,re,shutil,sqlite3,time,unicodedata
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer
from prepare_pilot import digest,normalized
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/continuation-v1';ARCH=ROOT.parent/'inference-archive-20261029/restart/execution-v1/m2-intake'
STOPWORDS=set('the a an is are was were be been to of and in on at from with for as by it its this that these those have has had do does did not can will would may which who their they them you your we our or but if when than then into also'.split())
def paragraphs(text):return [x.strip() for x in re.split(r'\n+',text) if x.strip()]
def fingerprint(text):
    words=re.findall(r'[a-z0-9]+',text.casefold())[:4096]
    if len(words)<5:return int(digest(text)[:16],16)
    hashes=np.fromiter((int.from_bytes(hashlib.blake2b(' '.join(words[i:i+5]).encode(),digest_size=8).digest(),'little') for i in range(len(words)-4)),dtype=np.uint64)
    hashes=np.unique(hashes)
    if len(hashes)>64:hashes=np.partition(hashes,63)[:64]
    bits=np.unpackbits(hashes.view(np.uint8).reshape(-1,8),axis=1,bitorder='little');majority=(bits.sum(axis=0)*2>=len(bits)).astype(np.uint8)
    return int.from_bytes(np.packbits(majority,bitorder='little').tobytes(),'little')
class Near:
    def __init__(self):self.tables=[collections.defaultdict(list) for _ in range(4)]
    def add(self,h):
        for i,t in enumerate(self.tables):t[(h>>(16*i))&65535].append(h)
    def contains(self,h):
        return any((h^other).bit_count()<=3 for i,t in enumerate(self.tables) for other in t.get((h>>(16*i))&65535,()))
def english(text):
    letters=[c for c in text if c.isalpha()]
    words=re.findall(r'[a-z]+',text.lower())
    return len(words)>=60 and bool(letters) and sum(c.isascii() for c in letters)/len(letters)>=.95 and sum(w in STOPWORDS for w in words)/len(words)>=.06 and len(set(words)&STOPWORDS)>=8

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    if (OUT/'manifest.json').exists():raise RuntimeError('Already prepared')
    start=time.time();cache=OUT/'protection-cache.pkl'
    known=set();para=set();near=Near();stats=collections.Counter()
    index=sqlite3.connect(f'file:{ROOT / "data/pilot-v1/documents.sqlite"}?mode=ro',uri=True)
    if cache.exists():
        with cache.open('rb') as f:known,para,near=pickle.load(f)
    else:
        for i,(h,text) in enumerate(index.execute('SELECT hash,text FROM docs')):
            known.add(h);near.add(fingerprint(text))
            para.update(digest(normalized(p)) for p in paragraphs(text) if len(p)>=80)
            if i%20000==0:print('protecting old documents',i,flush=True)
        # Protect previous generation-evaluation documents, including their long paragraphs.
        e=json.loads((ROOT/'reports/evaluation-v1/evaluation-set.json').read_text())
        protected={h for v in e['provenance'].values() for h in v.get('normalized_document_sha256',[])}
        wiki=ARCH/'raw/79ee06627f4ba2fec056fcd23c077a29238bbcbacc3187e8d1a0b47e663e9c7a.parquet'
        for b in pq.ParquetFile(wiki).iter_batches(columns=['text']):
            for text in b['text'].to_pylist():
                h=digest(normalized(text))
                if h in protected:
                    near.add(fingerprint(text));para.update(digest(normalized(p)) for p in paragraphs(text) if len(p)>=80)
        known.update(protected)
        with cache.open('wb') as f:pickle.dump((known,para,near),f)
    index.close();print('protected',len(known),'docs',len(para),'paragraphs',time.time()-start,flush=True)
    tok=Tokenizer.from_file(str(ROOT/'data/pilot-v1/tokenizer.json'));shutil.copyfile(ROOT/'data/pilot-v1/tokenizer.json',OUT/'tokenizer.json')
    c=sqlite3.connect(OUT/'documents.sqlite');c.execute('CREATE TABLE docs(hash TEXT PRIMARY KEY,source TEXT,split TEXT,group_id TEXT,text TEXT,metadata TEXT,tokens INTEGER)')
    wiki=ARCH/'raw/79ee06627f4ba2fec056fcd23c077a29238bbcbacc3187e8d1a0b47e663e9c7a.parquet';press=ARCH/'common-pile-pressbooks-raw-v1/00000_pressbooks.json.gz'
    def records(source):
        if source=='pressbooks':
            with gzip.open(press,'rt') as f:
                for line in f:
                    r=json.loads(line);meta=r['metadata'];u=urlsplit(meta.get('book_url',r['id']));group=urlunsplit((u.scheme,u.netloc,u.path.split('/chapter/')[0].split('/front-matter/')[0],'',''))
                    yield r['text'],group,meta
        else:
            path=wiki if source=='wikipedia' else OUT/'raw/fineweb-new.parquet'
            for b in pq.ParquetFile(path).iter_batches(batch_size=256):
                for r in b.to_pylist():
                    if source=='fineweb' and r.get('language')!='en':continue
                    u=urlsplit(r['url']);group=urlunsplit((u.scheme,u.netloc.lower(),u.path,'',''))
                    yield r['text'],group,{'url':r['url'],'id':r.get('id'),'source_file':str(path),'license':'CC-BY-SA/GFDL' if source=='wikipedia' else 'ODC-By dataset; underlying web provenance retained'}
    manifest={'sources':{},'vocab_size':tok.get_vocab_size(),'eos':1,'source_token_counts':{},'old_documents_protected':len(known),'old_long_paragraphs_protected':len(para),'duplicate_screen':'normalized exact document exclusion; repeated paragraphs >=80 characters removed; bottom-64 5-word-shingle SimHash, first 4096 words, Hamming <=3 via four bands; applies to old documents and new retained records. Approximate, not semantic uniqueness proof.','split':'5% deterministic group hash; Pressbooks grouped by book, Wikipedia/FineWeb by canonical URL; legacy evaluation hashes explicitly protected','language_screen':'source metadata plus >=95% ASCII letters and English function-word checks; heuristic, not comprehensive language verification','tokenizer_sha256':hashlib.sha256((OUT/'tokenizer.json').read_bytes()).hexdigest(),'sources_url':{'fineweb':'https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu','pressbooks':'https://huggingface.co/datasets/common-pile/pressbooks','wikipedia':'https://huggingface.co/datasets/wikimedia/wikipedia'}}
    # Target ample distinct blocks for 200M new tokens, never epoch/replay this pool.
    for source,cap in [('wikipedia',60_000_000),('pressbooks',60_000_000),('fineweb',120_000_000)]:
        totals={'train':0,'validation':0};pending=[];files={s:(OUT/f'{source}-{s}.bin').open('wb') for s in totals}
        def flush():
            if not pending:return
            encodings=tok.encode_batch([r[4] for r in pending])
            for record,enc in zip(pending,encodings):
                h,src,split,group,text,meta=record;ids=enc.ids+[1]
                limit=cap if split=='train' else 2_000_000
                if totals[split]+len(ids)>limit:stats[source+'_token_cap_skip']+=1;continue
                np.asarray(ids,dtype=np.uint16).tofile(files[split]);totals[split]+=len(ids)
                c.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?)',(h,src,split,group,text,json.dumps(meta),len(ids)))
            pending.clear();c.commit()
        for i,(text,group,meta) in enumerate(records(source)):
            stats[source+'_read']+=1
            if not isinstance(text,str) or not 300<=len(text)<=100000 or '\ufffd' in text or not english(text):stats[source+'_quality_reject']+=1;continue
            original=digest(normalized(text))
            if original in known:stats[source+'_exact_reject']+=1;continue
            fp=fingerprint(text)
            if near.contains(fp):stats[source+'_near_reject']+=1;continue
            parts=[];local=set()
            for part in paragraphs(text):
                h=digest(normalized(part))
                if len(part)>=80 and (h in para or h in local):stats[source+'_paragraphs_removed']+=1;continue
                parts.append(part);local.add(h)
            clean='\n'.join(parts)
            if len(clean)<.6*len(text) or not english(clean):stats[source+'_overlap_or_clean_quality_reject']+=1;continue
            h=digest(normalized(clean))
            if h in known:stats[source+'_clean_exact_reject']+=1;continue
            known.add(original);known.add(h);near.add(fp);near.add(fingerprint(clean));para.update(digest(normalized(p)) for p in parts if len(p)>=80)
            split='validation' if int(digest(group)[:8],16)%100<5 else 'train'
            pending.append((h,source,split,group,clean,meta))
            if len(pending)>=64:flush()
            if i%5000==0:print(source,i,totals,flush=True)
            if totals['train']>=cap-100000:break
        flush()
        for split,f in files.items():
            f.close();path=OUT/f'{source}-{split}.bin'
            manifest['sources'][f'{source}-{split}']={'path':path.name,'tokens':totals[split],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest['source_token_counts'][source]=totals;print('SOURCE COMPLETE',source,totals,flush=True)
    # One block-shuffled no-replacement pool. Truncate source tails so each source
    # occupies whole 512-target blocks; a boundary context token is permitted.
    combined=OUT/'train.bin';ranges={};total=0
    with combined.open('wb') as f:
        for source in ['fineweb','wikipedia','pressbooks']:
            a=np.memmap(OUT/f'{source}-train.bin',dtype=np.uint16,mode='r');n=(len(a)//512)*512;a[:n].tofile(f);ranges[source]=[total,total+n];total+=n
        np.asarray([1],dtype=np.uint16).tofile(f)
    assert total>=205_000_000,('Insufficient fresh data; do not launch',total)
    assert all(manifest['source_token_counts'][s]['train']>=25_000_000 for s in ['wikipedia','pressbooks'])
    assert all(manifest['source_token_counts'][s]['validation']>=100000 for s in ['fineweb','wikipedia','pressbooks'])
    manifest.update(train_tokens=total,train_sha256=hashlib.sha256(combined.read_bytes()).hexdigest(),source_ranges=ranges,screen_counts=dict(stats),seconds=time.time()-start)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest),flush=True);c.close()
if __name__=='__main__':main()
