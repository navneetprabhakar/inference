import collections,hashlib,json,os,pathlib,re,sqlite3,time
R=pathlib.Path(__file__).resolve().parents[2];D=R/'data/sft-readiness-v5';V=R/'data/sft-readiness-v3';W=R/'data/sft-readiness-v4';KEEP={'smol-magpie-ultra-short','smol-summarize-20k','smollm-rewrite-30k'}
FICTION=re.compile(r'\b(?:role[ -]?play|pretend|fictional|assume the role|act as|imagine (?:you|yourself)|you are (?:an? |the )?(?:\d+[ -]year[ -]old|old prospector|prospector|police officer|dragon|dwarf|wizard|elf|elven|journalist|antique book seller))\b',re.I)
DRAFT=re.compile(r'\b(?:rewrite|rephrase|draft|write (?:an? |the |my )?(?:email|letter|message|story|dialogue|scene|script)|edit (?:this|my|the) (?:text|email|letter)|translate)\b',re.I)
DONE=re.compile(r"\bI(?:'ve|’ve| have| had)?(?:\s+(?:just|already))?\s+(?:found|located|booked|scheduled|emailed|sent|reserved|browsed|searched|set (?:a |the |your )?reminder)\b",re.I)
FUTURE=re.compile(r"\bI(?:'ll|’ll| will| am going to| can)(?:\s+(?:now|also|proceed with|help (?:you )?(?:by )?))?\s+(?:find (?:you |a |an |some |local |nearby)|book\b|schedul\w*|email\b|send\b|reserve\b|browse\b|search (?:the web|online)|set (?:a |the |your )?reminder)",re.I)
LOCAL=re.compile(r'\b(?:there (?:are|is) (?:several |some |a few |many )?(?:\w+\s+){0,3}(?:in your area|near (?:you|your home))|(?:studios?|carpools?|restaurants?|appointments?) (?:are |is )?available (?:near you|in your area))\b',re.I)
def rules(h):
 context='';out=set()
 for m in h:
  if m['role'] in ('system','user'):context+='\n'+m['text']
  if m['role']!='assistant' or FICTION.search(context):continue
  user=next((x['text'] for x in reversed(h[:h.index(m)]) if x['role']=='user'),'')
  if DRAFT.search(user):continue
  text=re.sub(r'"[^"\n]*"|“[^”\n]*”|```[\s\S]*?```','',m['text'])
  if DONE.search(text):out.add('completed_external_lookup_or_action')
  if FUTURE.search(text):out.add('future_external_action')
  if LOCAL.search(text):out.add('unsupported_local_availability')
 return sorted(out)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 os.nice(10);start=time.monotonic();assert not(D/'receipt.json').exists()
 files=[V/'candidates.sqlite',V/'custody.json',V/'quality-review.json',V/'quality-selection.json',W/'receipt.json',W/'excluded.json',W/'review.json',W/'samples.jsonl',pathlib.Path(__file__),pathlib.Path(__file__).with_name('FILTER_PROTOCOL.md'),pathlib.Path(__file__).with_name('verify_filter.py')];pins={str(p):sha(p) for p in files}
 ex=set(json.load(open(V/'custody.json'))['excluded_doc_ids'])|set(json.load(open(V/'quality-review.json'))['proposed_excluded_doc_ids'])|{x['doc_id'] for x in json.load(open(W/'excluded.json'))}|set(json.load(open(W/'review.json'))['proposed_additional_excluded_doc_ids']);prior={x['doc_id'] for x in json.load(open(V/'quality-selection.json'))['sample_ids']}|{json.loads(l)['doc_id'] for l in open(W/'samples.jsonl')}
 con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True);con.row_factory=sqlite3.Row;counts=collections.defaultdict(collections.Counter);excluded=[];candidates=[]
 for i,row in enumerate(con.execute('select doc_id,source,split,input_tokens,target_tokens,selected_history_json from documents')):
  if i%1000==0:assert time.monotonic()-start<900 and not(R/'runs/STOP').exists() and not(D/'STOP').exists()
  r=dict(row)
  if r['doc_id'] in ex:continue
  reasons=['deferred_small_cohort'] if r['source'] not in KEEP else rules(json.loads(r['selected_history_json'])) if r['source']=='smol-magpie-ultra-short' else []
  c=counts[r['source']+':'+r['split']];c['before_docs']+=1;c['before_targets']+=r['target_tokens']
  if reasons:
   excluded.append({'doc_id':r['doc_id'],'source':r['source'],'split':r['split'],'rules':reasons});c['excluded_docs']+=1
   for reason in reasons:c['rule_'+reason]+=1
  else:
   c['remaining_docs']+=1;c['remaining_targets']+=r['target_tokens']
   if r['source']=='smol-magpie-ultra-short' and r['split']=='train' and r['doc_id'] not in prior:candidates.append(r)
 candidates.sort(key=lambda r:(r['input_tokens'],r['doc_id']));chosen=[];strata=[]
 for q in range(4):
  pool=[r for i,r in enumerate(candidates) if min(3,i*4//len(candidates))==q]
  for multi in (False,True):
   group=[r for r in pool if (sum(x['role']=='user' for x in json.loads(r['selected_history_json']))>1)==multi];group.sort(key=lambda r:hashlib.sha256(('sft-v5-quality-20261106|'+r['doc_id']).encode()).hexdigest());strata.append(dict(quartile=q+1,multi=multi,available=len(group),selected=min(2,len(group))));chosen.extend(dict(r,quartile=q+1,multi=multi) for r in group[:2])
 (D/'excluded.json').write_text(json.dumps(excluded,indent=2)+'\n');(D/'samples.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in chosen));receipt=dict(state='filtered_not_admitted_samples_frozen_before_review',pins=pins,counts=dict(counts),strata=strata,sample_count=len(chosen),sample_sha256=sha(D/'samples.jsonl'),excluded_sha256=sha(D/'excluded.json'),seconds=time.monotonic()-start);(D/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt['counts']));print('strata',strata)
if __name__=='__main__':main()
