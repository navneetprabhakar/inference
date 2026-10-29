"""Offline fail-closed rebinding of already captured primary prose. No network."""
import collections,gzip,hashlib,html,json,re,sqlite3,sys,urllib.parse
from pathlib import Path
from html.parser import HTMLParser
P=Path(__file__).resolve().parent; ROOT=P.parents[2]; OLD=ROOT/'restart/coherence-g0-2026-10-29/broad'; A=ROOT/'restart/coherence-g0-v2-2026-10-29/acquisition'
def digest(x):return hashlib.sha256(x.encode() if isinstance(x,str) else x).hexdigest()
def read(p):return json.loads(p.read_text())
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
class Canon(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.events=[];self.parts=[]
 def handle_starttag(self,t,a):
  self.events.append(['start',t,sorted(a)])
  if t in ['p','li','br','h1','h2','h3']:self.parts.append('\n')
 def handle_endtag(self,t):
  self.events.append(['end',t])
  if t in ['p','li','h1','h2','h3']:self.parts.append('\n')
 def handle_data(self,d):
  self.parts.append(d)
  if d.strip():self.events.append(['text',re.sub(r'\s+',' ',d).strip()])
 def handle_comment(self,d):self.events.append(['comment',d])
 def handle_decl(self,d):self.events.append(['decl',d])
def canonical(body):
 p=Canon();p.feed(body);p.close();text='\n'.join(x.strip() for x in ''.join(p.parts).splitlines() if x.strip());return p.events,text
def body_equal(a,b):return canonical(a)==canonical(b)
def content_event(e):return any(k in e for k in ['body','title','last_body','last_title'])
def noncontent(e):return not content_event(e) and (e.get('revision_type')=='vote_based' or 'tags' in e or 'last_tags' in e)
def latest(h,k):return max([e for e in h if k in e],key=lambda e:(e.get('revision_number',0),e['creation_date']),default={})
def bind(pair,r,hist):
 q,a=pair['question'],pair['answer'];assert pair['site']==r['site'];assert q['question_id']==r['question_id']==a['question_id'];assert a['answer_id']==r['answer_id']==q['accepted_answer_id']
 ev=[]
 for i,x in enumerate([q,a]):
  assert digest(x['body'])==r['component_body_sha256'][i]
  if x.get('content_license')!='CC BY-SA 4.0' or not all(x.get('owner',{}).get(k) for k in ['display_name','link']):return 'current_owner_or_license',None
  h=hist.get(r['site']+':'+str(x['question_id'] if i==0 else x['answer_id']))
  if not h:return 'missing_complete_history',None
  prose=[e for e in h if content_event(e)]
  if any(not content_event(e) and not noncontent(e) for e in h):return 'unknown_revision_semantics',None
  if not prose:return 'no_content_revision',None
  if any(e.get('content_license')!='CC BY-SA 4.0' or not e.get('user',{}).get('display_name') for e in prose):return 'unresolved_content_license_or_contributor',None
  b=latest(prose,'body')
  if not b or not body_equal(x['body'],b['body']):return 'body_revision_mismatch',None
  if i==0:
   t=latest(prose,'title')
   if not t or html.unescape(q['title'])!=html.unescape(t['title']):return 'title_revision_mismatch',None
  ev.append(dict(current_body_sha256=digest(x['body']),revision_body_sha256=digest(b['body']),body_revision_guid=b['revision_guid'],binding='exact' if x['body']==b['body'] else 'identical_HTML_events_and_extracted_prose',content_revisions=prose,noncontent_revision_guids=[e['revision_guid'] for e in h if not content_event(e)]))
 expected='Question: '+html.unescape(q['title'])+'\n'+canonical(q['body'])[1]+'\n\nAccepted answer:\n'+canonical(a['body'])[1]
 assert expected==r['text'] and digest(expected)==r['h']
 return None,ev

def main():
 assert not (P/'freeze.json').exists(),'Frozen outputs immutable'
 receipts=read(A/'primary-receipts.json');rawposts={};groups=collections.defaultdict(dict);pins={}
 for receipt in receipts:
  if receipt['status']!='COMPLETE':continue
  key=receipt['key'];f=A/'private'/('revisions' if '-revisions-' in key else 'primary')/(key+'.json')
  if not f.exists():continue
  raw=f.read_bytes();assert digest(raw)==receipt['sha256'];pins[str(f.relative_to(ROOT))]=digest(raw);data=json.loads(raw);url=urllib.parse.urlparse(receipt['url']);params=urllib.parse.parse_qs(url.query);site=params['site'][0]
  if '-revisions-' in key:groups[(site,url.path)][int(params['page'][0])]=data
  else:
   for x in data['items']:
    typ='answer' if 'answer_id' in x else 'question';rawposts[(site,typ,x[typ+'_id'])]=x
 hist={}
 for (site,path),pages in groups.items():
  if sorted(pages)!=list(range(1,max(pages)+1)) or pages[max(pages)].get('has_more'):continue
  if any(not pages[i].get('has_more') for i in range(1,max(pages))):continue
  ids=list(map(int,path.split('/posts/')[1].split('/')[0].split(';')));events=[e for d in pages.values() for e in d['items']];assert all(e['post_id'] in ids for e in events)
  for pid in ids:hist[site+':'+str(pid)]=[e for e in events if e['post_id']==pid]
 pairs={}
 for f in sorted((A/'private/primary').glob('*-pairs.jsonl.gz')):
  pins[str(f.relative_to(ROOT))]=digest(f.read_bytes())
  for line in gzip.open(f,'rt'):
   r=json.loads(line)
   for typ in ['question','answer']:assert r[typ]==rawposts[(r['site'],typ,r[typ][typ+'_id'])]
   pairs[(r['site'],r['question']['question_id'])]=r
 candidates=[];holds=[]
 for r in read(A/'private/selected-primary.json'):
  reason,e=bind(pairs[(r['site'],r['question_id'])],r,hist)
  if reason:holds.append(dict(h=r['h'],reason=reason,tokens=r['tokens']))
  else:candidates.append({**r,'provenance_evidence':e,'status':'CANDIDATE_NOT_ADMITTED'})
 save('private/provenance-candidates.json',candidates);save('private/holds.json',holds)
 prior=read(OLD/'private/semantic-sample.json');assert len(prior)==100;excluded={r['h'] for r in prior}|set(read(OLD/'policy.json')['prior_sample_hashes_excluded'])
 rows=[r for r in read(OLD/'private/repaired-candidate-manifest.json') if r['h'] not in excluded]
 for r in candidates:
  if r['h'] in excluded:continue
  b=int(digest('coherence-g0-family-v1:'+r['family']),16)%10
  rows.append({k:v for k,v in r.items() if k not in ['text','provenance_evidence']}|{'split':'development' if b==0 else 'reserve' if b==1 else 'train','source':'new_primary'})
 assert len({r['h'] for r in rows})==len(rows)
 counts={s:{d:sum(r['tokens'] for r in rows if r['split']==s and r['domain']==d) for d in ['everyday','procedural','educational']} for s in ['train','development','reserve']}
 supply=sum(counts['train'].values())>=4000000 and all(n>=1000000 for n in counts['train'].values())
 save('private/combined-manifest.json',rows)
 policy=dict(normalization='Require both identical parsed HTML event stream (tags, attributes, decoded text; insignificant whitespace folded) AND exact extracted prose. Never normalize spelling, punctuation, word order, links or paragraphs.',revision_semantics='Body/title/last_body/last_title imply content and require actual license and display attribution. Only positively identified tag-only or vote-only events can omit prose license. Unknown events held. Latest revision_number breaks timestamp ties.',binding='Captured receipt-hashed raw primary objects, exact accepted-answer/question/site IDs, raw body SHA, current owner/license, complete receipt-hashed pagination, current title and body against latest content revision.',excluded_hashes=sorted(excluded),split=read(OLD/'policy.json')['split'],sample_seed='291029-g0-v3-source',semantic_gate='100 whole texts:34 everyday33 procedural33 educational, max5 major zero severe. Stop at sixth major.',status='CANDIDATE_NOT_ADMITTED',admitted_tokens=0)
 save('policy.json',policy)
 result=dict(status='AWAITING_SEMANTIC_REVIEW' if supply else 'STOP_DATA_ADMISSION',primary_documents=len(candidates),primary_tokens=sum(r['tokens'] for r in candidates),holds=dict(collections.Counter(r['reason'] for r in holds)),binding_counts=dict(collections.Counter(e['binding'] for r in candidates for e in r['provenance_evidence'])),token_counts=counts,supply_pass=supply,admitted_tokens=0,network_requests=0)
 if supply:
  oldpolicy=read(OLD/'policy.json');src=ROOT/oldpolicy['source'];assert digest(src.read_bytes())==oldpolicy['source_sha256'];db=sqlite3.connect('file:'+str(src)+'?mode=ro',uri=True);texts={r['h']:r['text'] for r in candidates};sample=[]
  for d,n in [('everyday',34),('procedural',33),('educational',33)]:
   draw=sorted([r for r in rows if r['split']=='train' and r['domain']==d],key=lambda r:digest(policy['sample_seed']+':'+r['h']))[:n];assert len(draw)==n
   for r in draw:
    txt=texts[r['h']] if r['h'] in texts else db.execute('SELECT text FROM docs WHERE h=?',(r['h'],)).fetchone()[0];assert digest(txt)==r['h'];sample.append({**r,'text':txt})
  db.close();save('private/semantic-sample.json',sample);result['sample_documents']=len(sample)
 save('result.json',result)
 for f in [A/'private/selected-primary.json',A/'primary-receipts.json',OLD/'policy.json',OLD/'private/repaired-candidate-manifest.json',OLD/'private/semantic-sample.json']:pins[str(f.relative_to(ROOT))]=digest(f.read_bytes())
 save('input-pins.json',pins);save('freeze.json',{str(f.relative_to(P)):digest(f.read_bytes()) for f in P.rglob('*') if f.is_file() and f.name!='freeze.json'});print(json.dumps(result,indent=2))
if __name__=='__main__':main()
