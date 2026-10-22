"""Two separately named candidate/fresh populations; no rerolls/version choice."""
import hashlib,heapq,json

def transcript(value):return (json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def integer(seed,draw,total):
 if total<=0:raise ValueError('positive_token_population_required')
 limit=(1<<256)-((1<<256)%total)
 for attempt in range(100):
  raw=(seed+'\nTOKEN_WEIGHTED\n'+str(draw)+'\n'+str(attempt)+'\n').encode()
  v=int.from_bytes(hashlib.sha256(raw).digest(),'big')
  if v<limit:return v%total
 raise ValueError('rejection_sampling_attempt_bound')

def select(db,seed,n,check,context):
 count,total=db.execute('SELECT count(*),coalesce(sum(M1_content_tokens),0) FROM texts WHERE fresh_population=1').fetchone()
 if count<n or total<=0:raise ValueError('fixed_sampling_population_too_small_no_reroll')
 cursor=db.execute('SELECT text_SHA256,M1_content_tokens,UTF8_bytes,first_source,first_ordinal FROM texts WHERE fresh_population=1 ORDER BY text_SHA256')
 digest=hashlib.sha256();heap=[]
 for h,t,b,s,o in cursor:
  check();digest.update(transcript([h.hex(),t,b,s,o]));priority=hashlib.sha256(seed.encode()+b'\nUNIFORM\n'+h).digest()
  # <=n only; ascending priority/sha tie order is deterministic uniform pseudorandom ranking.
  item=(int.from_bytes(priority+h,'big'),h,t,b,s,o)
  if len(heap)<n:heapq.heappush(heap,(-item[0],item))
  elif item[0]<heap[0][1][0]:heapq.heapreplace(heap,(-item[0],item))
 uniform=[v[1] for v in sorted(heap,key=lambda v:v[1][0])]
 draws=[]
 def add(mode,draw,h,t,b,s,o,extra):
  draws.append({'mode':mode,'draw':draw,'text_SHA256':h.hex(),'M1_content_tokens':t,'UTF8_bytes':b,'capture_source_id':s,'capture_ordinal':o,'capture_occurrence_not_preferred_corpus_version':True,'context':context(s,o),**extra})
 for i,(priority,h,t,b,s,o) in enumerate(uniform,1):add('UNIFORM_DISTINCT_RAW_SHA_WITHOUT_REPLACEMENT',i,h,t,b,s,o,{'priority_SHA256':priority.to_bytes(64,'big')[:32].hex()})
 positions=sorted((integer(seed,i,total),i) for i in range(1,n+1));pi=0;cum=0
 for h,t,b,s,o in db.execute('SELECT text_SHA256,M1_content_tokens,UTF8_bytes,first_source,first_ordinal FROM texts WHERE fresh_population=1 ORDER BY text_SHA256'):
  check();end=cum+t
  while pi<len(positions) and positions[pi][0]<end:
   pos,i=positions[pi];add('TOKEN_WEIGHTED_WITH_REPLACEMENT_NOT_BYTES',i,h,t,b,s,o,{'token_position_zero_based':pos});pi+=1
  cum=end
 if pi!=n or cum!=total:raise ValueError('token_weighted_complete_cdf')
 draws.sort(key=lambda d:(d['mode'],d['draw']));unique={d['text_SHA256']:d for d in draws};uniformsha={d['text_SHA256'] for d in draws if d['mode'].startswith('UNIFORM')};weighted=[d['text_SHA256'] for d in draws if d['mode'].startswith('TOKEN')]
 return {'status':'FROZEN_PRE_REVIEW_CANDIDATE_QUALITY_AUDIT_SELECTION_NOT_M2_ACCEPTANCE','seed':seed,'fresh_population_distinct_raw_SHA':count,'fresh_population_M1_content_tokens':total,'ordered_fresh_frame_SHA256':digest.hexdigest(),'uniform_without_replacement':n,'tokenweighted_with_replacement':n,'draws':draws,'unique_drawn_raw_SHA':len(uniformsha|set(weighted)),'unique_capture_UTF8_bytes':sum(d['UTF8_bytes'] for d in unique.values()),'all_draw_multiplicity_UTF8_bytes':sum(d['UTF8_bytes'] for d in draws),'unique_capture_M1_content_tokens':sum(d['M1_content_tokens'] for d in unique.values()),'largest_selected_UTF8_bytes':max(d['UTF8_bytes'] for d in draws),'book_context_clusters_not_independent_books':len({d['context'].get('book_url') for d in unique.values() if d['context'].get('book_url')}),'weighted_unique_raw_SHA':len(set(weighted)),'weighted_repeat_draws':n-len(set(weighted)),'cross_draw_mode_overlap_raw_SHA':len(uniformsha&set(weighted)),'all_draw_multiplicity_and_overlaps_preserved':True,'book_cluster_handling':'No unreviewed same-book chapters excluded; clustered book context reported, probability population is distinct raw text not independently sampled books.','sampling_references':'uniform priority=SHA256(seedUTF8 + LF + UNIFORM + LF + rawSHA256bytes), lowest(priority,rawSHA); token integer=unbiased SHA256 rejection of seed+LF+TOKEN_WEIGHTED+LF+draw+LF+attempt+LF, modulo complete content-token sum.','source_rights_family_near_protected_uncleared':True,'new_admitted_documents':0,'new_admitted_tokens':0}
