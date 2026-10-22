"""Materialize isolated M1 streams; no model allocation or final scoring."""
import collections,csv,hashlib,json,pathlib,sqlite3,struct,tempfile,shutil,os
import numpy as np
from slm.common.tokenizer import BPE,STRUCTURAL
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).resolve().parent
MAN=R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def byte_decoder():
    kept=list(range(33,127))+list(range(161,173))+list(range(174,256));chars=list(kept);extra=0
    for b in range(256):
        if b not in kept:kept.append(b);chars.append(256+extra);extra+=1
    return {chr(u):b for b,u in zip(kept,chars)}
def main():
    receipt=json.loads((O/'tokenizer-receipt.json').read_text())
    if sha(MAN)!='2ad53dc0fc670a7185763f1cfe151e1148933038b8855e55d54a29f84256716d':raise ValueError('Changed source')
    if sha(O/'tokenizer-8192/manifest.json')!=receipt['tokenizer_manifest_sha256']:raise ValueError('Changed tokenizer')
    tok=BPE.load(O/'tokenizer-8192');decoder=byte_decoder()
    lengths={i:len(bytes(decoder[c] for c in tok._core.id_to_token(i-10))) for i in range(10,tok.vocab_size)}
    con=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    rows=list(csv.DictReader(MAN.open()))
    result={};all_families={};all_hashes=set()
    for name,split,budget in [('data-train','train',None),('data-dev','development',200000),('data-final','test',None)]:
        target=O/name
        if target.exists():raise FileExistsError(target)
        stage=pathlib.Path(tempfile.mkdtemp(prefix='.'+name+'-',dir=O))
        selected=sorted((r for r in rows if r['split']==split),key=lambda r:hashlib.sha256(('m1-loss-v1:'+r['family_id']+':'+r['audit_id']).encode()).digest())
        docs=targets=bytes_=0;families=set();unigram=np.zeros(tok.vocab_size,dtype=np.uint64)
        try:
            with (stage/'tokens.u16').open('wb') as stream,(stage/'index.jsonl').open('w') as index:
                for r in selected:
                    if budget is not None and targets>=budget:break
                    if split!='train' and r['source']!='TinyStories':raise ValueError('Narrative holdout required')
                    text=con.execute('select text from docs where id=?',(int(r['audit_id']),)).fetchone()[0]
                    if hashlib.sha256(text.encode()).hexdigest()!=r['original_text_sha256']:raise ValueError('Text changed')
                    ids=tok.encode(text)
                    raw=b''.join(bytes(decoder[c] for c in tok._core.id_to_token(i-10)) for i in ids)
                    if raw!=text.encode():raise ValueError('Tokenizer byte mapping mismatch')
                    encoded=ids+[STRUCTURAL['eos']]
                    count=len(encoded) if budget is None else min(len(encoded),budget-targets)
                    encoded=encoded[:count];nbytes=sum(lengths.get(i,0) for i in encoded)
                    stream.write(np.asarray(encoded,dtype='<u2').tobytes())
                    row={'audit_id':r['audit_id'],'source':r['source'],'split':split,'family_id':r['family_id'],'offset':targets,'targets':count,'full_document_targets':len(ids)+1,'partial':count<len(ids)+1,'scored_utf8_bytes':nbytes,'original_text_sha256':r['original_text_sha256'],'normalized_sha256':r['normalized_sha256']}
                    index.write(json.dumps(row,sort_keys=True)+'\n')
                    unigram+=np.bincount(encoded,minlength=tok.vocab_size).astype(np.uint64)
                    docs+=1;targets+=count;bytes_+=nbytes;families.add(r['family_id'])
                    if r['normalized_sha256'] in all_hashes:raise ValueError('Duplicate text')
                    all_hashes.add(r['normalized_sha256']);all_families.setdefault(r['family_id'],set()).add(split)
            if split=='train':np.save(stage/'unigram-counts.npy',unigram,allow_pickle=False)
            if split!='train' and len(families)<500:raise ValueError('Insufficient holdout families')
            if split=='development' and targets!=200000:raise ValueError('Development supply shortfall')
            if split=='test' and targets<500000:raise ValueError('Final supply shortfall')
            if split in ('train','test') and targets!=receipt['splits'][split]['targets_with_eos']:raise ValueError('Count mismatch')
            summary={'split':split,'documents':docs,'families':len(families),'targets':targets,'scored_utf8_bytes':bytes_,'files':{p.name:sha(p) for p in stage.iterdir()},'source_manifest_sha256':sha(MAN),'tokenizer_manifest_sha256':receipt['tokenizer_manifest_sha256'],'order':'sha256 m1-loss-v1:family:id','selection':'all documents' if budget is None else 'first exactly 200000 targets, only final selected document may be partial'}
            (stage/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
            os.rename(stage,target);result[name]=summary
        except BaseException:shutil.rmtree(stage,ignore_errors=True);raise
    if any(len(s)>1 for s in all_families.values()):raise ValueError('Family leakage')
    (O/'loss-data-receipt.json').write_text(json.dumps({'status':'PASS','scope':'M1 exact loss streams; final only materialized, not scored','streams':result,'cross_split_families':False,'neural_weights_initialized':False},indent=2)+'\n')
    print(json.dumps({k:{x:v[x] for x in ['documents','families','targets']} for k,v in result.items()},indent=2),flush=True)
if __name__=='__main__':main()
