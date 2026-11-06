import collections,hashlib,json,os,pathlib,re,sqlite3,time
R=pathlib.Path(__file__).resolve().parents[2];D=R/'data/sft-readiness-v5';V=R/'data/sft-readiness-v3';W=R/'data/sft-readiness-v4';KEEP={'smol-magpie-ultra-short','smol-summarize-20k','smollm-rewrite-30k'}
FICTION=re.compile(r'\b(?:role[ -]?play|pretend|fictional|assume the role|act as|imagine (?:you|yourself)|you are (?:an? |the )?(?:\d+[ -]year[ -]old|old prospector|prospector|police officer|dragon|dwarf|wizard|elf|elven|journalist|antique book seller))\b',re.I)
DRAFT=re.compile(r'\b(?:rewrite|rephrase|draft|write (?:an? |the |my )?(?:email|letter|message|story|dialogue|scene|script)|edit (?:this|my|the) (?:text|email|letter)|translate)\b',re.I)
DONE=re.compile(r"\bI(?:'ve|’ve| have| had)?(?:\s+(?:just|already))?\s+(?:found|located|booked|scheduled|emailed|sent|reserved|browsed|searched|set (?:a |the |your )?reminder)\b",re.I)
FUTURE=re.compile(r"\bI(?:'ll|’ll| will| am going to| can)(?:\s+(?:now|also|proceed with|help (?:you )?(?:by )?))?\s+(?:find (?:you |a |an |some |local |nearby)|book\b|schedul\w*|email\b|send\b|reserve\b|browse\b|search (?:the web|online)|set (?:a |the |your )?reminder)",re.I)
LOCAL=re.compile(r'\b(?:there (?:are|is) (?:several |some |a few |many )?(?:\w+\s+){0,3}(?:in your area|near (?:you|your home))|(?:studios?|carpools?|restaurants?|appointments?) (?:are |is )?available (?:near you|in your area))\b',re.I)
EXIT=re.compile(r'\b(?:out of character|stop (?:the )?role.?play|back to reality|in real life|real (?:request|booking|appointment)|actually (?:book|schedule|send)|not (?:a |the )?(?:story|fiction|role.?play))\b',re.I)
CONTINUE=re.compile(r'\b(?:stay in character|continue (?:the )?(?:story|scene|role.?play)|in (?:the|this) (?:story|scene)|still (?:playing|that|the))\b',re.I)
def rules(h):
 out=set();prior_fiction=False;system_fiction=bool(h and h[0]['role']=='system' and FICTION.search(h[0]['text']))
 user='';current_fiction=False;ambiguous=False
 for index,m in enumerate(h):
  if m['role']=='user':
   user=m['text'];exit_role=bool(EXIT.search(user));explicit=bool(FICTION.search(user));continuation=bool(CONTINUE.search(user))
   current_fiction=not exit_role and (explicit or system_fiction or (continuation and prior_fiction))
   ambiguous=prior_fiction and not (exit_role or explicit or continuation or system_fiction)
   prior_fiction=current_fiction or (prior_fiction and not exit_role)
   if exit_role:system_fiction=False
   continue
  if m['role']!='assistant':continue
  # Current user state is updated by position, never list.index/equality.
  if current_fiction:continue
  if DRAFT.search(user):continue
  text=re.sub(r'"[^"\n]*"|“[^”\n]*”|```[\s\S]*?```','',m['text'])
  hits=[]
  if DONE.search(text):hits.append('completed_external_lookup_or_action')
  if FUTURE.search(text):hits.append('future_external_action')
  if LOCAL.search(text):hits.append('unsupported_local_availability')
  out.update(hits)
  if ambiguous and hits:out.add('ambiguous_roleplay_external_claim')
 return sorted(out)

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 os.nice(10);start=time.monotonic();D=R/'data/sft-readiness-v6';P=R/'data/sft-readiness-v5';assert not(D/'receipt.json').exists()
 files=[V/'candidates.sqlite',V/'custody.json',V/'quality-review.json',W/'excluded.json',W/'review.json',P/'excluded.json',P/'review.json',P/'receipt.json',pathlib.Path(__file__),pathlib.Path(__file__).with_name('FILTER_PROTOCOL.md'),pathlib.Path(__file__).with_name('verify_filter.py')];pins={str(p):sha(p) for p in files}
 ex=set(json.load(open(V/'custody.json'))['excluded_doc_ids'])|set(json.load(open(V/'quality-review.json'))['proposed_excluded_doc_ids'])|{x['doc_id'] for x in json.load(open(W/'excluded.json'))}|set(json.load(open(W/'review.json'))['proposed_additional_excluded_doc_ids'])|{x['doc_id'] for x in json.load(open(P/'excluded.json'))}|set(json.load(open(P/'review.json'))['proposed_additional_excluded_doc_ids'])
 con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True);counts=collections.defaultdict(collections.Counter);excluded=[]
 for i,(did,source,split,targets,h) in enumerate(con.execute('select doc_id,source,split,target_tokens,selected_history_json from documents')):
  if i%1000==0:assert time.monotonic()-start<600 and not(R/'runs/STOP').exists() and not(D/'STOP').exists()
  if did in ex:continue
  assert source in KEEP
  rs=rules(json.loads(h)) if source=='smol-magpie-ultra-short' else [];c=counts[source+':'+split];c['before_docs']+=1;c['before_targets']+=targets
  if rs:
   excluded.append(dict(doc_id=did,source=source,split=split,rules=rs));c['excluded_docs']+=1;c['excluded_targets']+=targets
   for rule in rs:c['rule_'+rule]+=1
  else:c['remaining_docs']+=1;c['remaining_targets']+=targets
 (D/'excluded.json').write_text(json.dumps(excluded,indent=2)+'\n');receipt=dict(state='rescreened_superset_exclusions_not_admitted',training_admitted=False,pins=pins,counts=dict(counts),new_excluded_ids=len(excluded),excluded_sha256=sha(D/'excluded.json'),seconds=time.monotonic()-start,quality_sample='No reroll; retain prior frozen reviews and disclose roleplay-claim ambiguity deferral.');(D/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
