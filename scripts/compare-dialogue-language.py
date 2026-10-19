#!/usr/bin/env python3
"""Compare fixed language rules on actual readings and explicit diagnostics."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.data.dialogue_language import RULE,assess
from slm.data.quality_audit import predict,top_scores,LIMITS
from slm.data.tokenized import sha,stamp
from slm.data.schema import digest

CONTROLS=[
 ('short_english','Hi!','review_attention'),
 ('short_english','lol yep im good, how bout u?','review_attention'),
 ('short_english','Me want bread. You help?','review_attention'),
 ('short_english','Arrr, matey! Where be the map?','review_attention'),
 ('short_english','Please move our meeting from 3 PM to 4 PM.','review_attention'),
 ('short_english','Keep two apples. Do not buy three.','review_attention'),
 ('short_english','Got it. Thanks!','review_attention'),
 ('short_english','Nah, the blue one, not the red one.','review_attention'),
 ('long_english','Please read the earlier conversation carefully before writing a response. The colleague corrected the appointment time and asked us to retain the updated quantity. A clear answer should preserve those facts without inventing a different name or changing the intended meaning.','not_hard_attention'),
 ('long_english','The story follows a traveler who gets lost in a forest and asks a friendly shopkeeper for directions. The shopkeeper explains the route, checks whether the traveler has understood, and offers a shorter path when the traveler says that time is limited.','not_hard_attention'),
 ('code_or_numeric','```python\ndef add(a, b):\n    return a + b\n```','review_attention'),
 ('code_or_numeric','{"tool":"arithmetic","arguments":{"left":2,"right":3}}','review_attention'),
 ('code_or_numeric','42','review_attention'),
 ('ambiguous_short_non_english','Bonjour, comment ça va ?','review_attention'),
 ('ambiguous_short_non_english','Hola, ¿cómo estás?','review_attention'),
 ('ambiguous_short_non_english','Guten Tag, wie geht es dir?','review_attention')
]


def legacy(windows):
    return any(w['status']!='scored' or not w['top_scores'] or len(w['top_scores'])!=2
               or w['top_scores'][0]['language']!='en' or w['top_scores'][0]['score']<.8 for w in windows)


def main():
    root=Path('data/iteration-two-language-comparison-v1');negative=root/'natural-negative-candidates.json'
    if sha(negative)!='2c5382e5ce732ee90006528f3e2eced2050d6133e72f08040ecdb2ae64ffdf53':raise ValueError('Actually read negatives differ')
    output=root/'results';output.mkdir()
    descriptor=Path('data/language-detector-v4/detector.json');detector=json.loads(descriptor.read_text())
    binary=Path(detector['binary']);model=Path(detector['model'])
    if sha(binary)!=detector['binary_sha256'] or sha(model)!=detector['model_sha256']:raise ValueError('Pinned detector differs')
    review_path=Path('reports/milestone-forty-five-dialogue-review.json');review=json.loads(review_path.read_text())
    sample=Path('data/iteration-two-dialogue-preparation-v1/quality/sample.jsonl')
    if sha(sample)!=review['sample_sha256']:raise ValueError('Actual English review sample differs')
    candidates=json.loads(negative.read_text());cases=[]
    for i,(slice_name,text,expected) in enumerate(CONTROLS):cases.append(dict(id='language-control-v1/'+str(i),slice=slice_name,text=text,expected=expected))
    for i,row in enumerate(candidates):
        if row['judgment']['language']!='clearly_non_english_prose' or digest(row['text'])!=row['text_sha256']:raise ValueError('Negative reading binding differs')
        cases.append(dict(id='natural-negative/'+row['node_id'],slice='natural_non_english',text=row['text'],expected='strong_non_english_attention',publisher_language=row['publisher_language']))
    inputs=[negative,descriptor,binary,model,review_path,sample,Path(__file__),Path('src/slm/data/dialogue_language.py')]
    guards={p:stamp(p) for p in inputs}
    (output/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    freeze=dict(creator='Navneet Prabhakar',rule=RULE,rule_sha256=digest(RULE),cases_sha256=sha(output/'cases.json'),
        detector_descriptor_sha256=sha(descriptor),actual_review_sha256=sha(review_path),natural_negative_sha256=sha(negative),
        script_sha256=sha(__file__),training_eligible=False)
    (output/'freeze.json').write_text(json.dumps(freeze,indent=2,sort_keys=True)+'\n')
    with (output/'input.txt').open('w') as f:
        for case in cases:f.write(case['text'].replace('\r',' ').replace('\n',' ')+'\n')
    predict(binary,model,output/'input.txt',output/'predictions.txt',LIMITS)
    predictions=(output/'predictions.txt').read_text().splitlines()
    if len(predictions)!=len(cases):raise ValueError('Prediction coverage differs')
    results=[]
    for case,line in zip(cases,predictions,strict=True):
        w=[dict(message=0,start=0,end=len(case['text']),status='scored' if any(c.isalpha() for c in case['text']) else 'no_alphabetic_content',top_scores=top_scores(line))]
        observation=assess([dict(role='user',content=case['text'])],w)
        okay=not observation['hard_attention'] if case['expected']=='not_hard_attention' else observation['status']==case['expected']
        results.append(dict(id=case['id'],slice=case['slice'],expected=case['expected'],v2=observation['status'],expectation_met=okay,
            v1_hard_attention=legacy(w),v2_hard_attention=observation['hard_attention'],language_scores=w[0]['top_scores']))
    english=[];read_ids={d['example_id']:d for d in review['decisions']}
    for line in sample.open():
        row=json.loads(line);record=row['record'];eid=record['example_id']
        if eid not in read_ids:continue
        if digest(record)!=read_ids[eid]['record_sha256']:raise ValueError('Actually read path differs')
        w=row['signals']['language_windows'];observation=assess(record['messages'],w)
        english.append(dict(example_id=eid,record_sha256=digest(record),v1_hard_attention=legacy(w),v2_hard_attention=observation['hard_attention'],
            v2=observation['status'],semantic_judgment=read_ids[eid]['decision']))
    if len(english)!=77:raise ValueError('Actual read-path coverage differs')
    if any(stamp(p)!=v for p,v in guards.items()):raise ValueError('Diagnostic input/code changed')
    report=dict(creator='Navneet Prabhakar',review_mode='delegated_expert',human_attestation=False,
        rule_sha256=digest(RULE),freeze_sha256=sha(output/'freeze.json'),implementation_sha256=sha('src/slm/data/dialogue_language.py'),
        script_sha256=sha(__file__),diagnostic_case_results=results,actual_english_path_results=english,
        diagnostic_expectations_met=sum(r['expectation_met'] for r in results),diagnostic_cases=len(results),
        natural_negative_languages=sorted({r['publisher_language'] for r in candidates}),
        actual_read_english_paths=len(english),v1_actual_english_hard_attention=sum(r['v1_hard_attention'] for r in english),
        v2_actual_english_hard_attention=sum(r['v2_hard_attention'] for r in english),training_eligible=False,
        scope='Selected development diagnostics: 77 already read English conversations (some with code/quotes), 12 read natural non-English roots from six languages, and 16 explicit controls. No calibrated population error rate, English certification, student training, source approval or corpus admission. Short non-English controls deliberately remain uncertain, not accepted English.')
    (output/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    Path('reports/milestone-forty-six-language-comparison.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('diagnostic_expectations_met','diagnostic_cases','actual_read_english_paths','v1_actual_english_hard_attention','v2_actual_english_hard_attention','natural_negative_languages')},indent=2))


if __name__=='__main__':main()
