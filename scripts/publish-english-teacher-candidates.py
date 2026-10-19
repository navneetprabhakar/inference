"""Reconstruct all actual teacher candidates, direct reviews and continuation-only tokens."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import sqlite3
from slm.common.tokenizer import BPE
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.teacher.english_continuations import compose

ROOT=Path('data/english-teacher-20call-v1').resolve()
OUT=Path('data/english-teacher-candidates-v2').resolve()


class ReadOnlyCache:
    def __init__(self,path):self.path=Path(path)
    def cached(self,key):
        db=sqlite3.connect('file:'+str(self.path.resolve())+'?mode=ro',uri=True)
        try:row=db.execute('SELECT status,response,response_hash FROM requests WHERE key=?',(key,)).fetchone()
        finally:db.close()
        if row is None or row[0]!='complete':raise ValueError('Actual completed response required')
        raw=json.loads(row[1])
        if digest(raw)!=row[2]:raise ValueError('Original cache response hash differs')
        return raw


def inspect():
    plan=json.loads((ROOT/'plan.json').read_text())
    if plan['root']!=str(ROOT) or sha(ROOT/'plan.json')!=json.loads((ROOT/'freeze.json').read_text())['plan_sha256']:
        raise ValueError('Frozen actual pilot required')
    bindings={**plan['bindings'],**plan['historical_journals'],str(ROOT/'batches.json'):plan['batches_sha256']}
    for p,h in bindings.items():
        if sha(p)!=h:raise ValueError('Original pilot input changed: '+p)
    review_path=ROOT/'direct-review.jsonl';reviews=[json.loads(x) for x in review_path.read_text().splitlines()]
    if len(reviews)!=182 or len({r['scenario_id'] for r in reviews})!=182:raise ValueError('All182actual direct review decisions required')
    review={r['scenario_id']:r for r in reviews}
    registry=Path('configs/next-iteration-training-plan-v1.json');cfg=json.loads(registry.read_text())['checkpoint_registry']['language_phase_source']
    tokenizer_path=Path(cfg['tokenizer_path']);tokenizer_hash=cfg['tokenizer_manifest_sha256']
    if sha(tokenizer_path/'manifest.json')!=tokenizer_hash:raise ValueError('Bound production tokenizer required')
    tokenizer=BPE.load(tokenizer_path)
    journal=ReadOnlyCache(ROOT/'journal.sqlite');db=sqlite3.connect('file:'+str(journal.path)+'?mode=ro',uri=True)
    try:
        budget=db.execute('SELECT cap,authorization,halted,max_requests FROM budget').fetchall()
        states=dict(db.execute('SELECT status,COUNT(*) FROM requests GROUP BY status').fetchall())
    finally:db.close()
    if budget!=[(0,plan['authorization']['authorization_id'],0,20)] or states!={'complete':20}:
        raise ValueError('Exact20completed calls and unchanged allowance required')
    candidates=[];usage=Counter();record_bindings={};families=Counter();styles=Counter();exact=0
    records=sorted((ROOT/'records').glob('*.json'))
    if [p.name for p in records]!=[f'{i:02d}.json' for i in range(20)]:raise ValueError('Complete20record sequence required')
    keys=set()
    for path in records:
        record=json.loads(path.read_text());record_bindings[str(path)]=sha(path)
        if record['plan_sha256']!=sha(ROOT/'plan.json') or record['request_key'] in keys:raise ValueError('Unique original planned generations required')
        keys.add(record['request_key']);usage.update(record['usage'])
        rows=compose(record,journal,EvaluationExclusions(plan['evaluation_inventory'],plan['evaluation_inventory_sha256']),tokenizer,
                     tokenizer_sha256=tokenizer_hash,capture_base=ROOT/'captures')
        for row,scenario,result in zip(rows,record['request']['batch'],record['results'],strict=True):
            r=review[row['scenario_id']]
            if (r['record_sha256']!=sha(path) or r['context_sha256']!=digest(scenario['context'])
                    or r['reply_sha256']!=digest(result['reply']) or r['human_attestation'] is not False
                    or r['training_approved'] is not False or r['decision'] not in ('consider','exclude','defer')):
                raise ValueError('Actual direct-review identity differs')
            if r['decision']=='consider' and not (r['meaning_passed'] and r['style_passed'] and r['content_passed'] and row['automated_passed']):
                raise ValueError('False-gate consideration refused')
            row['direct_quality_decision']=r['decision'];row['direct_review_sha256']=digest(r)
            candidates.append(row);families[row['family_id']]+=1;styles[row['style']]+=1
            exact+=int('exact_reply_oracle' in result['checks'] and result['checks']['exact_reply_oracle'])
    accepted=[r for r in candidates if r['direct_quality_decision']=='consider']
    duplicates=Counter(r['messages'][-1]['content'] for r in accepted)
    long_duplicates={text:n for text,n in duplicates.items() if n>1 and len(text.split())>8}
    summary=dict(creator='Navneet Prabhakar',kind='actual-english-teacher-pilot-v1',complete=True,
        additional_cli_calls=20,historical_reserved_calls=20,total_historical_plus_new=40,
        candidate_instances=len(candidates),semantic_template_families=len(families),style_counts=dict(styles),
        direct_quality_decisions=dict(Counter(r['direct_quality_decision'] for r in candidates)),
        automated_passes=sum(r['automated_passed'] for r in candidates),exact_reply_oracle_passes=exact,
        direct_meaning_style_content_passes=len(accepted),direct_reviewer_authority='delegated_expert',human_attestation=False,
        usage=dict(usage),requested_model='gpt-6.1-sol',resolved_model=None,model_substitution_used=False,
        platform_api_calls=0,settled_cli_cost_usd=None,remaining_additional_calls=0,
        prepared_positions_all_one_pass=sum(r['physical_positions'] for r in candidates),
        prepared_assistant_targets_all_one_pass=sum(r['assistant_targets'] for r in candidates),
        considered_positions_one_pass=sum(r['physical_positions'] for r in accepted),
        considered_assistant_targets_one_pass=sum(r['assistant_targets'] for r in accepted),
        unique_considered_answer_texts=len(duplicates),repeated_long_answer_groups=len(long_duplicates),
        largest_exact_long_answer_repeat=max(long_duplicates.values(),default=1),
        candidate_style_control_verified=True,continuation_only_masks_verified=True,raw_cli_capture_replayed=True,
        tokenizer_manifest_sha256=tokenizer_hash,pilot_plan_sha256=sha(ROOT/'plan.json'),
        direct_review_sha256=sha(review_path),journal_sha256=sha(journal.path),
        record_bindings=record_bindings,publisher_sha256=sha(__file__),adapter_sha256=sha('src/slm/teacher/english_continuations.py'),
        student_gradient_updates=0,training_approved=False,source_evidence_complete=False,
        scope='Quality-considered teacher seeds only. No training release, student improvement, broad independent task coverage or resolved backend identity. Prior assistant context is input only; explicit host style controls are added without rewriting teacher text.')
    if sha(tokenizer_path/'manifest.json')!=tokenizer_hash:raise ValueError('Tokenizer changed during composition')
    return candidates,summary


def main(check=False):
    candidates,summary=inspect()
    if check:
        if json.loads((OUT/'report.json').read_text())!=summary:raise ValueError('Published report differs')
        rows=[json.loads(x) for x in (OUT/'candidates.jsonl').read_text().splitlines()]
        if rows!=candidates:raise ValueError('Published candidate content differs')
        print(json.dumps(dict(actual182_candidates_reconstructed=True,all20_captures_replayed=True,training_approved=False)));return
    if OUT.exists():raise FileExistsError('Preserve prior candidate output')
    OUT.mkdir()
    with (OUT/'candidates.jsonl').open('x') as stream:
        for row in candidates:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    (OUT/'report.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    Path('reports/english-teacher-pilot.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='record_bindings'},indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args();main(args.check)
