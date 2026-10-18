#!/usr/bin/env python3
"""Audit the existing sample and detector controls without admitting any data."""
# Creator: Navneet Prabhakar
import argparse
import json
from pathlib import Path
import resource
import time
from slm.data.quality_audit import audit,predict,top_scores,LIMITS
from slm.data.tokenized import sha
from slm.data.staging import canonical,metadata
from slm.data.review import training_examples

CASES=[
 ('professional','en','Please summarize the delivery risks, identify the missing information, and give me three concrete next steps.'),
 ('slang','en',"yo, i need two cheap notebooks for school, but don't add any pens to the order."),
 ('caveman','en','Me need two apples. No bananas. Keep total under ten dollars.'),
 ('negation','en','Do not send the email yet. First correct the quantity from twelve to two and wait for my confirmation.'),
 ('profanity','en','That was a damn frustrating result. Please explain what failed and how to fix the problem.'),
 ('french','non_en','Je voudrais deux pommes et aucun autre fruit. Pouvez-vous me dire combien cela coûte au total ?'),
 ('hindi','non_en','मुझे दो सेब चाहिए और कोई दूसरा फल नहीं चाहिए। कृपया कुल कीमत बताइए।'),
 ('chinese','non_en','我想买两个苹果，不要其他水果。请告诉我总共需要多少钱。'),
 ('spanish','non_en','Quiero comprar dos manzanas y ninguna otra fruta. Por favor, dime cuánto cuestan en total.'),
 ('german','non_en','Ich möchte zwei Äpfel kaufen und keine anderen Früchte. Bitte sagen Sie mir den Gesamtpreis.'),
 ('short_slang','ambiguous','yo'),
 ('numbers','ambiguous','12.50, 2, 100'),
 ('json','ambiguous','{"quantity":2,"price":12.50,"enabled":false}'),
 ('romanized_mixed','ambiguous','mujhe two apples chahiye, total kitna hoga?'),
 ('code','ambiguous','def add(x, y): return x + y'),
 ('emoji','ambiguous','🦄 👍 123')]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--detector',required=True);a=p.parse_args()
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False);descriptor=Path(a.detector).resolve()
    dataset=Path('data/official-split-audit-v1/curated').resolve();packet=Path('data/official-split-audit-v1/pending-review.json');packet_hash=sha(packet)
    spec=dict(dataset=str(dataset),descriptor=str(descriptor),limits=LIMITS,seed='quality-audit-20261019-v1',groups_per_stratum=3,window_characters=2048)
    (root/'spec.json').write_text(canonical(spec)+'\n');start=time.monotonic();report=audit(output=root/'audit',**spec);wall=time.monotonic()-start
    model=metadata(descriptor);binary=descriptor.parent/model['binary'];weights=descriptor.parent/model['model']
    control_input=root/'control-input.txt';control_input.write_text(''.join(text+'\n' for _,_,text in CASES))
    predict(binary,weights,control_input,root/'control-output.txt',LIMITS)
    outputs=[top_scores(line) for line in (root/'control-output.txt').read_text().splitlines()]
    assert len(outputs)==len(CASES)
    controls=[]
    for (name,expected,text),scores in zip(CASES,outputs):
        match=None if expected=='ambiguous' else bool(scores) and (scores[0]['language']=='en')==(expected=='en')
        controls.append(dict(name=name,expected=expected,top_scores=scores,expected_top_class_matched=match))
    try:list(training_examples(root/'audit'))
    except ValueError as exc:refusal=str(exc)
    else:raise AssertionError('Audit accepted as training release')
    assert sha(packet)==packet_hash and sha(binary)==model['binary_sha256'] and sha(weights)==model['model_sha256']
    result=dict(scope='Existing first-N-derived sample only. Whole-group sampling is conditional on this snapshot, not upstream-representative or corpus approval.',
                audit_wall_seconds=wall,process_peak_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,rss_unit='bytes on macOS; KiB on Linux',
                report=report,controls=controls,controls_scope='Small authored diagnostic, not calibrated language accuracy or reviewed production evaluation.',
                training_refusal=refusal,original_review_packet_unchanged_sha256=packet_hash,audit_manifest_sha256=sha(root/'audit/manifest.json'),
                audit_implementation_sha256=sha('src/slm/data/quality_audit.py'),detector_descriptor_sha256=sha(descriptor),neural_updates=0,
                teacher_launches=0,platform_teacher_api_calls=0,cloud_jobs=0,actual_source_or_row_approvals=0)
    (root/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({k:result[k] for k in ('audit_wall_seconds','training_refusal','actual_source_or_row_approvals')}))


if __name__=='__main__':main()
