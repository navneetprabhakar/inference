import math
import pytest
from slm.restart.monitor import Monitor,Resources,StopRun,cosine_rate

def update(m,**kw):m.update(**(dict(loss=2.,gradient_norm=1.,update_ratio=.001,targets=300000,all_state_finite=True)|kw))

def test_schedule_endpoints_and_nonfinite():
    assert cosine_rate(0,48000000)==0
    assert cosine_rate(250000,48000000)==2e-4
    assert cosine_rate(48000000,48000000)==2e-5
    assert cosine_rate(1000000,48000000)>cosine_rate(2000000,48000000)
    with pytest.raises(StopRun):cosine_rate(math.nan,48000000)

@pytest.mark.parametrize('field,value',[('loss',math.nan),('gradient_norm',math.inf),('all_state_finite',False),('loss',-1)])
def test_invalid_update_is_terminal(field,value):
    m=Monitor()
    with pytest.raises(StopRun):update(m,**{field:value})
    with pytest.raises(StopRun):update(m)

@pytest.mark.parametrize('field,value,n',[('loss',5.,5),('gradient_norm',11.,5),('update_ratio',.011,3)])
def test_sustained_spikes_and_persisted_state(field,value,n):
    m=Monitor()
    for _ in range(100):update(m)
    for _ in range(n-1):update(m,**{field:value})
    restored=Monitor(**m.state())
    with pytest.raises(StopRun):update(restored,**{field:value})

def test_development_regression_and_plateau():
    m=Monitor();m.development(nll=2.,after_pilot=False);m.development(nll=2.2,after_pilot=True)
    with pytest.raises(StopRun):m.development(nll=2.2,after_pilot=True)
    m=Monitor()
    for _ in range(6):m.development(nll=2.,after_pilot=True)
    with pytest.raises(StopRun,match='plateau'):m.development(nll=2.,after_pilot=True)

def test_overfitting_collapse_regression_copying():
    m=Monitor()
    for t,d in [(2,2),(1.95,2.02)]:m.diagnostic(train_nll=t,dev_nll=d,grammar=.8,grounded=.8,degenerate_outputs=0)
    with pytest.raises(StopRun,match='overfitting'):m.diagnostic(train_nll=1.9,dev_nll=2.04,grammar=.8,grounded=.8,degenerate_outputs=0)
    with pytest.raises(StopRun,match='collapse'):Monitor().diagnostic(train_nll=2,dev_nll=2,grammar=.8,grounded=.8,degenerate_outputs=5)
    m=Monitor()
    for g in [.8,.7]:m.diagnostic(train_nll=2,dev_nll=2,grammar=g,grounded=.8,degenerate_outputs=0)
    with pytest.raises(StopRun,match='regression'):m.diagnostic(train_nll=2,dev_nll=2,grammar=.7,grounded=.8,degenerate_outputs=0)
    m=Monitor();m.copying(6,1)
    with pytest.raises(StopRun,match='copying'):m.copying(7,1)

def observe(r,**kw):r.observe(**(dict(now=0,rss_gib=10,swap_growth_mib=0,free_disk_gib=100,heartbeat_at=0,thermal='nominal')|kw))

@pytest.mark.parametrize('args',[dict(rss_gib=18.1),dict(swap_growth_mib=513),dict(free_disk_gib=19),dict(now=121),dict(thermal=None),dict(rss_gib=math.nan),dict(heartbeat_at=1)])
def test_resource_immediate_limits(args):
    r=Resources()
    with pytest.raises(StopRun):observe(r,**args)
    with pytest.raises(StopRun):observe(r)

def test_resource_sustained_and_reset():
    r=Resources();observe(r,rss_gib=17);observe(r,now=20,rss_gib=16);observe(r,now=30,rss_gib=17)
    with pytest.raises(StopRun,match='sustained RSS'):observe(r,now=60,rss_gib=17)
    r=Resources();observe(r,thermal='serious');observe(r,now=59,thermal='serious')
    with pytest.raises(StopRun,match='thermal'):observe(r,now=60,thermal='critical')
