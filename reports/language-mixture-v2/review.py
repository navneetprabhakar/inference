"""Reproduce counts from fixed manual judgments; never admit or mutate candidates."""
import collections,hashlib,json,pathlib,re,sqlite3,time,shutil
R=pathlib.Path(__file__).resolve().parents[2]; D=R/'data/language-mixture-v2'; V=R/'data/language-mixture-v1'; start=time.monotonic()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check():
 assert time.monotonic()-start<900
 assert not(R/'runs/STOP').exists() and not(D/'STOP').exists()
 assert shutil.disk_usage(R).free>20*1024**3
check(); receipt=json.loads((D/'quality-sample-receipt.json').read_text())
for p,key in [(D/'quality-sample.jsonl','sample_sha256'),(V/'candidates.sqlite','candidate_database_sha256'),(V/'partial-candidate-manifest.json','candidate_manifest_sha256'),(V/'custody.json','custody_sha256'),(V/'candidate-verification.json','candidate_verification_sha256')]:assert sha(p)==receipt[key]
rows=[json.loads(l) for l in (D/'quality-sample.jsonl').read_text().splitlines()]
reviews={10:'Ambiguous night/day timeline.',16:'Forced vocabulary and awkward grammar.',27:'Unmotivated gate/key causality.',28:'Disconnected snack detail and forced moral.',34:'Image-dependent opening and broad directional biology simplification; not fact-checked.',36:'Unsupported strongest-correlation claim.',38:'Overconfident universal disease assertion; anecdotal authority, not fact-checked.',39:'Product promotion and missing demonstration reference.',40:'Missing opening letters/quotation marks; otherwise coherent report.',41:'Truncated opening quote and broken URL extraction.',43:'Sweeping organic-health claim and historical labeling rules; not verified.',44:'School promotion and historical policy claims; coherent.',47:'Article/comments concatenation and deliberately malformed quoted language.',53:'Tourism superlatives and broad endemic claim, not verified.',55:'Unsupported universal LEED requirement and broad cleaning claim.',58:'Overgeneralizations about all carbon/carbohydrates; missing diagrams; not independently fact-checked.',60:'Repeated advice and copyright/footer boilerplate.',61:'Literal HTML and long references; main debate is coherent.',62:'Newsletter contamination and taxonomic terminology concerns; not externally fact-checked.',64:'Long repetitive generic how-to with exaggerated ease claims.'}
holds={17:'Missing-friend plot abandoned for unrelated dead jellyfish.',20:'Cannot-swim character instantly dives; forced dictionary metaphor.',22:'Tornado removes puppy; resolution and ownership moral unsupported.',35:'Dismissive snakebite treatment claim warrants exclusion pending specialist verification.',37:'Stitched essay advice with disconnected opening/referents.',46:'Dictionary example list with unrelated navigation rather than coherent exposition.',48:'Confused drug/treatment statement and speculative supplements.',49:'Repeated SEO questions, contradictory loan generalizations and broken sentence.',54:'Sweeping cure/detox claims and category-confused free-radical explanation.',57:'Service SEO and large unrelated link list.',59:'Explicit Wikipedia derivative escapes domain-only exclusion.',63:'Sweeping solar availability/transmission claims and promotional repetition.'}
judgments=[]
for n,row in enumerate(rows,1):
 rating='hold' if n in holds else ('review' if n in reviews else 'retain')
 judgments.append({k:row[k] for k in ['source','doc_id','quartile','tokens']}|{'sample_number':n,'rating':rating,'reason':holds.get(n,reviews.get(n,'Readable source-appropriate narrative/exposition; no material issue found in this limited review.'))})
(D/'quality-judgments.json').write_text(json.dumps(judgments,indent=2)+'\n')
# Conservative proposal: defer every flagged sample, not just strongest holds.
manual={r['doc_id'] for r in judgments if r['rating']!='retain'}
excluded=set(json.loads((V/'custody.json').read_text())['excluded_doc_ids'])
counts=collections.defaultdict(lambda:collections.Counter());removed=[]
con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True)
for n,(did,source,split,tokens,url,text) in enumerate(con.execute('select doc_id,source,split,tokens,canonical_url,text from documents')):
 if n%2000==0:check()
 if source not in ('stories','web') or did in excluded:continue
 reasons=[]; low=text.casefold()
 if did in manual:reasons.append('flagged_sample')
 if source=='web' and ('newworldencyclopedia.org' in (url or '').casefold() or any(x in low for x in ('rewrote and completed the wikipedia article','imported to new world encyclopedia','derived from wikipedia','copied from wikipedia'))):reasons.append('explicit_wikipedia_derivative')
 key=source+':'+split;counts[key]['before_docs']+=1;counts[key]['before_tokens']+=tokens
 if reasons:
  counts[key]['removed_docs']+=1;counts[key]['removed_tokens']+=tokens;removed.append({'doc_id':did,'source':source,'split':split,'tokens':tokens,'reasons':reasons})
 else:counts[key]['remaining_docs']+=1;counts[key]['remaining_tokens']+=tokens
summary={'state':'review_complete_proposed_exclusions_only_not_admitted','training_admitted':False,'sample_counts':{s:dict(collections.Counter(j['rating'] for j in judgments if j['source']==s)) for s in ('stories','web')},'quota_counts':dict(counts),'quota_30m_each_available':all(counts[s+':train']['remaining_tokens']>=30000000 for s in ('stories','web')),'rules':['Defer all individually review/hold-rated samples by exact ID.','Web: exclude URL containing newworldencyclopedia.org OR casefolded text containing any of: rewrote and completed the wikipedia article; imported to new world encyclopedia; derived from wikipedia; copied from wikipedia.'],'limitations':['Manual sample exclusions do not repair similar unreviewed documents.','Narrow derivative rule is not comprehensive mirror or semantic contamination detection.','Not external factual verification or statistical certification.','Token counts include per-document EOT and are not final packed training targets.'],'sample_receipt_sha256':sha(D/'quality-sample-receipt.json'),'judgments_sha256':sha(D/'quality-judgments.json'),'review_code_sha256':sha(pathlib.Path(__file__)),'elapsed_seconds':time.monotonic()-start}
(D/'proposed-exclusions.json').write_text(json.dumps(removed,indent=2)+'\n');summary['exclusions_sha256']=sha(D/'proposed-exclusions.json')
(D/'quality-review.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
