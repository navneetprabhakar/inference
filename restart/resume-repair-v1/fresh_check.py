"""Isolated correction of a false float-literal assertion; shared attempt budget."""
import validate as v
import json,time
s=v.s
# Preserve failed attempt ledger/STOP. Count its resources in the shared 12-update
# engineering limit while keeping correction receipts in a separate directory.
prior=s.read(v.ROOT/'ledger.json')
prior_stop=s.read(v.ROOT/'STOP.json')
assert prior_stop['type']=='AssertionError' and prior['updates']==8
assert 2e-5*2/5 != 8e-6
s.ROOT=v.ROOT/'fresh-check';s.PRIVATE=s.ROOT/'private';s.PRIVATE.mkdir(parents=True,exist_ok=True)
assert not (s.ROOT/'ledger.json').exists()
s.save(s.ROOT/'approval.json',s.read(v.ROOT/'approval.json'))
s.save(s.ROOT/'ledger.json',dict(prior,continued_from=str(v.ROOT/'ledger.json')))
s.save(s.ROOT/'correction.json',dict(reason='Literal 8e-6 differs from scheduled expression 2e-5*2/5; exact schedule remains unchanged.',expected_schedule=2e-5*2/5,incorrect_literal=8e-6,original_stop_preserved=True,max_aggregate_updates=12,new_updates_allowed=2))
meter=v.Meter('fresh-check-correction')
try:
    e,c=s.load(mode='fresh');_,gfn=s.serializer.loss_functions(e)
    assert e.base_step==0
    for opt,names in [(e.om,e.matrix),(e.on,e.norm)]:
        assert int(opt.state['step'])==0
        assert all(not bool(e.mx.any(opt.state[k][f])) for k in names for f in ['m','v'])
    rows=s.read(v.OLD/'private/fit.json');replay=v.np.load(v.OLD/'private/replay.npy').astype(v.np.int32)
    for i in range(2):s.update(e,c,gfn,[('fit',.5,rows[i*8:i*8+8])],replay[i],2e-5*(i+1)/5,meter)
    path=s.checkpoint(e,meter,'fresh-step2')
    state=s.snapshot(e,meter)
    assert state['optimizer_step']==2 and state['effective_learning_rate']==2e-5*2/5
    s.save(s.ROOT/'result.json',dict(status='PASS',optimizer_step=state['optimizer_step'],effective_learning_rate=state['effective_learning_rate'],new_updates=2,aggregate_engineering_updates=meter.data['updates'],checkpoint=str(path)))
except Exception as exc:
    s.save(s.ROOT/'STOP.json',dict(reason=str(exc),type=type(exc).__name__));raise
finally:meter.close()
