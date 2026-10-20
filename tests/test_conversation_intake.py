# Creator: Navneet Prabhakar
import json
import pytest
from slm.data.conversation_intake import fetch,validate_page
from slm.data.intake_ledger import IntakeLedger

def test_revision_failure_is_charged_and_cannot_repeat(tmp_path):
 p={'limits':dict(requests=2,body_bytes=1000,rows=10,output_bytes=1000),'wall_seconds':60}
 l=IntakeLedger(tmp_path/'ledger',p)
 class R:
  status=200;headers={'x-revision':'wrong'}
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def read(self,n):return b'{}'
 with pytest.raises(ValueError,match='revision'):fetch(l,'one','https://example.test',tmp_path/'p',100,revision='expected',opener=lambda *a,**k:R())
 assert l.snapshot()['attempts'][0]['state']=='failed' and l.totals()['requests']==1
 with pytest.raises(ValueError,match='already reserved'):fetch(l,'one','https://example.test',tmp_path/'p',100,opener=lambda *a,**k:R())
 l.close()

@pytest.mark.parametrize('change',[{'truncated_cells':['messages']},{'row_idx':2}])
def test_truncated_or_wrong_row_refused(change):
 entry={'row_idx':0,'row':{'source':'x','messages':[]},'truncated_cells':[]};entry.update(change)
 with pytest.raises(ValueError):validate_page(json.dumps({'num_rows_total':1,'rows':[entry]}).encode(),0,1,'r',1)

def test_complete_page_preserved():
 row={'source':'x','messages':[{'role':'user','content':'A'}]};raw=json.dumps({'num_rows_total':1,'rows':[{'row_idx':0,'row':row,'truncated_cells':[]}]}).encode()
 assert validate_page(raw,0,1,'r',1)==[row]
