"""Bounded whole-dialogue screening; candidates only, no training approval."""
# Creator: Navneet Prabhakar
import collections,json,re,time,unicodedata
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.tokenized import document_tokens
from slm.data.stream_hash import sha
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.quality_audit import PATTERNS,predict,top_scores,LIMITS
from slm.data.detector_projection import fasttext_line
from slm.data.prose_screen import windows
ROOT=Path('data/conversation-screen-v1')
SOURCE=Path('data/conversation-parquet-intake-v3/train.jsonl')
TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
CORE={'smol-magpie-ultra-short','smol-contraints','smollm-rewrite-30k','smol-summarize-20k','smol-summarize-5k','everyday-conversations'}
# Deliberately narrow first private research scope, not content/SFW certification.
OUT_OF_SCOPE=re.compile(r'\b(?:diagnos\w*|prescri\w*|dosage|medication|therapy|therapist|suicid\w*|self.harm|cancer|diabetes|pregnan\w*|invest\w*|stock market|tax\w*|legal advice|lawsuit|attorney|lawyer|financial advice|cryptocurrenc\w*|python|javascript|sql|html|algorithm|equation|calculus|sexual\w*|porn\w*|weapon\w*|bomb\w*|kill\w*)\b',re.I)
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();started=time.monotonic();bpe=BPE.load(TOK)
 config=json.loads(Path('configs/future-intake-evaluation-exclusions-v3.json').read_text());guard=EvaluationExclusions(config['inventory'],config['inventory_sha256'])
 descriptor=Path('data/language-detector-v4/detector.json');spec=json.loads(descriptor.read_text())
 for k in ('binary','model'):
  if sha(spec[k])!=spec[k+'_sha256']:raise ValueError('Pinned detector differs')
 paths=[SOURCE,TOK/'manifest.json',Path(config['inventory']),descriptor,Path(__file__)]
 bindings={str(p):sha(p) for p in paths};rows=[];all_checks=[];counts=collections.Counter();window_map=[]
 with (ROOT/'detector-input.txt').open('x') as out:
  for line in SOURCE.open():
   if time.monotonic()-started>1800:raise TimeoutError('Screen deadline')
   r=json.loads(line);m=r['messages'];why=[]
   if r['source'] not in CORE:why.append('constituent_outside_scope')
   roles=[x.get('role') for x in m]
   expected=(['system'] if roles and roles[0]=='system' else [])+['user','assistant']*((len(roles)-(roles[:1]==['system']))//2)
   if not roles or roles!=expected or any(set(x)!={'role','content'} or not isinstance(x['content'],str) or not x['content'].strip() for x in m):why.append('whole_alternating_dialogue_required')
   text='\n'.join(x.get('content','') for x in m)
   if len(text)>12000 or '\ufffd' in text or any(unicodedata.category(c)=='Cc' and c not in '\n\r\t' for c in text):why.append('length_encoding_scope')
   if OUT_OF_SCOPE.search(text) or '```' in text or re.search(r'https?://',text):why.append('narrow_task_scope')
   if any(p.search(text) for p in PATTERNS.values()):why.append('privacy_pattern')
   # Inventory verified once before and after this bounded run; original text unchanged.
   if guard.guard.matches(text):why.append('protected_evaluation_text')
   metrics={};parts=[]
   if not why:
    result,reason=document_tokens(bpe,dict(messages=m),'sft',768)
    if reason:why.append(reason)
    else:
     tokens,mask=result;assistant=[len(bpe.encode(x['content'])) for x in m if x['role']=='assistant']
     metrics=dict(prediction_positions=len(tokens)-1,supervised_positions=sum(mask[1:]),max_assistant_content_tokens=max(assistant))
     if sum(mask[1:])<16 or max(assistant)>256:why.append('assistant_length_scope')
   if not why:
    words=re.findall(r'\w+',text.casefold())
    if not words or max(collections.Counter(words).values())/len(words)>.15:why.append('word_repetition_signal')
    parts=windows(text)
    if not parts:why.append('no_qualifying_language_window')
   entry=dict(row_index=r['row_index'],source=r['source'],reasons=why,**metrics)
   all_checks.append(entry)
   if not why:
    rowid=len(rows);rows.append(r)
    for part in parts:
     window_map.append(rowid);out.write(fasttext_line(part['text'])+'\n')
   counts.update(why)
 predict(Path(spec['binary']),Path(spec['model']),ROOT/'detector-input.txt',ROOT/'detector-output.txt',{**LIMITS,'detector_seconds':120})
 predictions=[top_scores(x) for x in (ROOT/'detector-output.txt').open()]
 if len(predictions)!=len(window_map):raise ValueError('Full window coverage differs')
 bad=set()
 for i,scores in zip(window_map,predictions):
  if not scores or scores[0]['language']!='en' or scores[0]['score']<.8:bad.add(i)
 candidates=[r for i,r in enumerate(rows) if i not in bad]
 for path,value in [('candidates.jsonl',candidates),('checks.jsonl',all_checks)]:
  with (ROOT/path).open('x') as f:
   for r in value:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 if any(sha(p)!=h for p,h in bindings.items()):raise ValueError('Screen inputs changed')
 report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,content_category='unreviewed',human_attestation=False,input_rows=len(all_checks),candidates=len(candidates),by_source=dict(collections.Counter(r['source'] for r in candidates)),initial_reasons=dict(counts),language_window_rejections=len(bad),language_windows=len(window_map),max_context=768,max_assistant_content_tokens=256,minimum_assistant_targets=16,input_bindings=bindings,candidates_sha256=sha(ROOT/'candidates.jsonl'),elapsed_seconds=time.monotonic()-started,scope='Whole original rows; all qualifying1024-character/40-letter language windows >=.8 English signal; narrow heuristic task scope, no factual/privacy/SFW certification. Exact/near/family/source admission remains required.')
 (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='input_bindings'},indent=2))
if __name__=='__main__':main()
