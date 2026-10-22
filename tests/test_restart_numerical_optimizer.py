import copy,json
from pathlib import Path
import numpy as np
from slm.restart.numerical_optimizer import accumulation_cases,trajectory_cases,schedule_case
B=json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-fixtures-v1/batches.json').read_text())


def gradient(backend,batch,embedding_implementation):
    y=np.array(batch['targets']);m=np.array(batch['loss_mask']);v=float((y*m).sum()/m.sum())
    return v,{'fixture':np.array([v,v/2],np.float32)}


def test_real_accumulators_against_arithmetic_full_batch():
    assert all(r['passed'] for r in accumulation_cases(B,{'fixture':(2,)},gradient).values())


def trajectory():
    # Constant gradient [3,4] has analytic norm 5, so clipping is active.
    # Constant effective gradient has bias-corrected m=g and v=g^2 at every step.
    p={'embedding':np.array([[1.,2.]],np.float32),'norm':np.array([1.],np.float32)};old={};rows=[]
    for step in range(1,9):
        g={'embedding':np.array([[3.,4.]],np.float32),'norm':np.array([0.],np.float32)}
        effective={k:v.astype(np.float64)/(5.+1e-6) for k,v in g.items()}
        moments={k:((v*(1-.9**step)).astype(np.float32),(v*v*(1-.95**step)).astype(np.float32)) for k,v in effective.items()}
        after={k:(w*(1-.02*(.1 if w.ndim==2 else 0))-.02*effective[k]/(np.abs(effective[k])+1e-8)).astype(np.float32) for k,w in p.items()}
        rows.append(dict(step=step,lr=.02,before=p,gradients=g,moments_before=old,after=after,moments_after=moments));p=after;old=moments
    return {'mlx':copy.deepcopy(rows),'torch':copy.deepcopy(rows)}


def test_numpy_oracle_matches_closed_form_constant_gradient_trajectory():
    result=trajectory_cases(trajectory());assert all(v['passed'] for v in result.values())


def test_wrong_moments_or_embedding_decay_fail():
    t=trajectory();t['mlx'][0]['moments_after']['embedding'][0][0,0]+=.01
    assert not trajectory_cases(t)['accumulation_optimizer:adam_first_second_moments']['passed']
    t=trajectory();t['mlx'][0]['after']['embedding']+=.002*t['mlx'][0]['before']['embedding']
    assert not trajectory_cases(t)['accumulation_optimizer:matrix_only_decay_including_embedding']['passed']


def test_all_six_case_ids_match_contract():
    cases=set(accumulation_cases(B,{'fixture':(2,)},gradient))|set(trajectory_cases(trajectory()))|set(schedule_case())
    design=json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-suite-design-v1.json').read_text())
    assert cases=={c['id'] for c in design['cases'] if c['group']=='accumulation_optimizer'}
    assert all(v['passed'] for v in schedule_case().values())
