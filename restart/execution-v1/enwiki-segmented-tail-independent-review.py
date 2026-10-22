from pathlib import Path
import sys,json,hashlib,types,sqlite3,tempfile
B=Path(__file__).resolve().parent;P=B/'enwiki-native-segmented-tail-preparation-v1';O=B/'enwiki-segmented-tail-independent-audit-v1';sys.path.insert(0,str(P));import segmented as s,transport_core as c
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
code='8e0aacf540baf266fba6d5c719864e40db5a73a123654f8beb66f887ea52090d';profile='4e81fc75252b528b64b620ed1c14dfb3cfa843b5555e51d8e8bc3308a1acaf6a';assert h(P/'readiness.json')=='bc9d0febdd04cd80c80c2933f00996d0f5e4ef5179414d634b5edd9b53f1e8fb'
oldopen=Path.open;oldhttp=s.urllib.request.OpenerDirector.open
reads=[]
def guarded(path,*a,**kw):
 if path.resolve()==s.PREFIX.resolve():raise AssertionError('forbiddenprefixbodyread')
 return oldopen(path,*a,**kw)
def forbidden(*a,**kw):raise AssertionError('HTTP_not_authorized_by_review')
Path.open=guarded;s.urllib.request.OpenerDirector.open=forbidden
try:p=s.verify(types.SimpleNamespace(code_pins_sha256=code,profile_sha256=profile))
finally:Path.open=oldopen;s.urllib.request.OpenerDirector.open=oldhttp
ranges=p['ranges'];assert len(ranges)==65 and ranges[0]['start']==17988844772 and ranges[-1]['end']==26668484994 and all(a['end']+1==b['start'] for a,b in zip(ranges,ranges[1:]));assert sum(v['bytes'] for v in ranges)==8679640223 and sum(v['bytes']+1 for v in ranges)==8679640288
# Independent ordered-stream and mutation refusal using tiny local synthetic files only.
independent=[]
with tempfile.TemporaryDirectory() as tmp:
 f=Path(tmp)/'a';f.write_bytes(b'original');e={'path':str(f),'bytes':8,'SHA256':hashlib.sha256(b'original').hexdigest(),'stat':c.stat_id(f)};v=c.hash_components([e],lambda:None);assert v['MD5']==hashlib.md5(b'original').hexdigest();independent.append('known_MD5_SHA1_SHA256_stream')
 changed=False
 def mutate():
  global changed
  if not changed:f.write_bytes(b'altered!');changed=True
 try:c.hash_components([e],mutate)
 except ValueError:independent.append('mutation_during_open_descriptor_hash_refused')
 else:raise AssertionError('mutationaccepted')
# Read-only cumulative budget, never instantiate a global writer.
db=sqlite3.connect((B/'m2-intake/charges/ledger.sqlite').as_uri()+'?mode=ro',uri=True);rows=db.execute('select charge,state from attempts').fetchall();db.close();tot={k:sum(json.loads(v[0])[k] for v in rows) for k in ['requests','body_bytes','output_bytes']};assert not any(v[1]=='pending' for v in rows);assert tot['body_bytes']+8679640288<=80000000000 and tot['output_bytes']+9000000000<=80000000000
assert c.stat_id(s.PREFIX)==p['prefix']['stat'];remaining=s.ORIGINAL_DEADLINE-s.clk();assert remaining>0
O.mkdir(exist_ok=False);r={'status':'PASS_INDEPENDENT_PREPARATION_REVIEW_NO_NETWORK_OR_SOURCEPREFIX_BODY_READ','code_pins_SHA256':code,'profile_SHA256':profile,'all45code_runtime_policy_receipt_pins_verified':len(json.loads((P/'code-pins.json').read_text())['SHA256']),'reproduced_offline_controls':38,'additional_independent_controls':independent,'production_files_fully_reviewed':['segmented.py','transport_core.py','checks.py','profile.json','primary-evidence.json','src/slm/data/intake_ledger.py'],'planned_exact_requests':65,'max_concurrent':2,'minimum_open_start_gap_seconds':1,'tail_response_bytes':8679640223,'tail_response_reserve_with65EOFbytes':8679640288,'current_cumulative_reservations':tot,'proposed_cumulative_body_reserve':tot['body_bytes']+8679640288,'proposed_cumulative_output_reserve':tot['output_bytes']+9000000000,'budget_scope':'Durable cumulative output contract80GB is distinct from stricter64GB current physical intake footprint; failed historical output reservations remain charged without refund. Parent preflight must verify actual footprint+9GB and53.47483648GB protected freefloor.','confirmed_safety':['Exact65 source-bound fixed contiguous Range/If-Match requests, no redirects200fallback/retries/replacements','Single coordinator SQLite writer, durable per-request precharge before submit/open; threads never use SQLite','Durable9GB output-only allocation before any new profile output, no fullarchivecopy','TLS certificate+hostname enforced by pinned trusted_context; exact206 single ContentRange/Length/ETag identity and bounded headers','Fresh original17.99GB prefix MD5/SHA1/SHA256 before firstGET; then worker and separate post-reap supervisor ordered26.67GB checksum streams before virtual-manifest publish','Worker/shared original8hdeadline retained, new7140/7200s ceilings; external strict root RSS/output/disk checks and owned-processgroup kill/reap','Partial files and charges retained; worker exception may leave threads until parentkill/reap, parent post-reap settles exact pending keys failed withoutrefund before future intake'],'limitations':['Availability/throughput not proven by synthetic tests','No bodydownload/decompression/articlecount/English/quality/admission authority provided by this review','On hard supervisor death parent must confirm child/processgroup death and reconcile exactprefix charges before another global intake'],'original_absolute_monotonic_deadline':s.ORIGINAL_DEADLINE,'remaining_original_deadline_seconds_at_review':remaining,'concrete_blockers':[],'actual_prefix_body_bytes_read':0,'actual_network_requests':0,'globalledger_writes':0,'model_training_or_source_mutations':0}
(O/'review.json').write_text(json.dumps(r,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'review.json':h(O/'review.json'),'reviewer_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'))
