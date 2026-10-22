"""Arithmetic fixture callbacks; no model or neural gradients evaluated."""
import json
from pathlib import Path
import numpy as np
import pytest
from slm.restart.numerical_gradients import run,compare_gradients
B=json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-fixtures-v1/batches.json').read_text())
SHAPES={'fixture':(2,)}


def invocation(fault=None):
    def gradient(backend,batch,embedding_implementation):
        y=np.array(batch['targets']);mask=np.array(batch['loss_mask']);m=mask.copy()
        if fault=='padding':m=np.ones_like(m)
        value=float((y*m).sum()/m.sum())
        g=np.array([value,value/2],np.float32)
        if fault=='backend' and backend=='mlx':g+=1
        if fault=='onehot' and embedding_implementation=='dense-onehot-v1':g+=1
        if fault=='eos' and np.all((mask==0)|(y==1)):g[:]=0
        return value,{'fixture':g}
    return gradient


def test_four_gradient_checks_with_arithmetic_fixture():
    r=run(B,SHAPES,invocation());assert r['passed'] and len(r['cases'])==4
    required={c['id'] for c in json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-suite-design-v1.json').read_text())['cases']}
    assert set(r['cases'])<=required


@pytest.mark.parametrize('fault,case',[('backend','all_parameter_gradients'),('padding','padding_zero_contribution'),('onehot','native_vs_onehot_embedding'),('eos','eos_nonzero_contribution')])
def test_injected_faults_fail_corresponding_case(fault,case):
    r=run(B,SHAPES,invocation(fault));assert not r['passed'] and not r['cases']['gradients:'+case]['passed']


def test_gradient_inventory_shape_and_finiteness_rejected():
    good={'fixture':np.ones(2,np.float32)}
    for bad in ({},{'fixture':np.ones(3)},{'fixture':np.array([1.,float('nan')])}):
        with pytest.raises(ValueError):compare_gradients(good,bad,SHAPES)
