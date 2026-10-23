"""CPU-only inventory of existing candidate records; not a corpus admission."""
import sys,json,time,gzip,sqlite3,hashlib,re,zlib,collections,importlib.util
from urllib.parse import urlsplit,unquote
from common import *
sys.path.insert(0,str(UPSTREAM))
from tokenizer import Tokenizer
SOURCE_DB=PROJECT/'restart/execution-v1/m2-intake/pressbooks-full-repaired-filter-impact-v1/candidate.sqlite'
GRANTS={'creativecommons.org/licenses/by/4.0/':'CC-BY-4.0','creativecommons.org/licenses/by-sa/4.0/':'CC-BY-SA-4.0','creativecommons.org/publicdomain/zero/1.0/':'CC0-1.0'}
spec=importlib.util.spec_from_file_location('family_leads',PROJECT/'restart/execution-v1/pressbooks-full-family-lead-preparation-v2/derive.py');family_leads=importlib.util.module_from_spec(spec);spec.loader.exec_module(family_leads)
GENRE=re.compile(r'\b(?:anthology|anthologies|poetry|poems|hymns|spiritual songs|autobiography|memoirs?|diaries|fiction|novels?|short stories|conference.*program)\b',re.I)
# High-stakes domains are held, not declared false or unlawful.
HIGH=re.compile(r'\b(?:nurs\w*|medic\w*|clinic\w*|anatom\w*|physiolog\w*|pharmac\w*|disease\w*|law|legal|financ\w*|accounting|econom\w*|invest\w*|tax(?:es|ation)?|patient\w*|therap\w*)\b',re.I)
DEPEND=re.compile(r'\b(?:(?:as shown in|as illustrated in|refer to|see|using|use|from)\s+(?:figure|table)\s*\d|watch the|watch this|video below|video above|click here|click on|following diagram|image below|diagram below|exercise\s*\d|answer the following|questions on the back|on the back of this page|use the following table|password protected|forthcoming|coming soon|\[latex\]|\\\[)\b',re.I)
COMPONENT=re.compile(r'\b(?:all rights reserved|used with permission|permission of|adapted from|reprinted from|reproduced from|copyright by|noncommercial|non-commercial|no derivatives|no-derivatives)\b',re.I)
NAV=re.compile(r'\b(?:primary navigation|book contents navigation|previous/next navigation|show answer|show glossary)\b',re.I)
CLAIMS=re.compile(r'\b(?:dosage|prescrib\w*|diagnos\w*|treat(?:ment|ments)?|patient\w*|interest rates?|investment returns?|tax(?:es|ation)?|financial advice|legal advice)\b',re.I)

def grant(metadata):
 text=metadata.get('license','');found=re.findall(r'https?://([^\s<>\)]+)',text)
 if len(found)!=1:return None
 key=found[0].lower().rstrip('/')+'/'
 return GRANTS.get(key)
def domain(m,text):
 meta=' '.join(str(m.get(k,'')) for k in ['title','subject'])
 # Domain assignment is a filter proposal; full-text sample still must validate it.
 if re.search(r'\b(?:writing|reading|study|studying|research methods|composition|rhetoric|literacy|speaking|communicators|manual|tutorial|guide|gardening|design|computing|programming|academic success|college success|student success|learning strategies|education|learning|teaching|communication)\b',meta,re.I) and re.search(r'\b(?:first|next|steps?|strategies|tips|you can|you should|how to)\b',text,re.I):return 'procedural'
 if re.search(r'\b(?:interpersonal|communication|relationships|life skills|personal development|human relations|everyday|psychology|sociology|business|management|leadership|workplace|career|employment|human development|college success|student success)\b',meta,re.I):return 'everyday'
 return 'educational'
