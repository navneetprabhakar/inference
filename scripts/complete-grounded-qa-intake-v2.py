"""Complete missing source evidence; reuse already complete train/dev intake charges."""
# Creator: Navneet Prabhakar
import hashlib,json
from pathlib import Path
from slm.data.intake_ledger import IntakeLedger
from slm.data.conversation_intake import fetch
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-qa-intake-v1')
def main():
 if (ROOT/'report-v2.json').exists():raise FileExistsError('Preserve completion evidence')
 p=json.loads(Path('configs/grounded-qa-intake-v1.json').read_text());ledger=IntakeLedger(ROOT/'ledger',p);commit=json.loads((ROOT/'source-ref.json').read_text())['object']['sha'];files={r['path']:r for r in json.loads((ROOT/'source-tree.json').read_text())['tree'] if r['type']=='blob'};evidence={};decoded={}
 try:
  snapshot=ledger.snapshot();states={x['key']:x['state'] for x in snapshot['attempts']}
  for name in ['dataset/train-v1.1.json','dataset/dev-v1.1.json','views/index.pug','LICENSE','README.md']:
   item=files[name];target=ROOT/Path(name).name
   if name.startswith('dataset/'):
    if states.get('file/'+name)!='complete' or states.get('decode/'+name)!='complete':raise ValueError('Existing complete original source intake required; no retry')
    raw=target.read_bytes()
   else:raw=fetch(ledger,'file/'+name,'https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer/'+commit+'/'+name,target,item['size'])
   if len(raw)!=item['size'] or hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=item['sha']:raise ValueError('Pinned complete Git blob differs')
   evidence[name]=dict(path=str(target),sha256=sha(target),git_blob=item['sha'],bytes=len(raw))
   if name.startswith('dataset/'):
    # Independent read-only source audit; no second acquisition/decode reservation or refund.
    body=json.loads(raw);count=0
    for article in body['data']:
     for paragraph in article['paragraphs']:
      for q in paragraph['qas']:
       count+=1
       if any(paragraph['context'][a['answer_start']:a['answer_start']+len(a['text'])]!=a['text'] for a in q['answers']):raise ValueError('Answer source offsets differ')
    decoded[name]=dict(questions=count,articles=len(body['data']),paragraphs=sum(len(a['paragraphs']) for a in body['data']),titles=[a['title'] for a in body['data']])
  if set(decoded['dataset/train-v1.1.json']['titles'])&set(decoded['dataset/dev-v1.1.json']['titles']):raise ValueError('Official article split overlap')
  text=(ROOT/'index.pug').read_text()
  if 'CC BY-SA 4.0' not in text:raise ValueError('Dataset-specific source license label required')
  report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,source=p['source'],revision=commit,version='1.1',evidence=evidence,decoded=decoded,all_answer_offsets_reconstructed=True,full_official_dev_articles_protected=True,code_license_not_dataset_license=True,ledger=ledger.snapshot(),original_path_lookup_failure_sha256=sha(ROOT/'failure.json'),scope='Full pinned human-authored QA source, no gradient or admission. Original failure was missing HTML path; actual site source is views/index.pug. Existing complete source files/98169 row charges reused without refetch, reset or refund. New evidence requests are distinct pinned files, not retries. Source assertions and sample semantic validity remain unverified.')
  (ROOT/'report-v2.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print('Pinned source intake complete',commit,{k:{a:b for a,b in v.items() if a!='titles'} for k,v in decoded.items()})
 finally:ledger.close()
if __name__=='__main__':main()
