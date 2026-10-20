# Creator: Navneet Prabhakar
import json,sqlite3,subprocess,sys
from pathlib import Path
from slm.data.stream_hash import sha

def plan(tmp_path):
 db=sqlite3.connect(tmp_path/'source.sqlite');db.execute('CREATE TABLE records(sid INTEGER PRIMARY KEY,data TEXT)')
 base=' '.join('word'+str(i) for i in range(120))
 for i,text in enumerate([base,base+' extra','other unrelated source has different tokens entirely']):db.execute('INSERT INTO records VALUES(?,?)',(i,json.dumps(dict(texts=dict(content=text)))))
 db.commit();db.close();(tmp_path/'order.bin').write_bytes(b'')
 p=dict(source=str(tmp_path/'source.sqlite'),ordering=str(tmp_path/'order.bin'),output=str(tmp_path/'out'),selection=None,max_facets=100,max_features=1000,max_pairs=100,max_database_bytes=1048576,max_work_bytes=10485760,minimum_free_bytes=1,wall_seconds=20)
 p['inputs']={f:sha(f) for f in [p['source'],p['ordering'],'scripts/run-prefix-grouping.py','src/slm/data/prefix_near.py']}
 f=tmp_path/'plan.json';f.write_text(json.dumps(p));return f,p

def test_full_runner_positive_pairs_terminal_and_replay_refusal(tmp_path):
 f,p=plan(tmp_path);r=subprocess.run([sys.executable,'scripts/run-prefix-grouping.py',str(f)],capture_output=True,text=True,timeout=30)
 assert r.returncode==0,r.stderr
 out=Path(p['output']);report=json.loads((out/'report.json').read_text())
 assert report['complete'] and report['full_population'] and report['source_records']==3 and report['qualifying_pairs']==1
 assert json.loads((out/'supervisor-terminal.json').read_text())['complete']
 assert subprocess.run([sys.executable,'scripts/run-prefix-grouping.py',str(f)],capture_output=True,timeout=10).returncode!=0

def test_source_tamper_refuses_before_output(tmp_path):
 f,p=plan(tmp_path);Path(p['ordering']).write_bytes(b'x')
 r=subprocess.run([sys.executable,'scripts/run-prefix-grouping.py',str(f)],capture_output=True,timeout=10)
 assert r.returncode!=0 and not Path(p['output']).exists()
