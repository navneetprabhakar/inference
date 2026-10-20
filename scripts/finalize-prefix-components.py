"""Consume terminal full-prefix links and independently verify source components."""
# Creator: Navneet Prabhakar
import json,sqlite3
from pathlib import Path
from slm.data.near_components import Components
from slm.data.near_component_audit import reconstruct,verify
from slm.data.stream_hash import sha
out=Path('data/english-global-components-v1');root=Path('data/global-prefix-grouping-v1')
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with Path(p).open() as f:
  for l in f:yield json.loads(l)
def main():
 if out.exists():raise FileExistsError(out)
 r=read(root/'report.json');terminal=read(root/'supervisor-terminal.json');plan=read(root/'plan.json')
 if not (r['complete'] and r['full_population'] and r['source_records']==235779 and terminal==dict(complete=True,returncode=0)):raise ValueError('Complete terminal full source join required')
 if sha('configs/global-prefix-grouping-v1.json')!=r['plan_sha256']:raise ValueError('Frozen full plan differs')
 for f,h in plan['inputs'].items():
  if sha(f)!=h:raise ValueError('Source input differs')
 for f,h in r['files'].items():
  if sha(root/f)!=h:raise ValueError('Join output differs')
 s=sqlite3.connect('file:'+str(Path(plan['source']).resolve())+'?mode=ro',uri=True);s.row_factory=sqlite3.Row
 n=sqlite3.connect('file:'+str((root/'index/near.sqlite').resolve())+'?mode=ro',uri=True)
 records=[dict(x) for x in s.execute('SELECT sid,eid,candidate,fixed,blocked FROM records ORDER BY sid')]
 inherited=[x['root'] for x in rows('data/global-grouping-input-v1/roots.jsonl')]
 a=Components(records,inherited)
 for facet,sid in n.execute('SELECT sid,source_sid FROM facet_sources ORDER BY sid,source_sid'):a.register(facet,sid)
 for x,y in n.execute('SELECT a,b FROM near_pairs ORDER BY a,b'):a.link(x,y)
 result=a.result()
 b=reconstruct(records,inherited,n.execute('SELECT sid,source_sid FROM facet_sources ORDER BY sid,source_sid'),n.execute('SELECT a,b FROM near_pairs ORDER BY a,b'),max_edges=2000000)
 receipt=dict(creator='Navneet Prabhakar',complete=True,records=len(records),components=len(result['components']),near_facet_links_consumed=result['near_facet_links_consumed'],candidate_withheld=result['candidate_withheld'],training_approved=False)
 out.mkdir()
 for name,rr in [('roots.jsonl',(dict(sid=i,root=x) for i,x in enumerate(result['roots']))),('components.jsonl',result['components'])]:
  with (out/name).open('x') as f:
   for row in rr:f.write(json.dumps(row,sort_keys=True)+'\n')
 receipt['independent_graph_check']=verify(b,rows(out/'roots.jsonl'),rows(out/'components.jsonl'),receipt)
 receipt['inputs']={str(p):sha(p) for p in ['scripts/finalize-prefix-components.py','src/slm/data/near_components.py','src/slm/data/near_component_audit.py',root/'report.json',root/'supervisor-terminal.json','data/global-grouping-input-v1/roots.jsonl',plan['source']]}
 receipt['files']={f:sha(out/f) for f in ['roots.jsonl','components.jsonl']}
 for p in [out/'report.json',Path('reports/english-global-components.json')]:p.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
