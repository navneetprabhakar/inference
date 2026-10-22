"""Harness sensitivity only: fake arithmetic forward, never a neural backend."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart.numerical_forward import run,discrepancy
B=json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-fixtures-v1/batches.json').read_text())
C=SimpleNamespace(vocab_size=16,num_layers=2,hidden_size=32)


def invocation(fault=None):
    def forward(backend,tokens,padding_mask=None,cache=None):
        history=tokens if cache is None else np.concatenate([cache,tokens],axis=1)
        values=np.cumsum(history,axis=1)[:,-tokens.shape[1]:].astype(np.float32)
        if fault=='causal':values+=history.sum(axis=1,keepdims=True)
        if fault=='documents':values+=history.sum()
        if fault=='cache' and cache is not None:values+=1
        if fault=='offset' and cache is not None and tokens.shape[1]>1:values+=1
        logits=np.repeat(values[:,:,None],16,axis=2)
        traces=[np.repeat(values[:,:,None],32,axis=2) for _ in range(2)]
        if fault=='backend' and backend=='torch':logits+=.01
        if fault=='trace' and backend=='torch':traces[1]+=1
        if fault=='nan':logits[:]=float('nan')
        return logits,history,traces
    return forward


def test_all_eight_checks_and_work_counter_with_arithmetic_stub():
    r=run(C,B,invocation())
    assert r['passed'] and len(r['cases'])==8 and r['forward_input_positions']>0
    ids={c['id'] for c in json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-suite-design-v1.json').read_text())['cases'] if c['group']=='forward'}
    assert set(r['cases'])==ids


@pytest.mark.parametrize('fault,case',[('causal','causal_future_perturbation'),('documents','separate_document_perturbation'),('cache','cached_vs_full_decode'),('offset','rope_offset_decode'),('backend','un-padded_batch_logits'),('trace','layer_residual_traces')])
def test_faults_fail_the_intended_case(fault,case):
    r=run(C,B,invocation(fault));assert not r['passed'] and not r['cases']['forward:'+case]['passed']


def test_nonfinite_output_and_shape_mismatch_cannot_pass():
    with pytest.raises(ValueError):run(C,B,invocation('nan'))
    with pytest.raises(ValueError):discrepancy([1],[1,2])
    assert discrepancy([1.],[1.00002])>1e-5
