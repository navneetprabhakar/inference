import collections,hashlib,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
T=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
P=Path(__file__).parent;path=ROOT/'runs/ownbase-budget50-v1/sft-2k/train.jsonl';rows=[json.loads(l) for l in path.open()]
families=collections.defaultdict(lambda:collections.Counter());modes=collections.Counter();lengths=[];texts=collections.Counter();policy_tokens=0
for row in rows:
 enc=encode_conversation(T,row['messages'],policies=row.get('policies'));f=families[row.get('family','unspecified')];f['sessions']+=1;f['assistant_targets']+=sum(enc['mask'][1:]);f['user_turns']+=sum(m['role']=='user' for m in row['messages']);lengths.append(len(enc['ids']))
 ps=row.get('policies') or [None for m in row['messages'] if m['role']=='user'];index=-1;turncalls=False
 for m in row['messages']:
  if m['role']=='user':
   if index>=0:modes[('enabled' if ps[index] and ps[index]['permit_calls'] else 'disabled')+('_call' if turncalls else '_no_call')]+=1
   index+=1;turncalls=False
  if m['role']=='assistant':
   if 'content'in m:texts[m['content']]+=1
   else:turncalls=True
 if index>=0:modes[('enabled' if ps[index] and ps[index]['permit_calls'] else 'disabled')+('_call' if turncalls else '_no_call')]+=1
meta=json.loads((ROOT/'runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs/metadata.json').read_text());manifest=ROOT/'runs/ownbase-budget50-v1/sft-2k/manifest.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest()==meta['identity']['source_manifest_sha256']
base=json.loads((ROOT/'runs/local-readiness-v1/base10b/metadata.json').read_text())
raw=json.loads((ROOT/'runs/ownbase-v2-data/corpus/full-10b-report.json').read_text())
source=sum(s['packing']['source_tokens'] for s in raw['train']);cropped=sum(s['packing']['cropped_tokens'] for s in raw['train'])
result={'approach':'Recomputed from the JSONL named by checkpoint identity; no reliance on prior prose verdict','sft_checkpoint_step':meta['step'],'sft_source_manifest_sha256':meta['identity']['source_manifest_sha256'],'sft_train_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'families':dict(families),'policy_modes_by_user_turn':modes,'sessions':len(rows),'assistant_text_turns':sum(texts.values()),'unique_exact_assistant_texts':len(texts),'top_repeated_assistant_texts':texts.most_common(10),'sequence_tokens':{'min':min(lengths),'median':statistics.median(lengths),'max':max(lengths)},'base_step':base['step'],'base_tokens_from_step_and_batch':base['step']*base['identity']['batch_tokens'],'base_context':base['identity']['config']['sequence_len'],'base_corpus_available_manifest_source_tokens':source,'base_corpus_cropped_tokens':cropped,'base_corpus_crop_fraction':cropped/source,'base_source':'karpathy/climbmix-400b-shuffle@915333b4f8b8684f39aeaafea600fea6f43fb703','limits':'Corpus aggregate covers packed inventory, not proof all inventory was consumed. Source payloads reside in GCS; no new full source/content/contamination audit performed. Exact text uniqueness is not scenario diversity.'}
(P/'data-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['top_repeated_assistant_texts']},indent=2))