def normalize(s):return ' '.join(re.findall(r"[a-z0-9]+",s.lower()))
def main():
 phase='D0';check(phase);freeze_check(phase);assert read(ROOT/'R0/result.json')['status']=='PASS';tok=Tokenizer(str(UPSTREAM/'tokenizer.model'))
 db=sqlite3.connect('file:'+str(SOURCE_DB)+'?mode=ro',uri=True)
 want={h:dict(native_pending=True,prior=prior,family_uncertainty=uncertain,source_flags=flags) for h,prior,uncertain,flags in db.execute('select text_SHA256,prior_reviewed_or_held,family_uncertainty,source_flags from texts where candidate=1')}
 # All prior draw records are excluded from the fresh release, including unread draws.
 protocol=read(PROJECT/'restart/execution-v1/pressbooks-fresh400-semantic-review-protocol-v1/protocol.json');old=set()
 for lane in protocol['assignments'].values():
  if isinstance(lane,dict):
   for item in lane.get('records',[]):
    if 'text_SHA256' in item:old.add(item['text_SHA256'])
 for item in read(ROOT/'D0/filter-development-samples.json').values():old.add(item['h'])
 old.update(read(ROOT/'D0/source-draw-reconciliation.json')['all_prior_selection_hashes_excluded'])
 old.update(read(ROOT/'D0/media-code-development-samples.json'))
 cap=PROJECT/'restart/execution-v1/m2-intake/pressbooks-fresh400-whole-original-capture-v1'
 for path in cap.glob('*.text.utf8'):old.add(sha(path))
 payload=ROOT/'payloads';payload.mkdir(exist_ok=True);out=sqlite3.connect(payload/'broad-candidate.sqlite')
 out.execute('CREATE TABLE docs(h TEXT PRIMARY KEY,norm TEXT,family TEXT,domain TEXT,tokens INTEGER,text TEXT,ids BLOB,metadata TEXT,source_id INTEGER,ordinal INTEGER,line_sha TEXT,license TEXT)')
 counts=collections.Counter();native=collections.Counter();licenses=collections.Counter();families=collections.defaultdict(set);rejected_tokens=collections.Counter();seen=set();totalraw=0
 for sid,path,n in db.execute('select source_id,path,rows from sources order by source_id'):
  with gzip.open(path,'rb') as f:
   for ordinal,line in enumerate(f,1):
    totalraw+=1
    if totalraw%100==0:check(phase)
    r=json.loads(line);text=r['text'];h=hashlib.sha256(text.encode()).digest()
    if h not in want or h in seen:continue
    seen.add(h);c=want[h];m=r.get('metadata',{});g=grant(m);licenses[str(g)]+=1;counts['raw_distinct_candidate']+=1
    reason=None
    if c['prior'] or h.hex() in old:reason='prior_seen_or_selected'
    elif family_leads.derive(m.get('book_url'),m.get('url'))[0]!=1:reason='unresolved_family'
    elif g is None:reason='grant_not_in_frozen_prior_classes'
    url=m.get('url') or r.get('id');book=m.get('book_url');author=m.get('author');title=m.get('title')
    if reason is None and not all(isinstance(x,str) and x.strip() for x in [url,book,author,title]):reason='missing_provenance'
    meta=' '.join(str(m.get(k,'')) for k in ['title','subject'])
    if reason is None and GENRE.search(meta):reason='nonexpository_or_mixed_component_genre'
    if reason is None and HIGH.search(meta):reason='high_stakes_domain_hold'
    if reason is None and len(CLAIMS.findall(text))>=3:reason='high_stakes_claims_hold'
    if reason is None and COMPONENT.search(text):reason='component_or_grant_exception_hold'
    if reason is None and DEPEND.search(text):reason='unresolved_external_dependency'
    if reason is None and NAV.search(text):reason='navigation_assessment_or_attribution_components'
    if reason is None and (len(text)<400 or len(re.findall(r'[.!?](?:\s|$)',text))<3):reason='short_or_nonexpository'
    if reason is None and (text.count('http')>2 or text.count('|')>3 or (text.count('{')>2 and len(re.findall(r'[;{}=]',text))>len(re.findall(r'\b[a-zA-Z]+\b',text))*.1)):reason='reference_code_or_tabular_hold'
    if reason:
     counts[reason]+=1;continue
    ids=tok.encode(text.strip(),bos=True,eos=False);content=len(ids)-1
    if content>4096:counts['over4096_native_content_tokens']+=1;rejected_tokens['over4096']+=content;continue
    b=urlsplit(book);parts=[p for p in unquote(b.path).split('/') if p];family=family_leads.derive(book,url)[1];assert family
    if c['family_uncertainty'] or c['source_flags']&64:counts['legacy_family_flag_resolved_literal_prefix']+=1
    if not b.hostname or not parts:counts['unresolved_book_root']+=1;continue
    d=domain(m,text);norm=hashlib.sha256(normalize(text).encode()).hexdigest()
    out.execute('insert into docs values(?,?,?,?,?,?,?,?,?,?,?,?)',(h.hex(),norm,family,d,content,text,zlib.compress(__import__('numpy').array(ids,dtype=__import__('numpy').uint16).tobytes()),json.dumps(m,ensure_ascii=False),sid,ordinal,hashlib.sha256(line).hexdigest(),g))
    counts['provisional_filtered']+=1;native[d]+=content;families[d].add(family)
  out.commit()
  save(ROOT/'D0/inventory-progress.json',dict(raw_rows=totalraw,counts=dict(counts),provisional_native_content_tokens=dict(native),families_per_domain={k:len(v) for k,v in families.items()},epoch=time.time()))
 result=dict(status='PROVISIONAL_INVENTORY_NOT_ADMISSION',raw_rows=totalraw,original_distinct_candidate_count=len(want),distinct_candidates_found=len(seen),counts=dict(counts),licenses=dict(licenses),provisional_native_content_tokens=dict(native),provisional_BOS_boundaries=counts['provisional_filtered'],families_per_domain={k:len(v) for k,v in families.items()},source_families=len(set().union(*families.values())) if families else 0,prior_excluded_hashes=len(old),rights_quality_near_dedup_splits_not_cleared=True,usable_documents=0,usable_native_tokens=0,epoch=time.time())
 assert len(seen)==len(want)
 save(ROOT/'D0/inventory.json',result);print(json.dumps(result))
if __name__=='__main__':main()
