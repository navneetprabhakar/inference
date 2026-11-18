"""Verify exact CLI artifacts, including cold-review input binding and revision chains."""
import functools,hashlib,json,pathlib,re

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def messages(c):return [{'role':r,'content':t[r]} for t in c['turns'] for r in ('user','assistant')]
@functools.lru_cache(maxsize=None)
def cli_artifact(path_text,root_text,expected_sha):
 root=pathlib.Path(root_text);raw=pathlib.Path(path_text);assert sha(raw)==expected_sha
 assert raw.name.endswith('.raw.json')
 def sibling(suffix):return raw.with_name(raw.name.replace('.raw.json',suffix))
 events=sibling('.events.jsonl');prompt=sibling('.prompt.txt');request=sibling('.request.json')
 if not request.exists():request=root/'reports'/request.relative_to(root/'runs')
 req=json.loads(request.read_text());cmd=req['command'];assert cmd[:2]==['codex','exec']
 assert cmd[cmd.index('--model')+1]=='gpt-6.1-terra' and cmd[cmd.index('--sandbox')+1]=='read-only'
 assert '--ephemeral' in cmd and 'resume' not in cmd
 assert pathlib.Path(cmd[cmd.index('--output-last-message')+1])==raw
 if 'artifacts' in req:
  for ref in req['artifacts']:assert sha(root/ref['path'])==ref['sha256']
 else:
  assert req['raw_sha256']==sha(raw) and req['events_sha256']==sha(events) and req['prompt_sha256']==sha(prompt)
 event_rows=[json.loads(l) for l in events.read_text().splitlines()]
 assert any(e.get('type')=='turn.completed' for e in event_rows)
 assert all(e.get('item',{}).get('type') in (None,'agent_message','reasoning') for e in event_rows)
 outputs=[e['item']['text'] for e in event_rows if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
 data=json.loads(raw.read_text());assert outputs and json.loads(outputs[-1])==data
 return {'data':data,'prompt':prompt.read_text(),'request':req}

def verify_review_input(path,root,expected_sha,row):
 artifact=cli_artifact(str(path),str(root),expected_sha);prompt=artifact['prompt'];decoder=json.JSONDecoder();found=[]
 for match in re.finditer(r'\{',prompt):
  try:obj,_=decoder.raw_decode(prompt[match.start():])
  except ValueError:continue
  if isinstance(obj,dict) and obj.get('group')==row['group'] and obj.get('messages')==row['messages']:found.append(obj)
 assert found,'Review prompt lacks exact group/messages input'
 assert any(obj.get('content_sha256',obj.get('messages_sha256',obj.get('messages_hash')))==digest(row['messages']) for obj in found)
 assert all('author_review_notes' not in obj for obj in found)
 return artifact['data']

@functools.lru_cache(maxsize=None)
def raw_inventory(directory_text):
 result={}
 for path in sorted(pathlib.Path(directory_text).glob('*.raw.json')):
  data=json.loads(path.read_text())
  for c in data.get('conversations',[]):result.setdefault(c['group'],[]).append(str(path))
 return result

def verify_revision_history(row,root):
 count=row['total_generation_revisions'];assert type(count) is int and 0<=count<=2
 ref=row['generation_history_receipt'];p=root/ref['path'];assert sha(p)==ref['sha256'];data=json.loads(p.read_text())
 entries=data['entries'] if isinstance(data,dict) else data;entries=[e for e in entries if e['group']==row['group']];assert len(entries)==1
 e=entries[0];assert e['messages_sha256']==digest(row['messages']) and e['total_generation_revisions']==count
 versions=e.get('versions')
 if versions is None:
  versions=[{**h,'raw_artifact':h['raw_artifact']['path'],'raw_sha256':h['raw_artifact']['sha256']} for h in e['history']]
 assert len(versions)==count+1 and len({v['raw_artifact'] for v in versions})==len(versions)
 selected=root/row['generation']['raw_artifact'];actual=set(raw_inventory(str(selected.parent)).get(row['group'],[]));listed={str(root/v['raw_artifact']) for v in versions};assert listed==actual,'Revision ledger omits/adds raw generation versions'
 chosen=[i for i,v in enumerate(versions) if v['raw_artifact']==row['generation']['raw_artifact'] and v['raw_sha256']==row['generation']['raw_sha256']];assert len(chosen)==1
 if 'selected_revision' in e:assert e['selected_revision']==chosen[0]
 if 'history' in e:assert [i for i,h in enumerate(e['history']) if h['selected']]==chosen
 for i,version in enumerate(versions):
  raw=root/version['raw_artifact'];assert sha(raw)==version['raw_sha256']
  for key in ('request_receipt','events_receipt'):
   if key in version:
    ref=version[key];assert sha(root/ref['path'])==ref['sha256']
  content=cli_artifact(str(raw),str(root),version['raw_sha256'])['data'];hits=[c for c in content['conversations'] if c['group']==row['group']];assert len(hits)==1
  assert digest(messages(hits[0]))==version['messages_sha256']
  if 'revision' in version:assert version['revision']==i
 return count
