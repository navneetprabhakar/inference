"""Combined evaluation family/provenance and cross-suite lexical audit; no scoring."""
import collections,csv,hashlib,json,sqlite3
from pathlib import Path
from slm.restart.edu_filter import normalized
O=Path(__file__).resolve().parent;R=O.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
    source={r['audit_id']:r for r in csv.DictReader(manifest.open())};family_splits=collections.defaultdict(set)
    for r in source.values():family_splits[r['family_id']].add(r['split'])
    collisions={k:sorted(v) for k,v in family_splits.items() if len(v)>1}
    assert not collisions,collisions
    db=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    files={};patterns=[];controls=0;counts=collections.Counter();ids=set();copyfamilies=set();evidence={}
    def read(rel,receipt,key):
        path=O/rel;digest=sha(path);assert digest==receipt[key][path.name],rel
        files[rel]=digest;return [json.loads(x) for x in path.read_text().splitlines()]
    def add(id,split,suite,kind,text):
        norm=normalized(text);words=norm.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)}
        assert grams
        patterns.append(dict(id=id,split=split,suite=suite,kind=kind,norm=norm,grams=grams))
    def artifact(rel):
        p=O/rel;evidence[rel]=sha(p);return json.loads(p.read_text())
    grammar=artifact('grammar-v2-screen.json');grounded=artifact('grounded-v3-verification.json')
    narrative=artifact('authored-narratives-v2/verification.json');copy=artifact('copy-probes-v2/receipt.json')
    copyverify=artifact('copy-probes-v2/verification.json');copyreview=artifact('copy-probes-v2/protection-review.json')
    assert copyreview['audit_sha256']==sha(O/'copy-probes-v2/protection-audit.json')
    assert copyverify['unexpected_match_count']==0
    for split in ['development','final']:
        for suite,rel,receipt,key in [
          ('grammar',split+'-grammar-v2-candidates.jsonl',grammar,'input_sha256'),
          ('grounded',split+'-grounded-v3-candidates.jsonl',grounded,'inputs_sha256'),
          ('narrative','authored-narratives-v2/'+split+'-narrative.jsonl',narrative,'input_sha256'),
          ('copy','copy-probes-v2/'+split+'-copy-pairs.jsonl',copy,'files_sha256')]:
            rows=read(rel,receipt,key);counts[split+':'+suite]=len(rows)
            assert len(rows)==(200 if suite=='grammar' else 100)
            byid={r.get('id',r.get('pair_id')):r for r in rows};assert len(byid)==len(rows)
            for row in rows:
                ident=row.get('id',row.get('pair_id'));assert ident not in ids;ids.add(ident)
                if suite=='grammar':
                    for i,text in enumerate(row['alternatives']):add(ident,split,suite,str(i),text)
                elif suite=='grounded':
                    add(ident,split,suite,'passage',row['passage'])
                    c=row['controls'];donor=byid[c['shuffled_source_id']]
                    assert donor['id']!=ident and donor['split']==split
                    assert c['shuffled_prompt']==donor['passage']+'\nQuestion: '+row['question']+'\nAnswer:'
                    controls+=1
                elif suite=='narrative':add(ident,split,suite,'prefix',row['prefix'])
                else:
                    for role in ['training','heldout']:
                        r=row[role];original=source[r['audit_id']]
                        assert r['family_id']==original['family_id'] and r['family_id'] not in copyfamilies
                        copyfamilies.add(r['family_id'])
                        assert r['split']==('train' if role=='training' else ('development' if split=='development' else 'test'))
                        text=db.execute('SELECT text FROM docs WHERE id=?',(int(r['audit_id']),)).fetchone()[0]
                        assert hashlib.sha256(text.encode()).hexdigest()==r['original_text_sha256']==original['original_text_sha256']
                        add(ident+':'+role,split,suite,'full_source',text)
    # All cross-suite pairs, and all opposite-split pairs within a suite.
    # Same-suite/same-split variants deliberately share templates and are not independent.
    index=collections.defaultdict(set);hits=[];compared=set()
    for i,p in enumerate(patterns):
        candidates=collections.Counter()
        for g in p['grams']:
            for j in index.get(g,()):candidates[j]+=1
        for j,n in candidates.items():
            q=patterns[j]
            if p['suite']==q['suite'] and p['split']==q['split']:continue
            compared.add((j,i));a=n/len(p['grams']);b=n/len(q['grams'])
            exact=(' '+p['norm']+' ') in (' '+q['norm']+' ') or (' '+q['norm']+' ') in (' '+p['norm']+' ')
            if exact or a>=.8 or b>=.8:
                hits.append(dict(left=q['id'],left_kind=q['kind'],right=p['id'],right_kind=p['kind'],left_suite=q['suite'],right_suite=p['suite'],left_split=q['split'],right_split=p['split'],exact_containment=exact,left_fraction=b,right_fraction=a))
        for g in p['grams']:index[g].add(i)
    result=dict(status='REVIEW_REQUIRED' if hits else 'SCOPED_COMBINED_AUDIT_PASS',files_sha256=files,evidence_sha256=evidence,source_manifest_sha256=sha(manifest),source_documents=len(source),source_families=len(family_splits),cross_split_source_family_collisions=collisions,copy_families=len(copyfamilies),same_split_control_lineages_verified=controls,counts=dict(counts),text_units=len(patterns),candidate_comparisons=len(compared),hits=hits,threshold='Bidirectional normalized containment or >=80% distinct word-fivegram containment; all cross-suite and opposite-split comparisons.',limitations=['Grammar variants within a split share frames; grounding variants and narrative name substitutions also share frames. Denominators do not imply independent scenarios.','Generic grounded answer-only text and empty prompts are not semantic ancestry evidence; passages and same-split control lineage are checked.','Copy training sources are intentional diagnostics; no extra training exposure permitted.','Known source-family separation and lexical screening cannot establish unknown upstream or semantic paraphrase ancestry.','This does not freeze files, enforce worker access, or authorize training.'])
    (O/'combined-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['files_sha256','evidence_sha256','hits']}|{'hit_count':len(hits)},indent=2))
if __name__=='__main__':main()
