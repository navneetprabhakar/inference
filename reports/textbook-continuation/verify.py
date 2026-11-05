"""Verify shard boundaries, prior-scope identity, source membership and train/validation separation."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import numpy as np
from local import ROOT,HERE,file_hash,split,h,norm,family,jsonrows
from tokenizer import load
def main():
    import sys
    tgt=Path(sys.argv[1]);manifest=json.loads((tgt/'manifest.json').read_text())
    assert file_hash(tgt/'documents.jsonl')==manifest['documents_sha256']
    prior_docs=set();prior_hashes=set();prior_wiki=set()
    for source in ['feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3']:
        for r in jsonrows(ROOT/'data'/source/'documents.jsonl'):
            prior_docs.add(r['document_id']);prior_hashes.add(r['normalized_sha256'])
            if r['source']=='wiki':prior_wiki.add(family(r.get('title',r['group'].split('/wiki/')[-1])))
    rows=list(jsonrows(tgt/'documents.jsonl'))
    assert len(rows)==len({r['document_id'] for r in rows})==len({r['normalized_sha256'] for r in rows})
    assert not {r['normalized_sha256'] for r in rows}&prior_hashes
    assert not {r['document_id'] for r in rows}&prior_docs
    groups=defaultdict(set);sources=Counter();titles=Counter()
    tok=load()
    for key,info in manifest['shards'].items():
        p=tgt/(key+'.u16')
        assert file_hash(p)==info['sha256'] and p.stat().st_size==info['tokens']*2
        data=np.memmap(p,mode='r',dtype='<u2')
        n=0
        for r in rows:
            if r['source']+'-'+r['split']!=key:continue
            assert n==r['offset'] and r['split']==split(r['source'],r['group'])
            ids=data[n:n+r['tokens']];n+=len(ids)
            assert ids[-1]==50256 and 50256 not in ids[:-1] and int(ids.max())==50256
            assert r['normalized_sha256']==h(norm(tok.decode(ids[:-1].tolist())))
            groups[r['split']].add((r['source'],r['group']))
            if r['source']=='wiki':assert r['group'] not in prior_wiki
            if r['source']=='stories':assert r['source_row']>=22500
            if r['source']=='textbook':titles[(r['book'],r['split'])]+=r['tokens']
            sources[key]+=r['tokens']
        assert n==info['tokens']
    assert not groups['train']&groups['validation']
    result=dict(manifest_sha256=file_hash(tgt/'manifest.json'),verified_documents=len(rows),prior_index_docs=len(prior_docs),
              equal_prior_source_ids=0,equal_prior_normalized_documents=0,source_group_overlap=0,
              eligible_input_positions=sources,token_positions_by_book_and_split={k+' '+s:v for (k,s),v in titles.items()},
              training_positions=sum(v for k,v in sources.items() if k.endswith('-train')),
              license_scope='personal noncommercial research only; book titles, exceptions, source URLs and archive terms recorded')
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
