"""Finite source-reviewed English research release and exact token preparation."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import sqlite3
from slm.data.english_eligibility import reasons
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.common.tokenizer import BPE,STRUCTURAL
from slm.data.tokenized import Writer,INDEX,ShardBatches

def save(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def lines(p):
 with Path(p).open() as f:
  for l in f:yield json.loads(l)
def select(source,roots,components,denied):
 """One unblocked candidate per full duplicate component; immutable original flags."""
 deny_roots={roots[s] for s in denied};chosen={};excluded=Counter()
 for sid,data,candidate,fixed,blocked,ingredient in source.execute('SELECT sid,data,candidate,fixed,blocked,ingredient FROM records ORDER BY sid'):
  if not candidate or ingredient not in ('general','narrative'):continue
  r=json.loads(data);g=components[roots[sid]]
  if bool(r['candidate'])!=bool(candidate) or r['ingredient']!=ingredient:raise ValueError('Source record flags differ')
  bad=reasons(r)
  if fixed or blocked or g['heldout_priority'] or g['blocked']:bad.append('protected_or_blocked_component')
  if roots[sid] in deny_roots:bad.append('direct_nonapproval_component')
  if bad:excluded.update(bad);continue
  identity=digest(['finite-english-research-v1',r['id']]);key=roots[sid]
  row=dict(sid=sid,example_id=r['id'],parent_group_id=g['group_id'],split_group=g['group_id'],source=ingredient,text=r['texts']['content'],content_sha256=digest(r['texts']['content']),original_content_tokens=r['tokens'],reference=r['reference'])
  if key not in chosen or identity<chosen[key][0]:chosen[key]=(identity,row)
 result=[]
 for _,r in sorted(chosen.values()):
  draw=int(digest(['english-recovery-split-v1',r['split_group']])[:12],16)%10000
  r['split']='validation' if draw<100 else 'test' if draw<200 else 'train';result.append(r)
 return result,dict(excluded)

def build_tokens(rows,bpe,output,release_hash,tokenizer_hash,policy_hash,context=1024):
 output=Path(output)
 if output.exists():raise FileExistsError(output)
 output.mkdir();writer=Writer(output,262144,100000000);buf=[];positions=count=0
 try:
  with (output/'lineage.jsonl').open('x') as lineage:
   for r in rows:
    if r['split']!='train' or digest(r['text'])!=r['content_sha256']:raise ValueError('Intact admitted train row required')
    tokens=bpe.encode(r['text'])+[STRUCTURAL['eos']]
    contribution=len(tokens)-(0 if count else 1)
    row={k:r[k] for k in ('example_id','parent_group_id','split_group','source','split','content_sha256')}
    row.update(prediction_positions=contribution,supervised_positions=contribution,encoded_positions=len(tokens),prediction_offset_start=positions,prediction_offset_end=positions+contribution,source_sid=r['sid'])
    lineage.write(json.dumps(row,sort_keys=True)+'\n');positions+=contribution;count+=1;buf.extend(tokens);start=0
    while len(buf)-start>context:
     chunk=buf[start:start+context+1];writer.add(chunk[:-1],chunk[1:],[1]*context);start+=context
    buf=buf[start:]
   if len(buf)>1:writer.add(buf[:-1],buf[1:],[1]*(len(buf)-1))
   writer.flush()
 finally:writer.close()
 if writer.processed!=positions or not count:raise ValueError('Exact complete source accounting required')
 report=dict(creator='Navneet Prabhakar',objective='foundation',records=count,processed_positions=positions,supervised_positions=positions,one_pass=True,source_text_truncation=False,cross_document_attention=True,admission_sha256=policy_hash)
 save(output/'report.json',report)
 manifest=dict(version=1,kind='portable-token-shards-v1',message_format='plain-dialogue-v1',split='train',objective='foundation',batch_size=1,context_length=context,vocab_size=bpe.vocab_size,tokenizer_hash=tokenizer_hash,release_manifest_sha256=release_hash,research_policy_file_sha256=policy_hash,lineage_schema='record-content-spans-v2',allowed_categories=['sfw'],allowed_sources=sorted({r['source'] for r in rows}),batches=writer.batches,processed_tokens=writer.processed,supervised_tokens=writer.supervised,index_dtype=INDEX.descr,shards=writer.shards,builder_sha256=sha(__file__),files={str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()})
 save(output/'manifest.json',manifest);return report

def verify_tokens(rows,bpe,path,tokenizer):
 """Reconstruct every next-token pair from complete source rows, independently of packer."""
 with ShardBatches(path,tokenizer) as data:
  def stream():
   for row in rows:
    if row['split']!='train' or digest(row['text'])!=row['content_sha256']:raise ValueError('Train-only unchanged source required')
    yield from bpe.encode(row['text']);yield STRUCTURAL['eos']
  it=iter(stream());previous=next(it);checked=0
  for i in range(len(data)):
   x,y,m=data[i]
   for a,b,c in zip(x[0],y[0],m[0]):
    expected=next(it,None)
    if int(a)!=previous or int(b)!=expected or float(c)!=1:raise ValueError('Full token/source alignment differs')
    previous=expected;checked+=1
  if next(it,None) is not None:raise ValueError('Missing source token tail')
  if checked!=data.counts(len(data))[0]:raise ValueError('Token accounting differs')
 return checked
