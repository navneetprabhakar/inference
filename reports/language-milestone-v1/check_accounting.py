"""CPU-only budget boundary checks; no model or dataset loads."""
import pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from own_base_language_milestone import forward_cost,reserve_forward
web=forward_cost(1,512);assert web==dict(attempted_targets=512,input_positions=512,attention_elements=262144,forwards=1)
pair=forward_cost(1,20,predicted=3);assert pair['attempted_targets']==3 and pair['input_positions']==20
gen=forward_cost(1,100,generation=True);assert gen['attempted_targets']==1 and gen['attention_elements']==10000
state={k:0 for k in web};reserve_forward(state,web,web);assert state==web
before=state.copy()
try:reserve_forward(state,gen,web)
except ValueError:pass
else:raise AssertionError('must refuse exhausted budget')
assert state==before # All dimensions checked atomically before any counter change.
for kwargs in [dict(batch=1,length=1025),dict(batch=1,length=4,predicted=5),dict(batch=0,length=4)]:
 try:forward_cost(**kwargs)
 except ValueError:pass
 else:raise AssertionError('invalid bounds accepted')
print('8 accounting/boundary checks PASS; no GPU or model load')

from own_base_language_milestone import ac_power_text
assert ac_power_text("Now drawing from 'AC Power'\n -InternalBattery-0 80%; charging")
assert not ac_power_text("Now drawing from 'Battery Power'\n -InternalBattery-0 80%; discharging")
assert not ac_power_text('unknown power status')
assert not ac_power_text('AC Power adapter unavailable')
print('4 AC policy parsing fixtures PASS; no host power query')
