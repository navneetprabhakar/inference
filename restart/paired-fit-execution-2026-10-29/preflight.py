import sys,json,tempfile,py_compile
from pathlib import Path
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent/'runner-readiness-2026-10-29'))
from runner import Meter
sys.path.insert(0,str(P.parent/'phase-a-2026-10-28'))
from contracts import score
from tasks import oracle
py_compile.compile(str(P/'run.py'),doraise=True)
rows=json.loads((P.parent/'paired-fit-preparation-2026-10-29/private/fit-records.json').read_text());n=0
for r in rows:
 for t,a in enumerate(oracle(r['scenario'])):
  assert score(r['scenario'],t,a)['complete'];assert not score(r['scenario'],t,a,eos=False)['complete'];assert not score(r['scenario'],t,'WRONG_VALUE')['complete'];n+=3
with tempfile.TemporaryDirectory() as d:
 m=Meter(Path(d)/'test.sqlite',dict(positions=10,updates=2,assistant=4,narrative=6,seconds=10),True)
 m.reserve('synthetic-import',5,updates=1,assistant=2,narrative=3);m.reserve('synthetic-final',5,updates=1,assistant=2,narrative=3)
 for kwargs in [dict(updates=1),dict(positions=1),dict(assistant=1),dict(narrative=1)]:
  before=m.cursor()
  try:m.reserve('must-reject',**{'positions':0,**kwargs})
  except RuntimeError:pass
  else:raise AssertionError('CAP_NOT_ENFORCED')
  assert m.cursor()==before
 m.db.execute('UPDATE timing SET seconds=11 WHERE id=1');m.db.commit()
 try:m.start()
 except RuntimeError:pass
 else:raise AssertionError('TIME_CAP_NOT_ENFORCED')
result={'status':'PASS','score_assertions':n,'synthetic_budget_guards':5,'model_loaded':False,'optimizer_updates':0};(P/'preflight.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
