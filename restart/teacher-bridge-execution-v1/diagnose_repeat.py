"""Read-only extension: distinguish key order from same-order gradient variation."""
import json
import numpy as np
import support as s
from run import groups_at
from diagnose_resume import compute


def differences(a,b):
    out={}
    for k in a:
        if not np.array_equal(a[k],b[k]):
            d=a[k].astype(np.float64)-b[k].astype(np.float64)
            out[k]=dict(max_abs=float(np.max(np.abs(d))),different_elements=int(np.count_nonzero(d)),
                relative_l2=float(np.linalg.norm(d)/max(np.linalg.norm(a[k].astype(np.float64)),1e-30)))
    return out


def main():
    assert (s.ROOT/'resume-diagnosis.json').exists()
    assert not (s.ROOT/'repeat-diagnosis.json').exists()
    s.assert_frozen();meter=s.Meter('diagnosis')
    try:
        e,c=s.load(s.PRIVATE/'resume-preflight-step1.pt')
        original=list(e.params);updated=e.matrix+e.norm
        before={k:np.array(v) for k,v in e.params.items()}
        optimizer_before={f'{group}:{k}:{field}':np.array(opt.state[k][field]) for group,opt,names in [('matrix',e.om,e.matrix),('norm',e.on,e.norm)] for k in names for field in ['m','v']}
        replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32)[1]
        arrays=[];summaries=[]
        for order in [original,original,updated,updated]:
            values,summary=compute(e,groups_at(1,'teacher'),replay,meter,order)
            arrays.append(values);summaries.append({k:v for k,v in summary.items() if k!='reduction_order'})
        for k,v in e.params.items():assert np.array_equal(before[k],np.array(v))
        for group,opt,names in [('matrix',e.om,e.matrix),('norm',e.on,e.norm)]:
            assert int(opt.state['step'])==101
            for k in names:
                for field in ['m','v']:assert np.array_equal(optimizer_before[f'{group}:{k}:{field}'],np.array(opt.state[k][field]))
        assert e.local_step==0
        result=dict(status='READ_ONLY_REPEAT_CHECK_COMPLETE',new_updates=0,study_updates=meter.data['updates'],
            same_original_order=differences(arrays[0],arrays[1]),same_updated_order=differences(arrays[2],arrays[3]),
            changed_order=differences(arrays[1],arrays[2]),summaries=summaries,weights_and_moments_unchanged=True,
            limits='Gradient repeats only. No next-step optimizer execution, repair certification, acceptance-threshold relaxation or historical retry.')
        s.save(s.ROOT/'repeat-diagnosis.json',result);print(json.dumps(result,indent=2));s.assert_frozen()
    finally:meter.close()


if __name__=='__main__':main()
