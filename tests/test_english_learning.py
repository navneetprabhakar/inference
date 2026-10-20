# Creator: Navneet Prabhakar
import sqlite3
import pytest
from slm.english_learning import Meter,compare_learning

def test_durable_precharge_no_refund_and_exact_budget(tmp_path):
 p=tmp_path/'meter.sqlite';m=Meter(p,'a',maximum=20,phase_maximum=12);m.reserve('mlx',0,8)
 with pytest.raises(sqlite3.IntegrityError):m.reserve('mlx',0,1)
 with pytest.raises(ValueError):m.reserve('mlx',8,5)
 m.close();m=Meter(p,'a',maximum=20,phase_maximum=12);assert m.total()==8;m.reserve('cuda',0,12)
 with pytest.raises(ValueError):m.reserve('third',0,1)
 m.close()
 with pytest.raises(ValueError):Meter(p,'changed')

def scores(vals):return {'rows':[dict(example_id=str(i),split_group='g'+str(i),source='general' if i%2 else 'narrative',positions=12,nll=v) for i,v in enumerate(vals)]}
def test_family_bootstrap_and_slice_regression_and_identity():
 a=scores([4]*20);b=scores([3.5]*20);r=compare_learning(a,b);assert r['passed'] and r['bootstrap_95_lower']>.49
 assert not compare_learning(a,scores([4.3 if i%2 else 2 for i in range(20)]))['passed']
 b['rows'][0]['split_group']='changed'
 with pytest.raises(ValueError):compare_learning(a,b)

def test_preliminary_arms_share_aggregate_two_million_cap(tmp_path):
 m=Meter(tmp_path/'aggregate.sqlite','fixed',maximum=100000000,phase_maximum=2000000)
 m.reserve('common',0,1000000);m.reserve('mlx',0,1000000)
 with pytest.raises(ValueError):m.reserve('cuda',0,1)
 assert m.total()==2000000;m.close()

def test_regression_capture_keeps_actual_student_history_and_resets_sessions(tmp_path,monkeypatch):
 from slm import english_language_stage as stage
 from slm.data.schema import digest
 import json
 calls=[]
 class FakeStudent:
  identity={'test_only':True}
  def __init__(self,*args,**kwargs):pass
  def generate(self,history,budget):
   calls.append([dict(m) for m in history]);return {'text':'actual-reply-'+str(len(calls))}
 monkeypatch.setattr(stage,'GreedyModel',FakeStudent)
 tok=tmp_path/'tokenizer';tok.mkdir();(tok/'manifest.json').write_text('{}')
 output=tmp_path/'assessment';stage.conversations(tmp_path/'model',tok,output,'mlx','default')
 rows=[json.loads(l) for l in (output/'turns.jsonl').read_text().splitlines()]
 assert len(calls)==len(rows)==300
 assert calls[1][1]==dict(role='assistant',content='actual-reply-1')
 assert calls[2][3]==dict(role='assistant',content='actual-reply-2')
 assert len(calls[3])==1
 assert all(r['context_sha256']==digest(c) for r,c in zip(rows,calls))
 assert 'actual-reply-300' in (output/'transcripts-part-2.md').read_text()
