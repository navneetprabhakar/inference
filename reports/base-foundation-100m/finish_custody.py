"""Add prior foundation validation domain-family exclusions to frozen custody."""
import importlib.util
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('base_corpus_builder',Path(__file__).with_name('build.py'))
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
DATA=ROOT/'data/base-foundation-100m'

def main():
    receipt=json.loads((DATA/'custody.json').read_text())
    assert receipt['state']=='cleared'
    assert builder.checksum(DATA/'candidates.sqlite')==receipt['candidate_database_sha256']
    families=set();indexes={};without_url=set()
    domains=builder.Domains()
    for name in ('feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3','balanced-continuation-v1'):
        path=ROOT/'data'/name/'documents.jsonl'
        if not path.exists():continue
        indexes[str(path.relative_to(ROOT))]=builder.checksum(path)
        for line in path.open():
            row=json.loads(line)
            if row.get('split') not in ('validation','val','dev'):continue
            url=row.get('book_url') or row.get('canonical_url') or row.get('source_url') or row.get('group','')
            if 'wikipedia.org/' in url and not url.startswith('http'):url='https://'+url
            domain,_=domains.canonical(url)
            if domain:families.add(domain)
            else:without_url.add(row.get('source','unknown'))
    conn=sqlite3.connect(f'file:{DATA/"candidates.sqlite"}?mode=ro',uri=True)
    excluded=[doc for doc,domain in conn.execute('SELECT doc_id,domain FROM documents') if domain in families]
    conn.close()
    extra=dict(previous_document_indexes=indexes,excluded_domain_families=sorted(families),
               excluded_doc_ids=excluded,sources_without_domain=sorted(without_url),
               method='Exclude domain families from prior foundation validation; earlier staging also rejects recorded exact normalized hashes. This does not establish absence of paraphrases or mirrors.')
    builder.write_json(DATA/'prior-validation-custody.json',extra)
    builder.write_json(DATA/'conversation-custody.json',receipt)
    receipt['excluded_doc_ids']=sorted(set(receipt['excluded_doc_ids'])|set(excluded))
    receipt['prior_foundation_validation']=dict(receipt_sha256=builder.checksum(DATA/'prior-validation-custody.json'),
                                               domains=sorted(families),candidate_exclusions=len(excluded),
                                               sources_without_domain=sorted(without_url))
    receipt['counts']['total_unique_excluded']=len(receipt['excluded_doc_ids'])
    builder.write_json(DATA/'custody.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='excluded_doc_ids'},indent=2))

if __name__=='__main__':main()
