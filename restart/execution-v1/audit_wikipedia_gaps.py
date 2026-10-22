"""Measure a prospective gap screen on the frozen failed cohort; no admission."""
import collections,hashlib,json,sqlite3
from pathlib import Path
from slm.restart.text_gaps import find_gaps,VERSION
O=Path(__file__).resolve().parent;D=O/'m2-intake/wikipedia-prose-v1';OUT=O/'m2-intake/wikipedia-gap-audit-v1'
def main():
    if OUT.exists():raise FileExistsError('Audit already exists; preserve evidence')
    OUT.mkdir()
    db=sqlite3.connect(f'file:{D}/candidates.sqlite?mode=ro',uri=True)
    verification=json.loads((D/'verification.json').read_text())
    assert hashlib.sha256((D/'candidates.sqlite').read_bytes()).hexdigest()==verification['candidates_sha256']
    reviewed={x['row_index']:x for x in map(json.loads,(D/'uniform-judgments.jsonl').read_text().splitlines())}
    stats=collections.Counter();rules=collections.Counter();comparison=[]
    with (OUT/'findings.jsonl').open('x') as out:
        for idx,sid,text,tokens in db.execute('SELECT row_index,source_id,text,tokens FROM candidates ORDER BY row_index'):
            flags=find_gaps(text);stats['screened_documents']+=1;stats['screened_tokens']+=tokens
            if flags:
                stats['flagged_documents']+=1;stats['flagged_tokens']+=tokens
                rules.update({x['rule'] for x in flags})
                out.write(json.dumps({'row_index':idx,'source_id':sid,'findings':flags},ensure_ascii=False)+'\n')
            else:stats['remaining_documents']+=1;stats['remaining_tokens']+=tokens
            if idx in reviewed:
                r=reviewed[idx];comparison.append({'row_index':idx,'label':r['label'],'flagged':bool(flags),'rules':sorted({x['rule'] for x in flags})})
    result={'status':'DIAGNOSTIC_ONLY','detector':VERSION,'detector_sha256':hashlib.sha256((O.parents[1]/'src/slm/restart/text_gaps.py').read_bytes()).hexdigest(),'counts':dict(stats),'rule_document_counts':dict(rules),'reviewed_comparison':comparison,'known_failures_remaining':sum(x['label'] in ('fail','major') and not x['flagged'] for x in comparison),'known_pass_minor_flagged':sum(x['label'] in ('pass','minor') and x['flagged'] for x in comparison),'limitations':['Rules developed from the reviewed sample: comparison is in-sample diagnosis, not independent validation.','Flagged minor defects are intentionally rejected for a conservative prose cohort, not retroactively relabelled major failures.','Remaining documents still need fluency, semantic, factual, ancestry and rights review.','No missing content invented; no candidate admitted.'],'newly_admitted_documents':0}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='reviewed_comparison'},indent=2))
if __name__=='__main__':main()
