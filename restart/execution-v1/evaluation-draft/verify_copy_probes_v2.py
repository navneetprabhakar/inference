"""Independent source/token checks and training-overlap screen for 64-token probes."""
import collections,csv,hashlib,json,sqlite3
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.restart.edu_filter import normalized
O=Path(__file__).resolve().parent;D=O/'copy-probes-v2';R=O.parents[2];TOK=BPE.load(O.parent/'tokenizer-8192')

def main():
    receipt=json.loads((D/'receipt.json').read_text())
    manifest=R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
    assert hashlib.sha256(manifest.read_bytes()).hexdigest()==receipt['source_manifest_sha256']
    assert hashlib.sha256((O.parent/'tokenizer-8192/manifest.json').read_bytes()).hexdigest()==receipt['tokenizer_manifest_sha256']
    source={r['audit_id']:r for r in csv.DictReader(manifest.open())}
    db=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    families=set();patterns=[];index=collections.defaultdict(set);counts=collections.Counter()
    def verify(row,kind,evaluation_split):
        original=source[row['audit_id']]
        for field in ['source','split','family_id','original_text_sha256','normalized_sha256']:assert row[field]==original[field]
        assert row['family_id'] not in families;families.add(row['family_id'])
        expected='train' if kind=='training_copy' else ('development' if evaluation_split=='development' else 'test')
        assert row['split']==expected and row['source']=='TinyStories'
        text=db.execute('SELECT text FROM docs WHERE id=?',(int(row['audit_id']),)).fetchone()[0]
        assert hashlib.sha256(text.encode()).hexdigest()==row['original_text_sha256']
        ids=TOK.encode(text);prefix_ids=TOK.encode(row['prefix'])
        assert prefix_ids==row['prefix_token_ids'] and ids[:len(prefix_ids)]==prefix_ids and text.startswith(row['prefix'])
        if kind.endswith('copy'):
            assert len(prefix_ids)==64 and len(row['expected_next_64_token_ids'])==64
            assert ids[64:128]==row['expected_next_64_token_ids'] and len(ids)==row['document_content_tokens']
        norm=normalized(row['prefix']);words=norm.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)}
        ix=len(patterns);patterns.append(dict(audit_id=row['audit_id'],family=row['family_id'],kind=kind,split=evaluation_split,norm=norm,grams=grams))
        for gram in grams:index[gram].add(ix)
        counts[kind]+=1
    for split in ['development','final']:
        for name in [split+'-copy-pairs.jsonl']:
            p=D/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['files_sha256'][name]
            rows=[json.loads(x) for x in p.read_text().splitlines()];assert len(rows)==100
            for pair in rows:
                assert pair['evaluation_split']==split
                assert pair['matching']=={'source':'TinyStories','prefix_tokens':64,'document_tokens':'exact','maximum_prefix_word_difference':2}
                t,h=pair['training'],pair['heldout']
                assert t['document_content_tokens']==h['document_content_tokens']
                assert abs(t['prefix_words']-h['prefix_words'])<=2
                assert t['prefix_words']==len(t['prefix'].split()) and h['prefix_words']==len(h['prefix'].split())
                verify(t,'training_copy',split);verify(h,'heldout_copy',split)
    train={int(k) for k,v in source.items() if v['split']=='train'};hits=[];expected_self=0;scanned=0
    for key,norm in db.execute('SELECT id,normalized FROM docs'):
        if key not in train:continue
        words=norm.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)};candidates=collections.Counter()
        for gram in grams:
            for ix in index.get(gram,()):candidates[ix]+=1
        for ix,shared in candidates.items():
            item=patterns[ix];exact=(' '+item['norm']+' ') in (' '+norm+' ')
            if not exact and shared/len(item['grams'])<.8:continue
            if item['kind']=='training_copy' and int(item['audit_id'])==key:
                assert exact;expected_self+=1;continue
            hits.append({'probe_audit_id':item['audit_id'],'kind':item['kind'],'evaluation_split':item['split'],'training_audit_id':key,'exact_prefix_containment':exact,'fivegram_fraction':shared/len(item['grams'])})
        scanned+=1
    assert expected_self==200
    result={'status':'SOURCE_VERIFIED_OVERLAP_REVIEW_REQUIRED' if hits else 'SOURCE_AND_LEXICAL_SCREEN_PASS','counts':dict(counts),'distinct_families':len(families),'training_documents_scanned':scanned,'intentional_training_self_matches':expected_self,'unexpected_match_count':len(hits),'hits':hits,'scope':'Original-prefix and token/reference verification plus normalized exact containment / >=80% distinct fivegram containment. Lexical hits need review; no ancestry certification or model scoring.'}
    (D/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='hits'},indent=2))
if __name__=='__main__':main()
