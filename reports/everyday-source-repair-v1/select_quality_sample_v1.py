"""One prospective64 full-history sample. Does not tokenize, admit or alter intake."""
import argparse,collections,hashlib,json,os,pathlib,resource,shutil,signal,sqlite3,sys,time
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).parent

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def choose(rows,seed):
 assert len(rows)==770 and len({r['doc_id'] for r in rows})==770
 ordered=sorted(rows,key=lambda r:(r['full_history_character_length'],r['doc_id']));cells=collections.defaultdict(lambda:collections.defaultdict(list))
 for rank,r in enumerate(ordered):
  assert r['old_whole'] in (0,1);q=rank*4//len(ordered);cells[q][r['old_whole']].append(r)
 selected=[];coverage={}
 for q in range(4):
  order=sorted(cells[q],key=lambda w:digest(['everyday-quality-cell-v1',seed,q,w]));queues={w:sorted(cells[q][w],key=lambda r:(digest(['everyday-quality-row-v1',seed,r['doc_id']]),r['doc_id'])) for w in order};positions={w:0 for w in order};chosen=[]
  while len(chosen)<16:
   progress=False
   for w in order:
    pos=positions[w]
    if pos<len(queues[w]):chosen.append(dict(queues[w][pos],quartile=q));positions[w]+=1;progress=True
    if len(chosen)==16:break
   assert progress,'insufficient quartile'
  selected+=chosen;coverage[q]=dict(eligible=sum(len(v) for v in cells[q].values()),cell_population={str(w):len(cells[q][w]) for w in order},cell_selected={str(w):positions[w] for w in order},selected_ids=[r['doc_id'] for r in chosen])
 assert len(selected)==64 and len({r['doc_id'] for r in selected})==64
 return selected,coverage

def main(policy,expected):
 if sys.flags.optimize:raise RuntimeError('assertions required')
 policy=pathlib.Path(policy).resolve();assert sha(policy)==expected;p=json.loads(policy.read_text());assert sha(pathlib.Path(__file__))==p['selector_sha256'];assert p['state']=='prospective_train_only_diagnostic_sample_not_admitted';source=R/p['source'];out=R/p['output'];assert not out.exists();start=time.monotonic();os.nice(10)
 def alarm(*args):raise TimeoutError('sample120second ceiling')
 signal.signal(signal.SIGALRM,alarm);signal.alarm(p['limits']['seconds'])
 def check():
  assert not any(x.exists() for x in (R/'runs/STOP',H/'STOP',source/'STOP',out/'STOP')),'STOP';assert time.monotonic()-start<p['limits']['seconds'],'wall';assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<p['limits']['rss_bytes'],'RSS';assert shutil.disk_usage(R).free>=p['limits']['free_disk_bytes'],'disk'
  if out.exists():assert sum(x.stat().st_size for x in out.iterdir() if x.is_file())<p['limits']['output_bytes'],'output'
 check();receiptpath=source/'receipt.json';receipt=json.loads(receiptpath.read_text());assert receipt['state']=='full_history_review_queue_not_admitted' and receipt['failure'] is None and receipt['training_admitted'] is False
 assert receipt['policy_sha256']==p['intake_policy_sha256'] and receipt['counts']==p['expected_counts'];assert sha(source/'review.sqlite')==receipt['database_sha256'] and sha(source/'review-queue.jsonl')==receipt['queue_sha256']
 pins={str(x.relative_to(R)):sha(x) for x in (policy,pathlib.Path(__file__).resolve(),receiptpath,source/'review.sqlite',source/'review-queue.jsonl')};db=sqlite3.connect(f'file:{source}/review.sqlite?mode=ro',uri=True);db.row_factory=sqlite3.Row;assert db.execute('pragma quick_check').fetchone()[0]=='ok';counts=dict(db.execute('select status,count(*) from histories group by status').fetchall());assert counts==p['expected_counts'];rows=[]
 for raw in db.execute("select * from histories where status='old_train' order by doc_id"):
  check();r=dict(raw);messages=json.loads(r.pop('messages_json'));assert digest(messages)==r['history_sha256'];r.update(messages=messages,full_history_character_length=sum(len(m['content']) for m in messages));rows.append(r)
 db.close();selected,coverage=choose(rows,p['seed']);out.mkdir()
 with (out/'sample.jsonl').open('x') as f:
  for r in selected:check();f.write(canon(r)+'\n')
 check()
 for n,h in pins.items():assert sha(R/n)==h,n
 manifest=dict(state='frozen_diagnostic_sample_not_reviewed_not_admitted',training_admitted=False,policy_sha256=expected,pins=pins,source_counts=counts,selected=64,coverage=coverage,sample_sha256=sha(out/'sample.jsonl'),records=[{k:v for k,v in r.items() if k!='messages'} for r in selected],seconds=time.monotonic()-start,limitations=p['scope'])
 check()
 with (out/'manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
 signal.alarm(0);print(json.dumps(dict(state=manifest['state'],selected=64,sample_sha256=manifest['sample_sha256'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('policy');p.add_argument('--sha256',required=True);a=p.parse_args();main(a.policy,a.sha256)
