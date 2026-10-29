"""Read-only fit diagnosis; correct ndarray input construction in old runner."""
import json
import numpy as np
from pathlib import Path
import importlib.util
p=Path(__file__).with_name('continue.py');spec=importlib.util.spec_from_file_location('continuation',p);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
s=c.s
from sentencepiece import SentencePieceProcessor
assert not (s.ROOT/'fit-position-diagnosis.json').exists()
s.assert_frozen();meter=s.Meter('diagnosis')
try:
    last=s.read(s.ROOT/'fit-result.json')['history'][-1]
    e,common=s.load(s.PROJECT/last['checkpoint']);model=common.bind(e)
    sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));rows=[]
    for row in s.read(s.PRIVATE/'fit.json'):
        ids,mask,spans=s.serializer.serialize(sp,row['messages']);span=spans[-1]
        meter.reserve(len(ids)-1,'fit-position-diagnosis-corrected')
        logits=model(e.mx.array(ids[:-1][None,:],e.mx.int32))[0].astype(e.mx.float32)
        positions=e.mx.arange(span['start']-1,span['end']-1)
        selected=logits[positions];targets=ids[span['start']:span['end']]
        pred=e.mx.argmax(selected,axis=-1);nll=e.mx.logsumexp(selected,axis=-1)-selected[e.mx.arange(len(targets)),e.mx.array(targets)]
        e.mx.eval(pred,nll);e.memory()
        rows.append(dict(id=row['id'],family=row['family'],targets=targets.tolist(),predictions=np.array(pred).tolist(),target_nll=np.array(nll).tolist()))
    s.save(s.PRIVATE/'fit-position-diagnosis.json',rows)
    summary={}
    for family in sorted({r['family'] for r in rows}):
        rs=[r for r in rows if r['family']==family]
        summary[family]=dict(answers=len(rs),content_positions=sum(len(r['targets'])-1 for r in rs),content_correct=sum(sum(a==b for a,b in zip(r['targets'][:-1],r['predictions'][:-1])) for r in rs),eos_correct=sum(r['targets'][-1]==r['predictions'][-1] for r in rs),premature_eos=sum(sum(p==sp.eos_id() for p in r['predictions'][:-1]) for r in rs),all_reference_targets_correct=sum(r['targets']==r['predictions'] for r in rs),mean_target_nll=sum(sum(r['target_nll']) for r in rs)/sum(len(r['targets']) for r in rs))
    s.save(s.ROOT/'fit-position-diagnosis.json',dict(summary=summary,teacher_forced=True,new_updates=0,corrected_input_construction=True,original_diagnosis_failure_preserved=True))
    print(json.dumps(summary));s.assert_frozen()
finally:meter.close()
