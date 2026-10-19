"""Check every story/measurement join, heldout families and sampled BPE counts."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.prose_screen import word_key
from slm.data.schema import digest
from slm.data.tokenized import sha

root=Path('data/tinystories-range-intake-v1');out=Path('data/tinystories-characterization-v1')
report=json.loads((out/'report.json').read_text());plan=json.loads((out/'plan.json').read_text())
assert report['plan_sha256']==sha('configs/tinystories-characterization-v1.json')
for p,h in plan['input_bindings'].items():assert sha(p)==h
assert sha(out/'measurements.jsonl')==report['measurements_sha256']
assert sha(out/'upstream-protection.json')==report['protection_sha256']
protection=json.loads((out/'upstream-protection.json').read_text());heldouts={};counts=Counter();tokens=Counter();index=0;sampled=0;overlaps=0
bpe=BPE.load(plan['tokenizer']);intake=json.loads((root/'report.json').read_text())
with (out/'measurements.jsonl').open() as measurements:
    for item in intake['requests']:
        request=item['request'];kind=request['kind']
        if kind=='evaluation_prompts':continue
        path=root/'cache'/(digest('records/'+request['key'])+'.bin')
        assert sha(path)==item['records_sha256']
        for line in path.read_bytes().splitlines():
            r=json.loads(line);m=json.loads(next(measurements));text=r['row']['text'];key=digest(word_key(text))
            assert m['file']==r['file'] and m['start']==r['row']['start'] and m['kind']==kind
            assert m['normalized_text_sha256']==key and m['raw_text_sha256']==r['row']['raw_text_sha256']
            assert m['training_approved'] is False and type(m['content_tokens']) is int and m['content_tokens']>0
            if index%101==0:
                assert len(bpe.encode(text))==m['content_tokens'];sampled+=1
            if kind=='official_validation':heldouts.setdefault(key,[]).append(dict(file=r['file'],start=r['row']['start']))
            else:
                assert m['official_heldout_exact']==(key in protection['normalized_validation_families'])
                overlaps+=m['official_heldout_exact']
            counts[request['key']]+=1;tokens[request['key']]+=m['content_tokens'];index+=1
        assert counts[request['key']]==report['totals'][request['key']]['records']
        assert tokens[request['key']]==report['totals'][request['key']]['content_tokens']
    assert measurements.read()==''
assert heldouts==protection['normalized_validation_families']
assert len(heldouts)==report['official_validation_distinct_normalized_families']
assert len(protection['prompts'])==report['published_evaluation_prompts']
assert overlaps==report['train_isolation_hits']['upstream_validation_exact']
result=dict(creator='Navneet Prabhakar',kind='actual-narrative-characterization-check-v1',passed=True,
    report_sha256=sha(out/'report.json'),all_source_measurement_joins=index,sampled_bpe_counts_reencoded=sampled,
    official_validation_exact_train_overlap=overlaps,training_approved=False,model_updates=0,
    scope='Every source/measurement identity, normalized heldout family and per-range count/token-sum checked; BPE re-encoding is systematic sample only. Content/privacy/language/global near grouping/admission remain open.')
Path('reports/tinystories-characterization-check.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2))
