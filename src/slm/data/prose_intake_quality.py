"""Full-window provisional prose screening, preserving original payloads."""
# Creator: Navneet Prabhakar
from pathlib import Path
from slm.data.detector_projection import fasttext_line
from slm.data.prose_screen import RULE, windows, screen
from slm.data.quality_audit import LIMITS, predict, top_scores
from slm.data.schema import digest


def assess(rows,guard,detector,work,judgments,heldouts):
    work=Path(work);work.mkdir(exist_ok=True)
    all_parts=[];counts=[]
    for raw in rows:
        if not isinstance(raw.get('id'),str) or not isinstance(raw.get('text'),str):
            raise ValueError('FineWeb text/id schema differs')
        parts=windows(raw['text']) if len(raw['text'])<=RULE['max_characters'] else []
        counts.append(len(parts));all_parts.extend(parts)
    if len(all_parts)>LIMITS['max_windows']:raise ValueError('Complete language coverage exceeds window cap')
    payload=''.join(fasttext_line(p['text'])+'\n' for p in all_parts).encode()
    if len(payload)>LIMITS['max_input_bytes']:raise ValueError('Language projection exceeds input cap')
    inp=work/'input.txt';out=work/'predictions.txt';inp.write_bytes(payload)
    scores=[]
    if all_parts:
        predict(Path(detector['binary']),Path(detector['model']),inp,out,LIMITS)
        lines=out.read_text().splitlines()
        if len(lines)!=len(all_parts):raise ValueError('Projected language window alignment differs')
        scores=[top_scores(line) for line in lines]
    result=[];cursor=0
    for raw,n in zip(rows,counts):
        group='HuggingFaceFW/fineweb-edu:'+raw['id'];isolation=guard.inspect_record(raw)
        if len(raw['text'])>RULE['max_characters']:
            decision=dict(candidate=False,reasons=['length_scope'],raw_record_sha256=digest(raw),
                training_approved=False,privacy_verified=False,factual_accuracy_verified=False,
                original_frozen_partition=heldouts.get(group),prior_direct_judgment=judgments.get(group),
                language_not_run='Original text exceeds admitted screen scope; no truncation.')
        else:
            decision=screen(raw,scores[cursor:cursor+n],guard.guard,judgments.get(group),heldouts.get(group))
        parts=[dict(start=p['start'],end=p['end'],scores=s) for p,s in zip(all_parts[cursor:cursor+n],scores[cursor:cursor+n])]
        cursor+=n
        result.append(dict(source_group=group,decision=decision,isolation=isolation,windows=parts,
            classifier_projection='fasttext-line-escape-v1',original_source_unchanged=True))
    for p in (inp,out,work/'detector.stderr'):
        if p.exists():p.unlink()
    return result
