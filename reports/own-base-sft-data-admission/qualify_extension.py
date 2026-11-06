"""Bind actual four-call final histories to the admitted extension stream."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[2]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_bytes())
def require(ok,why):
 if not ok:raise ValueError(why)

def main():
 d=ROOT/'data/own-base-tool-session-aligned-v1';source=ROOT/'data/own-base-tool-session-extension-v1'
 require(not (ROOT/'runs/STOP').exists() and not (d/'STOP').exists(),'STOP')
 out=d/'four-call-qualification.json';require(not out.exists(),'preserve prior qualification')
 expected='4b72130463efbf67dacf42b551edfbd851a9cd60c7e29f0e38c206c50655ce76'
 require(sha(d/'receipt.json')==expected,'aligned identity')
 require(read(d/'diagnostic-admission.json')['dataset_sha256']==expected,'admission identity')
 manifest=read(source/'candidate-manifest.json');require(sha(source/'candidates.sqlite')==manifest['database']['sha256'],'source DB identity')
 excluded=set(read(source/'custody.json')['excluded_doc_ids']);counts={};seen=set()
 with sqlite3.connect(f'file:{source}/candidates.sqlite?mode=ro',uri=True) as db:
  for split,number in [('train',29),('exposed-development',8)]:
   rows=[json.loads(line) for line in (d/f'{split}.index.jsonl').open()]
   receipt=read(d/'receipt.json');require(sha(d/f'{split}.index.jsonl')==receipt['outputs'][f'{split}.index.jsonl']['sha256'],'index identity')
   final=[r for r in rows if r['turn']==2];require(len(final)==number,'final prefix population')
   for r in final:
    require(r['doc_id'] not in excluded and r['doc_id'] not in seen,'excluded/repeated lesson');seen.add(r['doc_id'])
    dbsplit,raw=db.execute('select split,adapted_json from documents where doc_id=?',(r['doc_id'],)).fetchone();require(dbsplit==split,'split identity')
    turns=json.loads(raw);require(len(turns)==3 and turns[-1]['turn_index']==2,'three-turn lesson')
    h=turns[-1]['history'];calls=[m for m in h if m['role']=='assistant' and 'call' in m];records=[m['record'] for m in h if m['role']=='tool']
    require(len(calls)==len(records)==4,'four complete calls')
    require([m['call_id'] for m in calls]==[v['call_id'] for v in records] and len({v['call_id'] for v in records})==4,'unique observed bindings')
    require(all(v['ok'] is True and v['source']=='offline fixture' for v in records),'actual successful arithmetic required')
    require(turns[-1]['policy']['permit_calls'] is False,'final no-call policy')
    last=max(i for i,m in enumerate(h) if m['role']=='user');require(not any('call' in m for m in h[last:]),'unexpected final-turn call')
   counts[split]=len(final)
 result=dict(state='PASS',dataset_sha256=expected,session_calls=4,final_turn=2,final_prefixes=counts,
             source_database_sha256=sha(source/'candidates.sqlite'),custody_sha256=sha(source/'custody.json'),
             code_sha256=sha(Path(__file__)),scope='Observed-source session structure qualification only; no model capability claim')
 with out.open('x') as f:json.dump(result,f,indent=2)
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
