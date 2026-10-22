import collections,hashlib,json,pathlib,signal,subprocess,time
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('verification60seconds')))
signal.alarm(60)
START=time.monotonic();HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parents[1];PREP=BASE/'gutenberg-four-custody-preparation-v2';OUT=HERE.parent/'gutenberg-four-current-custody-v2'
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
def rows(n):return [json.loads(x) for x in (OUT/n).read_text().splitlines()]
assert sha(PREP/'code-pins.json')=='acc2eba693f00f75d3e8a5300a0fa998a6e5bcaa4e4152858526d9ff545045f9'
assert sha(PREP/'profile.json')=='79800e2221ef2a6b194b13b81d34c72e67c01819c62f91e82f3bb904bce5cc93'
registry=load(PREP/'code-pins.json');checked=0;inputbytes=0
for name,digest in registry['input_SHA256'].items():
 p=pathlib.Path(name);assert p.is_file() and not p.is_symlink() and sha(p)==digest,name
 checked+=1;inputbytes+=p.stat().st_size
supervisor=load(OUT/'supervisor.json');ownership=load(OUT/'ownership.json')
assert supervisor['status']=='PARTIAL_SCREEN_NO_RETRY_NO_ZERO_CLAIM'
assert supervisor['worker_exit_code']==-9 and supervisor['reason']=='process_tree_RSS1GB'
assert supervisor['result_SHA256']==sha(OUT/'result.json')
assert not (OUT/'result.json').read_text().strip()
assert supervisor['elapsed_seconds']<540 and supervisor['peak_observed_process_tree_RSS_bytes']>1_000_000_000
for key in ['supervisor_PID','worker_PID']:
 p=subprocess.run(['/bin/ps','-p',str(ownership[key]),'-o','pid='],capture_output=True,text=True)
 assert not p.stdout.strip(),key
assert not (OUT/'source-coverage.json').exists() and not (OUT/'family-custody.json').exists()
artifacts={f.name:{'bytes':f.stat().st_size,'SHA256':sha(f)} for f in OUT.iterdir() if f.is_file()}
assert sum(x['bytes'] for x in artifacts.values())==supervisor['output_bytes']<32_000_000
assert (OUT/'CPP-containment.tsv').read_bytes()==b'' and load(OUT/'four-internal-overlap.json')==[]
candidates={r['ebook_ID']:r for r in load(PREP/'candidates.json')};matches=rows('body-matches.jsonl');counts=collections.Counter()
assert len(matches)==8
for r in matches:
 c=candidates[r['candidate_ebook_ID']];path=r['source_identity'].split('#',1)[0]
 assert r['candidate_current_SHA256']==c['text_SHA256']
 assert r['disposition']=='EXACT_REGISTERED_CURRENT_UNIT_OR_CAPTURED_RAW_ANCESTOR_ALIAS_NOT_NEW_DOCUMENT'
 assert path in [c['file'],c['captured_raw_source_ancestor']['path']]
 if path==c['file']:assert r['match']['normalized_exact'] is True
 assert r['source_role'] not in ['explicit_protected','historical_heldout','current_development','current_test']
 counts[r['candidate_ebook_ID']]+=1
assert counts=={3028:2,34616:2,2521:2,8530:2}
holds=rows('coverage-holds.jsonl');assert len(holds)==1 and all(not r['required_current_candidate_or_protected_coverage'] for r in holds)
assert holds[0]['reason']=='document_word_cap' and '/pmc-native-discovery-pilot-v1/response-001.xml#file' in holds[0]['identity']
leads=rows('metadata-aliases.jsonl');assert len(leads)==1
assert leads[0]['candidate_ebook_ID']==8530 and leads[0]['metadata']['title']=='Asahel Lathrop'
result={'status':'VERIFIED_TERMINAL_PARTIAL_NO_RETRY_NO_COVERAGE_CLEARANCE','supervisor':supervisor,'inputs_rehashed':checked,'input_bytes_rehashed':inputbytes,'worker_and_supervisor_absent':True,'artifact_hashes':artifacts,'observed_saved_body_matches':len(matches),'saved_matches_all_registered_self_or_raw_ancestor_aliases':True,'observed_saved_required_holds':0,'observed_saved_optional_context_limits':len(holds),'lexical_metadata_lead':leads[0],'scope':['Result slot blank after hard RSS kill; no complete worker stats or source coverage/family receipts exist.','Saved empty CPP output is scoped to that completed command; independent full-screen clearance is not claimed.','Legacy/protection phase progression follows pinned worker control flow, but final reconciliation receipt was not published.','No observed required hold is not proof of complete required coverage.','No retries, admission, tokenizer, model, network or global ledger writes.'],'new_admitted_documents':0,'new_admitted_tokens':0,'elapsed_seconds':time.monotonic()-START}
(HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
manifest={'files':{f.name:{'SHA256':sha(f),'bytes':f.stat().st_size} for f in HERE.iterdir() if f.is_file()}}
(HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'status':result['status'],'inputs_rehashed':checked,'elapsed':result['elapsed_seconds'],'manifest_SHA256':sha(HERE/'manifest.json')}))
