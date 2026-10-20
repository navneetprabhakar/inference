"""Freeze new source-heldout conversation cases before new student gradients."""
# Creator: Navneet Prabhakar
import collections,json,re,struct,time
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.tokenized import document_tokens
from slm.data.conversation_grouping import Query,facets
from slm.data.curation import shingles
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.data.quality_audit import PATTERNS
ROOT=Path('data/conversation-acceptance-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();start=time.monotonic();bpe=BPE.load(TOK);source=Path('data/conversation-corpus-intake-v1/upstream-test.jsonl')
 order={}
 with Path('data/prefix-near-benchmark-v1/ordering-counts.bin').open('rb') as f:
  while b:=f.read(36):order[b[:32]]=struct.unpack('<I',b[32:])[0]
 query=Query('data/global-prefix-grouping-v2/index',order,2000000)
 pool=[json.loads(l) for l in source.open()];pool=sorted(pool,key=lambda r:digest(['conversation-acceptance-v1',r['row_index']]))
 chosen=[];prior=[];counts=collections.Counter()
 bad=re.compile(r'\b(?:diagnos\w*|prescri\w*|dosage|medic\w*|therap\w*|suicid\w*|self.harm|cancer|pregnan\w*|invest\w*|stock\w*|tax\w*|legal\w*|lawsuit|attorney|lawyer|financial\w*|cryptocurrenc\w*|python|javascript|sql|html|algorithm\w*|calculus|sexual\w*|porn\w*|weapon\w*|bomb\w*|kill\w*|current\w*|today|this year|forecast|religio\w*|god|bible|politic\w*)\b',re.I)
 for r in pool:
  if time.monotonic()-start>1800:raise TimeoutError('Acceptance freeze wall cap')
  if r['source']!='smol-magpie-ultra-short' or [m['role'] for m in r['messages']]!=['user','assistant']*3:continue
  text='\n'.join(m['content'] for m in r['messages'])
  if len(text)>4500 or bad.search(text) or any(p.search(text) for p in PATTERNS.values()) or '```' in text:continue
  result,reason=document_tokens(bpe,r,'sft',768)
  if reason or max(len(bpe.encode(m['content'])) for m in r['messages'] if m['role']=='user')>180:continue
  fs=facets(r['messages']);values=[shingles(t) for t in fs.values()]
  if any(query.matches(t) for t in fs.values()):counts['prior_population_overlap']+=1;continue
  if any(20*len(a&b)>=17*len(a|b) for a in values for b in prior):counts['acceptance_case_overlap']+=1;continue
  prior+=values;chosen.append(r)
  if len(chosen)%25==0:print('frozen unseen conversations',len(chosen),flush=True)
  if len(chosen)==200:break
 query.close()
 if len(chosen)!=200:raise ValueError('Insufficient independent200 conversation cases')
 for name,rr in [('development-100.json',chosen[:100]),('reserved-100.json',chosen[100:])]:
  cases=[]
  for i,r in enumerate(rr,1):
   cases.append(dict(id=i,source_row_index=r['row_index'],source_record_sha256=digest(r),category='source-heldout-natural-conversation',turns=[dict(user=r['messages'][2*t]['content'],success_criterion='Correctly fulfil this exact user request using actual student history; preserve requested facts, constraints, references and corrections. Supplied upstream answer is fallible context for expert review, not an equality oracle.') for t in range(3)]))
  (ROOT/name).write_text(json.dumps(dict(creator='Navneet Prabhakar',max_new_tokens=256,conversations=cases,source='HuggingFaceTB/smol-smoltalk',split='upstream-test',human_attestation=False,claim='Newly frozen source-heldout cases; development reuse is not a fresh final test. No random population accuracy claim.'),ensure_ascii=False,indent=2)+'\n')
 with (ROOT/'source-references.jsonl').open('x') as f:
  for r in chosen:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,development_conversations=100,reserved_conversations=100,source_sha256=sha(source),cases={n:sha(ROOT/n) for n in ['development-100.json','reserved-100.json','source-references.jsonl']},prior_query_pairs=query.pairs,rejections=dict(counts),elapsed_seconds=time.monotonic()-start,scope='Entire upstream test remains excluded from train.200 cases exact/17-of20-shingle-disjoint from all prior population and each other before gradients. No semantic/paraphrase-family guarantee; source references not certified correct. No score-based case selection.')
 (ROOT/'manifest.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
