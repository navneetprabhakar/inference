"""Build immutable locally reviewed supplement, retaining all prior split membership."""
import sys,json,hashlib,datetime
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_sft import JsonlConversations,BestFitConversations,NATIVE_IGNORE,load_manifest
from cloud_training.nano_chat_format import encode_conversation
from tools import FixtureSession
base=Path('runs/long-context-corpus-v5');out=Path('runs/long-context-corpus-v6')
assert not out.exists(),'Immutable output already exists'
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(r):return hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def grams(messages):
 w=' '.join(m.get('content','').casefold() for m in messages).split();return set(zip(*(w[i:] for i in range(5))))
bm=json.loads((base/'manifest.json').read_text());load_manifest(base/'manifest.json',bm['tokenizer_sha256'],4096)
rows={s:[json.loads(l) for l in (base/f'{s}.jsonl').read_text().splitlines()] for s in ['train','validation']}
existing=[grams(r['messages']) for rs in rows.values() for r in rs];supplement={s:[] for s in rows};reviews={};selected=[];excluded=[]
for folder,source_split in json.loads(Path('reports/ownbase-budget50-v1/corpus-expansion/reviewed-sources-v6.json').read_text()):
 root=Path('runs')/folder;rr=json.loads((root/'root-review.json').read_text());review={r['id']:r for r in rr['reviews']};reviews[str(root/'root-review.json')]=sha(root/'root-review.json')
 for line in (root/'candidates.jsonl').read_text().splitlines():
  s=json.loads(line);r=review[s['id']];assert r['sha256']==digest(s) and r['full_dialogue_reviewed']
  if not r['content_pass'] or not r.get('selected_for_supplement',False):excluded.append({'id':s['id'],'reason':r['reason']});continue
  split=r['split'];assert source_split is None or source_split==split
  if s.get('source_file'):
   assert sha(Path(s['source_file']))==s['source_sha256']
  b=FixtureSession();pol=iter(s['policies']);pending=None
  for m in s['messages']:
   if m['role']=='user':b.start_turn(**next(pol))
   elif m['role']=='assistant' and 'tool_call' in m:pending=b.propose(json.dumps(m['tool_call']),assistant_call_boundary=True);pending.pop('timestamp',None)
   elif m['role']=='tool':assert pending==m['record'];pending=None
  assert pending is None
  e=encode_conversation(tok,s['messages'],policies=s['policies'],context=4096);assert 3072<=len(e['ids'])<=4096
  g=grams(s['messages']);maxsim=max((len(g&h)/max(1,len(g|h)) for h in existing),default=0)
  assert maxsim<.65,('Near duplicate',s['id'],maxsim)
  existing.append(g)
  row={'family':'long_context_tool' if b.session_calls else 'long_context_natural','messages':s['messages'],'policies':s['policies'],'provenance':{'teacher':'gpt-6.1-terra','candidate_id':s['id'],'group':s['id'],'candidate_sha256':digest(s),'source':str(root/'candidates.jsonl'),'root_review':str(root/'root-review.json'),'split':split}}
  supplement[split].append(row);rows[split].append(row);selected.append({'id':s['id'],'split':split,'family':row['family'],'context_tokens':len(e['ids']),'assistant_targets':sum(e['mask'][1:]),'assistant_targets_after_2048':sum(e['mask'][2048:]),'assistant_targets_after_3072':sum(e['mask'][3072:]),'tool_call_positions':[span['start'] for span in e['spans'] if span['kind']=='tool_call_json'],'replayed_tool_calls':b.session_calls,'max_prior_jaccard':maxsim})
assert supplement['train'],'No training examples qualify'
out.mkdir();manifest={k:bm[k] for k in ['schema','training_admitted','format_version','context_tokens','tokenizer_sha256']};packed={};fingerprints={};coverage={}
for split in rows:
 coverage[split]={'assistant_targets_after_2048':0,'assistant_targets_after_3072':0,'sessions_at_least_3072':0}
 for row in rows[split]:
  e=encode_conversation(tok,row['messages'],policies=row.get('policies'),context=4096)
  coverage[split]['assistant_targets_after_2048']+=sum(e['mask'][2048:])
  coverage[split]['assistant_targets_after_3072']+=sum(e['mask'][3072:])
  coverage[split]['sessions_at_least_3072']+=int(len(e['ids'])>=3072)
 path=out/f'{split}.jsonl';path.write_bytes((base/f'{split}.jsonl').read_bytes()+''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in supplement[split]).encode())
 assert path.read_bytes().startswith((base/f'{split}.jsonl').read_bytes())
 d=JsonlConversations(path,tok,sha(path),4096);fingerprints[split]=d.fingerprints
 pack=BestFitConversations(d);targets=0
 while True:
  try:x,y=pack.next_row()
  except StopIteration:break
  assert len(x)==len(y)==4096;targets+=sum(v!=NATIVE_IGNORE for v in y)
 assert targets==sum(d.target_counts) and pack.consumed==len(rows[split])
 manifest[split]={'file':path.name,'sha256':sha(path),'bytes':path.stat().st_size,'sessions':len(rows[split]),'assistant_targets':targets}
 packed[split]={'rows':pack.rows,'targets':targets,'max_dialogue_tokens':max(d.lengths)}
 (out/f'supplement-{split}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in supplement[split]))
assert not fingerprints['train']&fingerprints['validation']
receipt={'schema':1,'training_admitted':True,'context_tokens':4096,'format_version':bm['format_version'],'tokenizer_sha256':bm['tokenizer_sha256'],'jsonl_sha256':[manifest[s]['sha256'] for s in ['train','validation']],'parent_manifest':str(base/'manifest.json'),'parent_manifest_sha256':sha(base/'manifest.json'),'root_review_sha256':reviews,'selected':selected,'excluded':excluded,'actual_trained_targets':0,'limitations':['Small pilot supplement, not a complete4Kextension corpus.','Development scenarios influenced generation design and are not a pristine benchmark.','Exact and5gram overlap checked; no embedding-based semantic deduplication.','Only calculate/convert workflows; no broader tool orchestration coverage.','Separate boundedGPUbase training is active; thisnew4Kcorpus remainsuntrained and excludedfromfrozen2KSFTpacket.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');load_manifest(out/'manifest.json',bm['tokenizer_sha256'],4096)
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'selected':selected,'supplement_counts':{s:len(supplement[s]) for s in supplement},'packing':packed,'full_corpus_coverage':coverage,'prior_split_membership':'Every prior row retained byte-for-byte in original split','actual_trained_targets':0,'manifest_sha256':sha(out/'manifest.json'),'full_4k_extension_corpus_ready':False,'vm':'Separate50USDbase continuation active; no4Ktraining','backup':'Local verified; immutable GCSupload/readback follows'}
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
