"""Project verified fresh broad text into trainer records without granting admission."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from tokenizer import ASSETS
from own_base_language_streams import pinned, sha, verify_custody

ROOT = Path(__file__).resolve().parent
D = ROOT/'data/fresh-broad-packed-v1'


def pin(p): return dict(path=str(p.resolve()), sha256=sha(p))


def main():
    start=time.monotonic()
    output=D/'language-manifest.json'; receipt=D/'language-manifest-verification.json'
    assert not output.exists() and not receipt.exists()
    proof_pin=pin(D/'independent-verification.json'); packing_pin=pin(D/'manifest.json')
    proof=pinned(proof_pin); packing=pinned(packing_pin)
    assert proof['state']=='PASS_full_packed_span_replay_not_admitted' and proof['training_admitted'] is False
    assert proof['manifest_sha256']==packing_pin['sha256'] and proof['checked_documents']==sum(s['documents'] for s in packing['shards'].values())
    source=packing
    custody=[dict(kind='fresh_broad_score4_v1',pin=packing_pin)]
    denied=verify_custody(custody,source['candidate_database_sha256'])
    assert sha(D/'documents.jsonl')==packing['documents_sha256']
    quality=pin(ROOT/'reports/fresh-broad-intake-v1/quality-score-review.json')
    documents=[]; files=[]; counts={}; seen=set()
    indexed=[json.loads(line) for line in (D/'documents.jsonl').open()]
    for split in ('train','validation'):
        entry=packing['shards'][split]; path=D/entry['file']
        assert path.stat().st_size==2*entry['tokens'] and sha(path)==entry['sha256']
        offset=count=0
        with path.open('rb') as stream:
            for d in indexed:
                if d['split']!=split: continue
                assert time.monotonic()-start<600 and not (ROOT/'runs/STOP').exists() and not (D/'STOP').exists()
                assert d['document_id'] not in denied and d['document_id'] not in seen
                assert d['offset']==offset and d['file']==entry['file']
                raw=stream.read(2*d['tokens'])
                assert len(raw)==2*d['tokens'] and hashlib.sha256(raw).hexdigest()==d['token_sha256']
                seen.add(d['document_id'])
                documents.append(dict(id=d['document_id'],original_id=d['document_id'],file=d['file'],
                                      offset=offset,tokens=d['tokens'],family='fineweb-domain:'+d['group'],split=split,
                                      sha256=d['token_sha256'],text_sha256=d['raw_sha256']))
                offset+=d['tokens'];count+=1
            assert not stream.read(1)
        assert offset==entry['tokens'] and count==entry['documents']
        files.append(dict(file=entry['file'],split=split,tokens=offset,sha256=entry['sha256']))
        counts[split]=dict(documents=count,tokens=offset)
    for key in ('family','text_sha256'):
        assert not {d[key] for d in documents if d['split']=='train'} & {d[key] for d in documents if d['split']=='validation'}
    assert shutil.disk_usage(ROOT).free>20*1024**3
    pinned(proof_pin);pinned(packing_pin)
    manifest=dict(schema=1,state='packed_pending_training_admission',name='fresh_broad',
                  tokenizer=dict(vocabulary=50257,eot=50256,identity=ASSETS),
                  candidate_sha256=source['candidate_database_sha256'],custody_receipts=custody,
                  quality_policy=quality,files=files,documents=documents,counts=counts)
    with output.open('x') as f:json.dump(manifest,f,separators=(',',':'));f.write('\n')
    verification=dict(state='PASS_canonical_manifest_projection',manifest_sha256=sha(output),failures=[],
                      excluded_ids_absent=True,full_document_tokens_verified=True,underlying_packing_proof=proof_pin,
                      underlying_packing_manifest=packing_pin,counts=counts,training_admitted=False,
                      mapping_scope='Every record and token span mapped from independently retokenized fresh source text; historical/public custody and quality-domain exclusions enforced. No capability claim.',
                      code_sha256={n:sha(ROOT/n) for n in ('prepare_fresh_broad_language_manifest.py','own_base_language_streams.py')},
                      seconds=time.monotonic()-start)
    with receipt.open('x') as f:json.dump(verification,f,indent=2);f.write('\n')
    print(json.dumps(dict(state=verification['state'],counts=counts,seconds=verification['seconds'])))


if __name__=='__main__':main()
