import copy
import pytest
from slm.restart.numerical_monitor_comparison import compare


def evidence():
    return dict(step=8,targets=256,data_cursor=8,rng={'state':42},tokenizer_hash='x',code_hash='x',config_hash='x',schedule_hash='x',
                monitor={'losses':[1.,.5],'gradients':[2.,.45],'terminal':None,'loss_streak':0,'dev':[]})


def test_small_float_difference_only():
    a=evidence();b=copy.deepcopy(a);b['monitor']['gradients'][-1]+=2e-10
    assert compare(a,b)['passed']


@pytest.mark.parametrize('fault',['counter','rng','terminal','length','nan','excess','boolean','dev'])
def test_material_or_discrete_difference_fails(fault):
    a=evidence();b=copy.deepcopy(a)
    if fault=='counter':b['step']+=1
    elif fault=='rng':b['rng']['state']+=1
    elif fault=='terminal':b['monitor']['terminal']='STOP'
    elif fault=='length':b['monitor']['losses'].append(.4)
    elif fault=='nan':b['monitor']['gradients'][-1]=float('nan')
    elif fault=='excess':b['monitor']['gradients'][-1]+=.00002
    elif fault=='boolean':b['monitor']['loss_streak']=False
    elif fault=='dev':b['monitor']['dev'].append(.1)
    try:r=compare(a,b)
    except ValueError:return
    assert not r['passed']
