import pytest
from slm.restart.numerical_budget import NumericalBudget,NumericalBudgetError


def test_unfinished_work_remains_charged_after_reopen(tmp_path):
    p=tmp_path/'budget.sqlite';b=NumericalBudget(p,identity='fixture',deadline=100)
    b.reserve('first',backend='mlx',kind='forward',positions=99999,now=1);b.close()
    b=NumericalBudget(p,identity='fixture',deadline=100)
    with pytest.raises(NumericalBudgetError):b.events()
    assert b.events(require_complete=False)[0]['positions']==99999
    with pytest.raises(NumericalBudgetError):b.reserve('retry',backend='mlx',kind='forward',positions=2,now=2)
    b.reserve('tail',backend='torch',kind='ce_gradient',positions=1,now=2)
    with pytest.raises(NumericalBudgetError):b.reserve('extra',backend='torch',kind='forward',positions=1,now=2)
    b.close()


def test_shared_optimizer_cap_and_duplicate_rejection(tmp_path):
    b=NumericalBudget(tmp_path/'budget',identity='fixture',deadline=100)
    for i in range(18):
        b.reserve(str(i),backend='mlx' if i%2 else 'torch',kind='optimizer',positions=32,now=1);b.complete(str(i))
    assert sum(e['optimizer_updates'] for e in b.events())==18
    with pytest.raises(NumericalBudgetError):b.reserve('21',backend='mlx',kind='optimizer',positions=32,now=1)
    with pytest.raises(NumericalBudgetError):b.reserve('0',backend='mlx',kind='forward',positions=1,now=1)
    with pytest.raises(NumericalBudgetError):b.complete('0')
    b.close()


def test_terminal_and_contract_cannot_be_reset(tmp_path):
    p=tmp_path/'budget';b=NumericalBudget(p,identity='fixture',deadline=100);b.stop('quality failure');b.close()
    with pytest.raises(NumericalBudgetError):NumericalBudget(p,identity='changed',deadline=100)
    b=NumericalBudget(p,identity='fixture',deadline=100)
    with pytest.raises(NumericalBudgetError):b.reserve('x',backend='mlx',kind='forward',positions=1,now=1)
    b.close()


def test_deadline_checked_before_work_is_charged(tmp_path):
    b=NumericalBudget(tmp_path/'budget',identity='fixture',deadline=100)
    with pytest.raises(NumericalBudgetError):b.reserve('x',backend='mlx',kind='gradient',positions=1,now=100)
    assert b.events()==[];b.close()


def test_operation_and_settlement_happen_after_durable_charge(tmp_path):
    from slm.restart.numerical_budget import perform
    b=NumericalBudget(tmp_path/'budget',identity='fixture',deadline=100);order=[]
    def operation():
        assert len(b.events(require_complete=False))==1
        with pytest.raises(NumericalBudgetError):b.events()
        order.append('operation');return 5
    def settle(value):assert value==5;order.append('settle')
    assert perform(b,'x',backend='mlx',kind='forward',positions=4,now=1,operation=operation,settle=settle)==5
    assert order==['operation','settle'] and len(b.events())==1;b.close()


@pytest.mark.parametrize('where',['operation','settle'])
def test_work_failure_retains_charge_and_stops_attempt(tmp_path,where):
    from slm.restart.numerical_budget import perform
    b=NumericalBudget(tmp_path/'budget',identity='fixture',deadline=100)
    def fail(*args):raise RuntimeError('fixture failure')
    with pytest.raises(RuntimeError):perform(b,'x',backend='mlx',kind='gradient',positions=4,now=1,operation=fail if where=='operation' else lambda:5,settle=fail if where=='settle' else lambda x:None)
    assert b.events(require_complete=False)[0]['positions']==4
    with pytest.raises(NumericalBudgetError):b.events()
    with pytest.raises(NumericalBudgetError):b.reserve('retry',backend='mlx',kind='gradient',positions=4,now=1)
    b.close()
