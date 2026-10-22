"""M1 train-only tokenizer preparation. Never initializes a neural model."""
import csv, hashlib, json, pathlib, sqlite3, time
import numpy as np
from slm.common.tokenizer import train_core, BPE, OFFSET
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(__file__).resolve().parent
MAN=ROOT/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
EXPECTED='2ad53dc0fc670a7185763f1cfe151e1148933038b8855e55d54a29f84256716d'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    started=time.time()
    if sha(MAN)!=EXPECTED: raise ValueError('Frozen manifest changed')
    rows=list(csv.DictReader(MAN.open()))
    byid={int(r['audit_id']):r for r in rows}
    if len(byid)!=len(rows): raise ValueError('Duplicate identity')
    families={}; hashes=set()
    for r in rows:
        if r['normalized_sha256'] in hashes: raise ValueError('Duplicate content')
        hashes.add(r['normalized_sha256'])
        families.setdefault(r['family_id'],set()).add(r['split'])
    if any(len(s)!=1 for s in families.values()): raise ValueError('Family leakage')
    con=sqlite3.connect(f'file:{ROOT}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    train=sorted((r for r in rows if r['split']=='train'),key=lambda r:hashlib.sha256(('m1-tokenizer-v1:'+r['family_id']+':'+r['audit_id']).encode()).digest())
    texts=[]; selected=[]; nbytes=0
    for r in train:
        text=con.execute('select text from docs where id=?',(int(r['audit_id']),)).fetchone()[0]
        raw=text.encode('utf8')
        if hashlib.sha256(raw).hexdigest()!=r['original_text_sha256']:raise ValueError('Text mismatch')
        if nbytes+len(raw)>32*1024*1024:break
        texts.append(text); selected.append(r['audit_id']); nbytes+=len(raw)
    target=OUT/'tokenizer-8192'
    provenance={'manifest_sha256':EXPECTED,'selection':'sha256 m1-tokenizer-v1:family:id ascending, complete documents until 32MiB','train_ids':selected,'utf8_bytes':nbytes,'fit_documents':len(selected)}
    if target.exists():
        if json.loads((target/'manifest.json').read_text())['provenance']!=provenance:raise ValueError('Frozen tokenizer provenance changed')
    else:
        tok=train_core(texts,8192)
        if tok.vocab_size!=8192:raise ValueError('Vocabulary shortfall')
        tok.save(target,provenance)
    tok=BPE.load(target)
    fixed=['',' English\n\tpunctuation!? ','<tool_call_start>{"path":"/a/b", "n":-1.25}</tool_call_end>','café हिन्दी 😀 e\u0301','\x00\r\n']
    for i in range(10000):
        s=fixed[i%len(fixed)]+f' case={i} '+chr(32+i%95)+chr(0x400+i%256)
        ids=tok.encode(s)
        if tok.decode(ids)!=s or any(x<OFFSET for x in ids):raise ValueError('Roundtrip/control failure')
    for invalid in ['\ud800','a\udfff']:
        try:tok.encode(invalid)
        except UnicodeEncodeError:pass
        else:raise ValueError('Invalid Unicode accepted')
    counts={}; fitness=[]; dev_n=0
    with (OUT/'retokenized-manifest.check.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['audit_id','source','split','family_id','content_tokens','targets_with_eos']);writer.writeheader()
        for r in rows:
            text=con.execute('select text from docs where id=?',(int(r['audit_id']),)).fetchone()[0]
            if hashlib.sha256(text.encode()).hexdigest()!=r['original_text_sha256']:raise ValueError('Corpus text mismatch')
            ids=tok.encode(text)
            if tok.decode(ids)!=text:raise ValueError('Corpus roundtrip')
            k=r['split']; c=counts.setdefault(k,{'documents':0,'content_tokens':0,'targets_with_eos':0})
            c['documents']+=1;c['content_tokens']+=len(ids);c['targets_with_eos']+=len(ids)+1
            writer.writerow({**{k:r[k] for k in ['audit_id','source','split','family_id']},'content_tokens':len(ids),'targets_with_eos':len(ids)+1})
            if r['split']=='development' and r['source']=='TinyStories' and dev_n<1000:
                fitness.append((len(ids)/len(text.split()),len(text.encode()),len(ids)));dev_n+=1
    checked=OUT/'retokenized-manifest.check.csv'; original=OUT/'retokenized-manifest.csv'
    if original.exists():
        if sha(checked)!=sha(original):raise ValueError('Retokenized manifest changed')
        checked.unlink()
    else:checked.rename(original)
    if len(fitness)!=1000:raise ValueError('Insufficient narrative development supply')
    ratios=[a for a,b,c in fitness]
    metrics={'documents':len(fitness),'median_tokens_per_word':float(np.median(ratios)),'p95_tokens_per_word':float(np.percentile(ratios,95)),'bytes_per_token':sum(b for a,b,c in fitness)/sum(c for a,b,c in fitness)}
    passed=metrics['documents']==1000 and metrics['median_tokens_per_word']<=1.6 and metrics['p95_tokens_per_word']<=2.5 and metrics['bytes_per_token']>=3
    receipt={'status':'PASS' if passed else 'FAIL','scope':'M1 tokenizer only; not neural training or M3 tokenizer selection','fit_bytes':nbytes,'fit_documents':len(selected),'integrity_cases':10000,'invalid_unicode_rejected':True,'splits':counts,'narrative_dev_fitness':metrics,'tokenizer_manifest_sha256':sha(target/'manifest.json'),'retokenized_manifest_sha256':sha(OUT/'retokenized-manifest.csv'),'elapsed_seconds':time.time()-started,'actual_m1_target_cap':min(48000000,3*counts['train']['targets_with_eos']),'weights_initialized':False}
    (OUT/'tokenizer-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2),flush=True)
if __name__=='__main__':main()
