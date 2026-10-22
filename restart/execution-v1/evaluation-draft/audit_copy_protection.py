"""Read-only bidirectional lexical audit of copying contexts and references."""
import collections,csv,hashlib,json,sqlite3
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.restart.edu_filter import normalized
O=Path(__file__).resolve().parent;R=O.parents[2];D=O/'copy-probes-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def grams(text):
    w=text.split();return {tuple(w[i:i+5]) for i in range(len(w)-4)}
def main():
    receipt=json.loads((D/'receipt.json').read_text());tok=BPE.load(O.parent/'tokenizer-8192')
    assert sha(O.parent/'tokenizer-8192/manifest.json')==receipt['tokenizer_manifest_sha256']
    db=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    probes=[];files={};families=set()
    for split in ['development','final']:
        p=D/(split+'-copy-pairs.jsonl');files[p.name]=sha(p);assert files[p.name]==receipt['files_sha256'][p.name]
        rows=[json.loads(x) for x in p.read_text().splitlines()];assert len(rows)==100
        for pair in rows:
            for role in ['training','heldout']:
                r=pair[role];assert r['family_id'] not in families;families.add(r['family_id'])
                original=db.execute('SELECT text FROM docs WHERE id=?',(int(r['audit_id']),)).fetchone()[0]
                assert hashlib.sha256(original.encode()).hexdigest()==r['original_text_sha256']
                encoded=tok.encode(original);assert encoded[:64]==r['prefix_token_ids'] and encoded[64:128]==r['expected_next_64_token_ids']
                # Decode the combined window to avoid isolated UTF-8 token boundaries.
                text=tok.decode(encoded[:128]);assert '\ufffd' not in text
                probes.append(dict(id=pair['pair_id']+':'+role,split=split,role=role,audit_id=r['audit_id'],family=r['family_id'],norm=normalized(text),full=normalized(original)))
    protected=[dict(id=str(k),norm=n,origin=o) for k,n,o in db.execute('SELECT id,normalized,origin FROM protections')]
    # Index all protections; both short contained exclusions and long source-like matches count.
    index=collections.defaultdict(set)
    for i,p in enumerate(protected):
        p['grams']=grams(p['norm'])
        for g in p['grams']:index[g].add(i)
    hits=[];short=[p for p in protected if not p['grams']]
    for p in probes:
        for scope in ['norm','full']:
            g=grams(p[scope]);c=collections.Counter()
            for x in g:
                for i in index.get(x,()):c[i]+=1
            for i,n in c.items():
                q=protected[i];a=(' '+p[scope]+' ') in (' '+q['norm']+' ');b=(' '+q['norm']+' ') in (' '+p[scope]+' ')
                pf=n/len(g);qf=n/len(q['grams'])
                if a or b or pf>=.8 or qf>=.8:hits.append(dict(probe=p['id'],audit_id=p['audit_id'],scope=scope,protection_id=q['id'],origin=q['origin'],probe_contained=a,protection_contained=b,probe_fivegram_fraction=pf,protection_fivegram_fraction=qf))
            for q in short:
                if (' '+q['norm']+' ') in (' '+p[scope]+' '):hits.append(dict(probe=p['id'],audit_id=p['audit_id'],scope=scope,protection_id=q['id'],origin=q['origin'],protection_contained=True))
    cross=[]
    for p in probes:
        if p['split']!='development':continue
        for q in probes:
            if q['split']!='final':continue
            for scope in ['norm','full']:
                a,b=grams(p[scope]),grams(q[scope]);n=len(a&b)
                exact=(' '+p[scope]+' ') in (' '+q[scope]+' ') or (' '+q[scope]+' ') in (' '+p[scope]+' ')
                if exact or n/len(a)>=.8 or n/len(b)>=.8:cross.append(dict(development=p['id'],final=q['id'],scope=scope,exact_containment=exact,development_fivegram_fraction=n/len(a),final_fivegram_fraction=n/len(b)))
    result=dict(status='REVIEW_REQUIRED' if hits or cross else 'SCOPED_LEXICAL_PASS',files_sha256=files,probes=len(probes),distinct_families=len(families),protection_records=len(protected),protection_hits=hits,cross_split_hits=cross,scope='Both 128-token context+reference windows and full originals checked against protections and opposite copy split. Exact bidirectional normalized containment or >=80% distinct fivegrams in either direction. Short protections below five words use containment.',limitations=['Lexical candidates require semantic review; short/common protections can be false positives.','No exhaustive semantic ancestry proof or combined authored-suite certification.','No model outputs or corpus modifications.'])
    (D/'protection-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['protection_hits','cross_split_hits']}|{'protection_hit_count':len(hits),'cross_split_hit_count':len(cross)},indent=2))
if __name__=='__main__':main()
