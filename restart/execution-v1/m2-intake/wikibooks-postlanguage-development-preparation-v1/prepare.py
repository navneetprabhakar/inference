"""Metadata-only coverage reconciliation and frozen selection; never selects rendered.data."""
from pathlib import Path
import sqlite3,json,hashlib,time,signal
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];ROOT=BASE/'m2-intake';DB=ROOT/'wikibooks-language-token-v1/screening.sqlite3';FINAL=ROOT/'wikibooks-global-finalization-v3/finalized.sqlite3';ORIG=ROOT/'wikibooks-uniform-discovery-sample-v1';TAIL=ROOT/'wikibooks-short-tail-uniform-discovery-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ro(p):
 c=sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def digest(r):return hashlib.sha256((json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()).hexdigest()
def save(n,o):
 raw=(json.dumps(o,indent=2,ensure_ascii=False)+'\n').encode()
 if sum(p.stat().st_size for p in HERE.iterdir() if p.is_file())+len(raw)>1000000:raise ValueError('metadata1MBoutput')
 with (HERE/n).open('xb') as f:f.write(raw)
def run():
 started=time.monotonic()
 def stop(s,f):raise TimeoutError('metadata30seconds')
 signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,30)
 try:
  frozen=json.loads((HERE/'metadata-profile.json').read_text());assert sha(DB)==frozen['screening_SHA256'] and sha(FINAL)==frozen['finalizer_SHA256'];db=ro(DB);final=ro(FINAL)
  current=[dict(r) for r in db.execute('select * from docs where language_pass=1 and known_discovery_hold=0 order by source_ordinal')]
  assert len(current)==18688 and sum(r['content_tokens'] for r in current)==19909154 and sum(r['utf8_bytes'] for r in current)==62994062
  currentids={r['source_ordinal'] for r in current};currentfamilies={r['family'] for r in current}
  original=json.loads((ORIG/'selection.json').read_text())['sample'];tail=json.loads((TAIL/'selection.json').read_text())['selected'];contexts={r['source_ordinal']:r for r in json.loads((TAIL/'contexts.json').read_text())['records']};reviewed={}
  for n in ['partial-manual-review-v5.json','partial-manual-review-v6.json','complete-manual-review-v1.json']:
   obj=json.loads((ORIG/n).read_text());vals=obj.get('reviews',obj.get('whole_texts_read_by_parent',[]));vals=list(vals.values()) if isinstance(vals,dict) else vals
   for r in vals:
    reviewed[r['ordinal']]=r
   if 'final_review' in obj:reviewed[obj['final_review']['ordinal']]=obj['final_review']
  reconciliation={}
  for label,rows in [('original20_uniform_fullcanonical_discovery',original),('shorttail20_failedwindow_diagnostic',tail)]:
   records=[]
   for r in rows:
    o=r['source_ordinal'];p=dict(final.execute('select * from pages where source_ordinal=?',(o,)).fetchone());f=dict(final.execute('select * from final_pages where source_ordinal=?',(o,)).fetchone());screen=db.execute('select * from docs where source_ordinal=?',(o,)).fetchone();screen=dict(screen) if screen else None
    assert (p['page_id'],p['revision_id'],p['family'])==(r['page_id'],r['revision_id'],r['family'])
    if label.startswith('original'):
     assert sha(ORIG/f'{o}.txt')==p['text_sha256'];review=reviewed[o];assert review['whole_extracted_text_read'] and review.get('text_SHA256',p['text_sha256'])==p['text_sha256'];whole=True;context=None
    else:
     assert r['text_sha256']==p['text_sha256'];cx=contexts[o];assert cx['full_original_text_sha256']==p['text_sha256'] and sha(TAIL/cx['context_file'])==cx['context_sha256'];whole=cx['context_is_entire_short_document'];review=None;context={'SHA256':cx['context_sha256'],'whole_original_document':whole}
    if screen:assert (screen['page_id'],screen['revision_id'],screen['text_sha256'])==(p['page_id'],p['revision_id'],p['text_sha256'])
    records.append({'source_ordinal':o,'page_id':p['page_id'],'revision_id':p['revision_id'],'family':p['family'],'title':p['title'],'text_SHA256':p['text_sha256'],'finalizer_holds':json.loads(f['holds']),'language_screened':screen is not None,'language_pass':screen['language_pass'] if screen else None,'known_discovery_hold':screen['known_discovery_hold'] if screen else None,'current_candidate':o in currentids,'whole_document_review_evidence':whole,'diagnostic_context':context})
   reconciliation[label]={'documents':len(records),'current_candidate_exact_documents':sum(r['current_candidate'] for r in records),'original_whole_document_review_evidence':sum(r['whole_document_review_evidence'] for r in records),'records':records}
  covered={r['source_ordinal'] for group in reconciliation.values() for r in group['records'] if r['current_candidate']};reviewfamilies={r['family'] for group in reconciliation.values() for r in group['records']}
  framehash=hashlib.sha256(''.join(json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n' for r in current).encode()).hexdigest()
  ranked=[]
  for r in current:
   rank=hashlib.sha256(bytes.fromhex(frozen['seed_hex'])+bytes.fromhex(frozen['screening_SHA256'])+str(r['source_ordinal']).encode('ascii')).hexdigest();ranked.append((rank,r['source_ordinal'],r))
  selected=[]
  profile=json.loads((BASE/'wikibooks-language-token-preparation-v1/profile.json').read_text());ids=[r['source_ordinal'] for _,_,r in sorted(ranked)[:20]];locations={}
  for pin in profile['shards']:
   c=ro(Path(pin['path']))
   for q in c.execute('select source_ordinal,page_id,revision_id from rendered where source_ordinal in ('+','.join('?' for _ in ids)+')',ids):
    if q['source_ordinal'] in locations:raise ValueError('duplicate_selected_shard_identity')
    locations[q['source_ordinal']]={'path':pin['path'],'SHA256':pin['sha256'],'page_id':q['page_id'],'revision_id':q['revision_id']}
   c.close()
  assert set(locations)==set(ids)
  for rank,o,r in sorted(ranked)[:20]:
   loc=locations[o];assert (loc['page_id'],loc['revision_id'])==(r['page_id'],r['revision_id']);selected.append({**r,'rank_SHA256':rank,'source_shard':loc,'previous_exact_review_overlap':o in covered,'oversize_under_proposed2MB_documentcap':r['utf8_bytes']>2000000})
  coverage={'status':'METADATA_RECONCILED_NO_SEMANTIC_CERTIFICATION','frame_documents':18688,'frame_content_tokens_diagnostic':19909154,'frame_UTF8_bytes':62994062,'groups':reconciliation,'exact_reviewed_current_documents':len(covered),'current_documents_in_previously_seen_family':sum(r['family'] in reviewfamilies for r in current),'family_overlap_does_not_mean_document_review':True,'scope':'Only original20 fullcanonical discovery and20 failedshorttail diagnostic explicitly reconciled. Does not inventory every other targeted historical review. Both were DEVELOPMENT, not repaired-cohort acceptance.','new_admitted_documents':0}
  proposal={'status':'FROZEN_FRESH20_DEVELOPMENT_PROPOSAL_NO_BODY_READ','screening_SHA256':frozen['screening_SHA256'],'frame_ordered_metadata_SHA256':framehash,'frame_documents':18688,'frame_tokens_diagnostic':19909154,'seed_hex':frozen['seed_hex'],'rank':'SHA256(seed32rawbytes || screeningSHA32rawbytes || ASCII(source_ordinal)); lowest20 with ordinal tie-break','selection_frame':'ALL current18688, no availability/size/title/genre/priorreview exclusion; keepeveryselectednegative/oversize and no replacement.','selected':selected,'selected_UTF8_bytes':sum(r['utf8_bytes'] for r in selected),'selected_M1_tokens_stored_diagnostic':sum(r['content_tokens'] for r in selected),'prior_exact_review_overlap':sum(r['previous_exact_review_overlap'] for r in selected),'future_capture_limits':{'worker_seconds':55,'external_seconds':60,'observed_tree_RSS_bytes':1000000000,'output_bytes':5000000,'per_document_UTF8_cap':2000000},'future_whole_capture_rule':'Read exact renderer original complete text only after parentreview. Verify sourceordinal/page/rev/family/textSHA/bytes/character/tokenmetadata; save entire text byteexact or explicit oversized/negative/unavailable outcome, no snippet substitution, rerank or replacement. Preserve block/sourceHTML/recordSHA/location metadata and originalholds. No token/detector rerun.','manual_review_extent':'All selected complete documents within frozen2MB each; keep oversize outcome unreviewed/held, never substitute. Review entire savedtext, separate coherence/completeness/corruption from factual/rights/context flags.','not_acceptance':'Development diagnostic only, NOT fresh200+200 acceptance, no sourcewidequality pass orusable/admitted counts','selected_original_body_bytes_read_during_preparation':0,'new_admitted_documents':0,'new_admitted_tokens':0}
  save('coverage.json',coverage);save('proposal.json',proposal)
  assert sha(DB)==frozen['screening_SHA256'] and sha(FINAL)==frozen['finalizer_SHA256'];save('metadata-receipt.json',{'status':'COMPLETE_METADATA_ONLY_NO_SELECTED_BODY_READ','elapsed_seconds':time.monotonic()-started,'selected_documents':20,'selected_UTF8_bytes':proposal['selected_UTF8_bytes'],'original20_current_matches':reconciliation['original20_uniform_fullcanonical_discovery']['current_candidate_exact_documents'],'shorttail20_current_matches':reconciliation['shorttail20_failedwindow_diagnostic']['current_candidate_exact_documents'],'selected_body_bytes_read':0,'inputs_unchanged':True})
 finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':run()
