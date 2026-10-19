"""Measure acquired stories and retain explicit upstream evaluation protection."""
# Creator: Navneet Prabhakar
import hashlib
import json
from pathlib import Path
import yaml
from slm.common.tokenizer import BPE
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.prose_screen import RequestGuard, word_key
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/tinystories-range-intake-v1')
OUT=Path('data/tinystories-characterization-v1')
PLAN=Path('configs/tinystories-characterization-v1.json')


def main():
    if OUT.exists():raise FileExistsError('Characterization output already exists')
    plan=json.loads(PLAN.read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned characterization input changed')
    intake=json.loads((ROOT/'report.json').read_text())
    def raw(key):return (ROOT/'cache'/(digest(key)+'.bin')).read_bytes()
    prompts=yaml.safe_load(raw('body/evaluation-prompts').decode())
    if not isinstance(prompts,list) or not prompts or any(not isinstance(p,str) for p in prompts):raise ValueError('Expected upstream list of original prefixes')
    prefix_guard=RequestGuard(prompts)
    spec=json.loads(Path('configs/future-intake-evaluation-exclusions-v1.json').read_text())
    prior=EvaluationExclusions(spec['inventory'],spec['inventory_sha256'])
    bpe=BPE.load(plan['tokenizer']);heldouts={};train_seen=set();rows=[]
    for item in intake['requests']:
        request=item['request']
        if request['kind']!='official_validation':continue
        payload=raw('records/'+request['key'])
        if hashlib.sha256(payload).hexdigest()!=item['records_sha256']:raise ValueError('Heldout records changed')
        for line in payload.splitlines():
            row=json.loads(line);key=digest(word_key(row['row']['text']))
            heldouts.setdefault(key,[]).append(dict(file=row['file'],start=row['row']['start']))
    totals={};hits=dict(upstream_validation_exact=0,upstream_evaluation_prefix=0,prior_evaluation_text=0,train_normalized_duplicate_members=0)
    OUT.mkdir();(OUT/'plan.json').write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n')
    with (OUT/'measurements.jsonl').open('w') as out:
        for item in intake['requests']:
            request=item['request'];kind=request['kind']
            if kind=='evaluation_prompts':continue
            payload=raw('records/'+request['key'])
            if hashlib.sha256(payload).hexdigest()!=item['records_sha256']:raise ValueError('Source records changed')
            count=0;tokens=0
            for line in payload.splitlines():
                row=json.loads(line);text=row['row']['text'];key=digest(word_key(text));n=len(bpe.encode(text));tokens+=n;count+=1
                old_hits=prior.guard.matches(text);prefix_hits=prefix_guard.matches(text)
                inherited=key in heldouts if kind=='train_range' else False
                duplicate=(key in train_seen) if kind=='train_range' else False
                if kind=='train_range':
                    train_seen.add(key);hits['upstream_validation_exact']+=inherited
                    hits['upstream_evaluation_prefix']+=bool(prefix_hits);hits['prior_evaluation_text']+=bool(old_hits)
                    hits['train_normalized_duplicate_members']+=duplicate
                measurement=dict(file=row['file'],start=row['row']['start'],raw_text_sha256=row['row']['raw_text_sha256'],
                    normalized_text_sha256=key,content_tokens=n,kind=kind,official_heldout_exact=inherited,
                    upstream_prefix_hits=prefix_hits,prior_evaluation_hits=old_hits,training_approved=False)
                out.write(json.dumps(measurement,sort_keys=True)+'\n')
            totals[request['key']]=dict(kind=kind,records=count,content_tokens=tokens)
            print(json.dumps(dict(range=request['key'],records=count,content_tokens=tokens)),flush=True)
    protection=dict(creator='Navneet Prabhakar',kind='upstream-narrative-protection-v1',training_approved=False,
        normalized_validation_families=heldouts,prompts=[dict(text=p,origin='Evaluation prompts.yaml:'+str(i)) for i,p in enumerate(prompts)],
        scope='Both official validation files preserved; full normalized story equality plus whole published evaluation-prefix sequences. Near variants require subsequent global grouping. Not an independent new benchmark.')
    (OUT/'upstream-protection.json').write_text(json.dumps(protection,sort_keys=True)+'\n')
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned characterization input changed during use')
    report=dict(creator='Navneet Prabhakar',kind='actual-narrative-characterization-v1',complete=True,plan_sha256=sha(PLAN),
        totals=totals,train_content_token_occurrences=sum(r['content_tokens'] for r in totals.values() if r['kind']=='train_range'),
        validation_content_token_occurrences=sum(r['content_tokens'] for r in totals.values() if r['kind']=='official_validation'),
        official_validation_distinct_normalized_families=len(heldouts),published_evaluation_prompts=len(prompts),
        train_isolation_hits=hits,measurements_sha256=sha(OUT/'measurements.jsonl'),protection_sha256=sha(OUT/'upstream-protection.json'),
        model_updates=0,teacher_calls=0,cloud_spend=0,training_approved=False,
        scope='Raw story BPE sizing and exact evaluation-family/prefix signals only. Prior483-text guard pinned and hashed before/after the read-only job, with its immutable matcher reused in memory. No language/privacy/content screening, cross-source near-family independence, source admission or useful learning claim.')
    (OUT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    Path('reports/tinystories-characterization.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
