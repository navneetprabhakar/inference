"""Independent structural checks only. Semantic judgments are in the review JSON."""
import json,hashlib
from pathlib import Path
from collections import Counter
from sentencepiece import SentencePieceProcessor
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
SRC=REPO/'restart/coherence-g0-2026-10-29/benchmarks'
sp=SentencePieceProcessor(model_file=str(REPO/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
def load(n):return json.loads((SRC/(n+'.json')).read_text())
native=load('native_continuations');ground=load('grounded_choices');grammar=load('grammar_contrasts');dev=load('development')
issues=[]
for r in ground:
 for label,prefix,enc in [('normal',r['prefix'],r['joint_encoding']),('empty',r['controls']['empty_passage_prefix'],r['controls']['empty_passage_prefix_joint_encoding']),('shuffled',r['controls']['shuffled_passage_prefix'],r['controls']['shuffled_passage_prefix_joint_encoding'])]:
  pre=[sp.bos_id()]+sp.encode(prefix)
  if enc['prefix_ids']!=pre or enc['suffix_start']!=len(pre):issues.append([r['id'],label,'prefix'])
  for j,s in enumerate(r['suffixes']):
   full=[sp.bos_id()]+sp.encode(prefix+s)
   if full!=enc['full_ids'][j] or full[:len(pre)]!=pre:issues.append([r['id'],label,'joint suffix',j])
for r in dev:
 worst=1
 for t in r['turns']:
  worst+=len(sp.encode('User: '+t['user']+'\nAssistant:'))
  if worst!=t['worst_prefix_tokens']:issues.append([r['id'],'prefix counter',worst,t['worst_prefix_tokens']])
  if len(sp.encode(t['reference']))+1>32:issues.append([r['id'],'reply over32'])
  worst+=32
 if worst>256:issues.append([r['id'],'context over256',worst])
 if worst!=r['worst_history_tokens_including_last_reply']:issues.append([r['id'],'last context counter'])
for f in ['native_continuations','grounded_choices','grammar_contrasts','development']:
 a=load(f);b=load(f+'_review')
 if len(a)!=len(b) or any(any(r.get(k)!=v for k,v in s.items()) for r,s in zip(a,b)):issues.append([f,'review mirror differs'])
result={'note':'Automated structural checks, not semantic judgments','issues':issues,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SRC.glob('*.json') if p.name in [f+'.json' for f in ['native_continuations','grounded_choices','grammar_contrasts','development']]},'native_count':len(native),'native_domains':dict(Counter(r['domain'] for r in native)),'native_max_prefix_tokens_including_bos':max(1+len(sp.encode(r['prefix'])) for r in native),'ground_count':len(ground),'ground_domains':dict(Counter(r['domain'] for r in ground)),'ground_key_positions':dict(Counter(r['correct_index'] for r in ground)),'grammar_count':len(grammar),'grammar_key_positions':dict(Counter(r['correct_index'] for r in grammar)),'development_count':len(dev),'development_turns':sum(len(r['turns']) for r in dev),'development_structures':dict(Counter(r['structure'] for r in dev)),'development_unique_source_families':len(set(r['source_family'] for r in dev)),'development_max_context':max(r['worst_history_tokens_including_last_reply'] for r in dev)}
(ROOT/'benchmark-integrity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
