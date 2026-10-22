"""Bounded candidate-only normalization/cardinality and synthetic memory test, no corpus scan."""
from pathlib import Path
import sys,json,hashlib,time,signal,subprocess,resource
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1]
sys.path.insert(0,str(HERE));import overlap_core as core
PARENT=BASE/'gutenberg-post1900-language17-custody-frame-preparation-v1/candidates.json';EXPECTED='1cb1dcbac5e661e94cd93a946e8964789a7c2ae9067d1184d462d5d2646e028c'
def H(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def candidate_stats():
 assert H(PARENT)==EXPECTED;c=json.loads(PARENT.read_text());assert len(c)==17 and sum(x['bytes'] for x in c)==528920 and sum(x['M1_content_tokens_already_computed'] for x in c)==173812
 stats=[]
 for r in c:
  p=Path(r['file']);assert H(p)==r['text_SHA256'] and p.stat().st_size==r['bytes'];norm=core.normalized(p.read_text());w=norm.split();stats.append({'ebook_ID':r['ebook_ID'],'bytes':r['bytes'],'normalized_words':len(w),'unique5grams':len(core.grams(w,5)),'unique12grams':len(core.grams(w,12)),'unique32grams':len(core.grams(w,32)),'maxword_characters':max(map(len,w),default=0)})
 return stats

def synthetic(stats):
 # Distinct64-character words maximize candidate shingle sets while exceeding
 # ordinary English word storage. Counts bind observed normalized-word lengths.
 import pyarrow,pyarrow._parquet,pyarrow.lib
 texts=[' '.join(('d'+str(i)+'w'+str(j)).ljust(64,'x') for j in range(r['normalized_words'])) for i,r in enumerate(stats)]
 before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;idx=core.Index(texts)
 # Concurrent M0role/family/history dictionaries retained in the legacy phase.
 roles={i:{'family_id':hashlib.sha256(('family'+str(i)).encode()).hexdigest(),'split':'train','normalized_sha256':hashlib.sha256(('norm'+str(i)).encode()).hexdigest()} for i in range(80038)}
 splits={v['family_id']:{'train'} for v in roles.values()};historical={i:hashlib.sha256(('hist'+str(i)).encode()).hexdigest() for i in range(252750)}
 # Exact four long-WB records must still be compared, never skipped. This
 # synthetic source exceeds the old200kword threshold and carries a late hit.
 words=['s'+str(i).zfill(58) for i in range(240742)];words[-64:]=idx.words[-1][-64:];text=' '.join(words);matches=idx.compare(text)
 assert len(roles)==80038 and len(splits)==80038 and len(historical)==252750
 peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 # macOS ru_maxrss is bytes; record platform explicitly.
 return {'status':'SYNTHETIC_MEMORY_FEASIBILITY_ONLY_NO_RETAINED_CORPUS_MATCH','candidate_documents':len(stats),'synthetic_candidate_words':sum(r['normalized_words'] for r in stats),'synthetic_candidate_word_width':64,'large_source_words':len(words),'source_last_candidate_late_containment_retained':len(stats)-1 in matches,'max5gram_jaccard_cardinality_threshold':max((len(x)*5//4 for x in idx.sets),default=0),'peak_RSS_bytes_macOS_ru_maxrss':peak,'before_index_peak_RSS_bytes':before,'actual_retained_source_corpus_rows_scanned':0,'SLM_tokenizer_used':False}

if __name__=='__main__':
 signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('capacity45seconds')));signal.alarm(45);start=time.monotonic()
 if '--worker' in sys.argv:
  stats=json.loads((HERE/('old4-cardinality.json' if '--old4' in sys.argv else 'candidate-cardinality.json')).read_text());print(json.dumps(synthetic(stats)));raise SystemExit()
 stats=candidate_stats();(HERE/'candidate-cardinality.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps({'candidate_stats_only':True,'max_words':max(r['normalized_words'] for r in stats),'sum_words':sum(r['normalized_words'] for r in stats),'elapsed_seconds':time.monotonic()-start}))
