"""Pinned public human-authored span-QA source; no student update or admission."""
# Creator: Navneet Prabhakar
import hashlib,json,time,urllib.request
from pathlib import Path
from slm.data.intake_ledger import IntakeLedger
from slm.data.conversation_intake import fetch
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-qa-intake-v1')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();p=json.loads(Path('configs/grounded-qa-intake-v1.json').read_text());ledger=IntakeLedger(ROOT/'ledger',p)
 try:
  raw=fetch(ledger,'source-ref','https://api.github.com/repos/rajpurkar/SQuAD-explorer/git/ref/heads/master',ROOT/'source-ref.json',65536);commit=json.loads(raw)['object']['sha']
  if len(commit)!=40:raise ValueError('Exact immutable source commit required')
  tree=json.loads(fetch(ledger,'source-tree','https://api.github.com/repos/rajpurkar/SQuAD-explorer/git/trees/'+commit+'?recursive=1',ROOT/'source-tree.json',2*1024**2))
  if tree.get('truncated'):raise ValueError('Complete source inventory required')
  files={r['path']:r for r in tree['tree'] if r['type']=='blob'};evidence={};decoded={}
  for name in ['dataset/train-v1.1.json','dataset/dev-v1.1.json','index-v1.1.html','LICENSE']:
   item=files[name];maximum=32*1024**2 if name.endswith('train-v1.1.json') else 8*1024**2 if name.endswith('dev-v1.1.json') else 1024**2
   if item['size']>maximum:raise ValueError('Pinned source file exceeds finite limit')
   target=ROOT/Path(name).name;raw=fetch(ledger,'file/'+name,'https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer/'+commit+'/'+name,target,item['size'])
   if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=item['sha']:raise ValueError('Immutable Git blob mismatch')
   evidence[name]=dict(path=str(target),sha256=sha(target),git_blob=item['sha'],bytes=len(raw))
   if name.startswith('dataset/'):
    body=json.loads(raw)
    if body['version']!='1.1':raise ValueError('Exact answerable QA version required')
    count=sum(len(z['qas']) for a in body['data'] for z in a['paragraphs']);ledger.reserve('decode/'+name,rows=count,output_bytes=1024**2)
    for article in body['data']:
     for paragraph in article['paragraphs']:
      for q in paragraph['qas']:
       if not q['answers'] or any(paragraph['context'][a['answer_start']:a['answer_start']+len(a['text'])]!=a['text'] for a in q['answers']):raise ValueError('Every full-source answer offset must reconstruct')
    ledger.finish('decode/'+name,raw=b'');decoded[name]=dict(questions=count,articles=len(body['data']),paragraphs=sum(len(a['paragraphs']) for a in body['data']),titles=[a['title'] for a in body['data']])
  if set(decoded['dataset/train-v1.1.json']['titles'])&set(decoded['dataset/dev-v1.1.json']['titles']):raise ValueError('Official train/dev article overlap')
  if 'CC BY-SA 4.0' not in (ROOT/'index-v1.1.html').read_text():raise ValueError('Dataset-specific source license evidence missing')
  report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,source=p['source'],revision=commit,version='1.1',evidence=evidence,decoded=decoded,all_answer_offsets_reconstructed=True,full_official_dev_articles_protected=True,code_license_not_dataset_license=True,ledger=ledger.snapshot(),scope='Intact human-authored question/answer spans from supplied Wikipedia passages, not pretrained student weights. Candidate for grounded answer conditioning only; full source/quality/grouping/research admission still required.')
  (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in decoded.items() if k!='titles'},indent=2))
 except BaseException as e:
  (ROOT/'failure.json').write_text(json.dumps(dict(complete=False,error_type=type(e).__name__,message=str(e),ledger=ledger.snapshot(),no_automatic_retry=True),indent=2)+'\n');raise
 finally:ledger.close()
if __name__=='__main__':main()
