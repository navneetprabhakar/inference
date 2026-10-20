"""Publish exact source-reviewed two-source recovery corpus after full grouping."""
# Creator: Navneet Prabhakar
import json,sqlite3,shutil
from pathlib import Path
from collections import Counter
from slm.data.english_corpus import select,save,lines,build_tokens,verify_tokens
from slm.data.stream_hash import sha
from slm.data.schema import digest
from slm.common.tokenizer import BPE
from slm.data.mixture import build_mixture
OUT=Path('data/english-recovery-corpus-v1');COMP=Path('data/english-global-components-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
def main():
 if OUT.exists():raise FileExistsError(OUT)
 receipt=json.loads((COMP/'report.json').read_text())
 if not receipt['complete'] or receipt['independent_graph_check']['records_checked']!=235779:raise ValueError('Independent complete component proof required')
 for name,h in receipt['files'].items():
  if sha(COMP/name)!=h:raise ValueError('Component bytes differ')
 for p,h in receipt['inputs'].items():
  if sha(p)!=h:raise ValueError('Component inputs differ')
 roots=[r['root'] for r in lines(COMP/'roots.jsonl')];comps={r['root']:r for r in lines(COMP/'components.jsonl')}
 reviews=[Path('data/english-corpus-admission-review-v1'),Path('data/english-corpus-admission-review-v2'),Path('data/english-long-prose-review-v1')]
 denied=set()
 for p in reviews:
  for r in lines(p/'judgments.jsonl'):
   if r['decision']!='consider':denied.add(r['sid'])
 source='data/global-exact-families-v2/families.sqlite';db=sqlite3.connect('file:'+str(Path(source).resolve())+'?mode=ro',uri=True)
 rows,excluded=select(db,roots,comps,denied);db.close()
 if not rows or len({r['split_group'] for r in rows})!=len(rows):raise ValueError('Nonempty unique admitted family population required')
 OUT.mkdir();evidence=OUT/'evidence';evidence.mkdir()
 bindings=[source,COMP/'report.json',COMP/'roots.jsonl',COMP/'components.jsonl','configs/english-recovery-execution-v1.json','configs/main-learning-budget-authorization-v2.json','src/slm/data/english_eligibility.py','src/slm/data/english_corpus.py',__file__]
 for p in reviews:bindings.extend([p/'plan.json',p/'samples.jsonl',p/'judgments.jsonl',p/'decision.json'])
 source_dirs=[Path('data/audit-v1/fineweb-edu/source'),Path('data/tinystories-source-ready-v1')]
 for folder in source_dirs:
  spec=json.loads((folder/'source.json').read_text())
  if sha(folder/'card.txt')!=spec['card_sha256'] or sha(folder/'license.txt')!=spec['license_text_sha256']:raise ValueError('Pinned source card/license differs')
  for name in ['source.json','card.txt','license.txt']:
   target=evidence/(folder.parent.name+'-'+name);shutil.copyfile(folder/name,target);bindings.append(folder/name)
 bindings.append('data/main-learning-budget-research-v1/commoncrawl-terms.html')
 policy=dict(creator='Navneet Prabhakar',kind='finite-english-research-admission-v1',authority='delegated_expert',human_attestation=False,training_approved=True,scope='Exact finite private laptop/one authorized GCP VM language pilot only; not production, redistribution or source-wide clearance',sources=['general','narrative'],source_license_basis='Pinned FineWeb-Edu ODC-By database evidence/Common Crawl conditions and TinyStories CDLA-Sharing publisher evidence; attribution retained. Underlying web/synthetic origin rights and factual uncertainty remain; no blanket rights guarantee.',eligibility='Original whole-window provisional screen plus fixed bounded coherent-prose filter, all exact/containment/near family exclusions and original heldout/nonapproval precedence',unread_risk='Majority policy-admitted rows are unread. Small source/length samples and uncalibrated proxies do not establish corpus error bounds or individual factual/privacy/SFW verification. Original failed populations and rejected Cosmopedia/long-prose strata retained.',nonapproval_source_sids=sorted(denied),excluded_signals=excluded,maximum_passes=2,inputs={str(p):sha(p) for p in bindings},population={source:{split:dict(records=sum(r['source']==source and r['split']==split for r in rows),content_token_occurrences=sum(r['original_content_tokens'] for r in rows if r['source']==source and r['split']==split)) for split in ['train','validation','test']} for source in ['general','narrative']})
 save(OUT/'admission.json',policy)
 for split in ['train','validation','test']:
  with (OUT/(split+'.jsonl')).open('x') as f:
   for r in rows:
    if r['split']==split:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 save(OUT/'manifest.json',dict(creator='Navneet Prabhakar',kind='finite-english-research-release-v1',policy_sha256=sha(OUT/'admission.json'),files={str(p.relative_to(OUT)):sha(p) for p in [OUT/'admission.json',*(OUT/f'{s}.jsonl' for s in ['train','validation','test']),*evidence.iterdir()]}))
 # Disjoint source families for preliminary physical work; never replay these in main language stream.
 main_rows={};preliminary=[]
 for source in ['general','narrative']:
  rr=sorted((r for r in rows if r['source']==source and r['split']=='train'),key=lambda r:digest(['preliminary-pool-v1',r['example_id']]))
  total=0;cut=0
  while total<600000 and cut<len(rr):total+=rr[cut]['original_content_tokens'];preliminary.append(rr[cut]);cut+=1
  main_rows[source]=rr[cut:]
 bpe=BPE.load(TOK);tokenizer_hash=sha(TOK/'manifest.json');release_hash=sha(OUT/'manifest.json');policy_hash=sha(OUT/'admission.json');prepared={}
 for name,rr in [('preliminary',preliminary),*main_rows.items()]:
  result=build_tokens(rr,bpe,OUT/name,release_hash,tokenizer_hash,policy_hash)
  checked=verify_tokens(rr,bpe,OUT/name,TOK)
  if checked!=result['processed_positions']:raise ValueError('Complete token reconstruction required')
  prepared[name]=result
 # Realized weights depend on supply; bounded two-pass exhaustion never fills with bad sources.
 components=[dict(id=s,path=str(OUT/s),dataset_hash=sha(OUT/s/'manifest.json'),weight=w,max_passes=2,max_positions=2*prepared[s]['processed_positions']) for s,w in [('general',60),('narrative',40)]]
 mixture=build_mixture(components,TOK,OUT/'language-mixture',objective='foundation',budget=78000000,minimum=10000000,group_cap=100000,seed='english-recovery-language-v1')
 # Freeze family-disjoint baseline/dev reference measurement before any gradients.
 dev=[]
 for source,n in [('general',200),('narrative',300)]:
  rr=sorted([r for r in rows if r['source']==source and r['split']=='validation'],key=lambda r:digest(['language-dev-v1',r['example_id']]))
  if len(rr)<n:raise ValueError('Insufficient independent development population')
  dev.extend(rr[:n])
 with (OUT/'development.jsonl').open('x') as f:
  for r in dev:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 prefix=[]
 for s in ['general','narrative']:
  for r in [r for r in dev if r['source']==s][:50]:prefix.append(dict(example_id=r['example_id'],source=s,prefix_tokens=bpe.encode(r['text'])[:48],reference_text=r['text']))
 save(OUT/'generation-prefixes.json',prefix)
 result=dict(creator='Navneet Prabhakar',complete=True,admission_sha256=policy_hash,release_manifest_sha256=release_hash,preparation=prepared,mixture=mixture,development_documents=len(dev),generation_prefixes=len(prefix),data_limited_two_source_revision=True,original40Mcoverage_gate_passed=False,model_updates=0,cloud_resources=0,training_contract_ready=False,inputs={str(p):sha(p) for p in bindings},files={f:sha(OUT/f) for f in ['development.jsonl','generation-prefixes.json']})
 save(OUT/'preparation.json',result);save('reports/english-corpus-preparation.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
