"""Supplemental protected spans for current admitted dev/test roles (not historical held flag)."""
import collections,hashlib,json,pathlib,sqlite3,sys,time
P=pathlib.Path(__file__).resolve().parent;E=P.parent;R=E.parents[1];sys.path.insert(0,str(R/'src'));from slm.restart.edu_filter import normalized
D=E/'gutenberg-overlap-v3';C=E/'gutenberg-novel-prose-v1';M=E/'m0-registry-v1';start=time.monotonic();h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
registry=json.loads((M/'registry.json').read_text());assert h(M/'artifacts/admitted-documents.jsonl')==registry['files']['admitted-documents.jsonl'];admitted=[json.loads(l) for l in (M/'artifacts/admitted-documents.jsonl').read_text().splitlines()];roles={int(r['audit_id']):r for r in admitted};protected={i:r for i,r in roles.items() if r['split'] in ['development','test']};assert len(protected)==7922
rows=[json.loads(l) for l in (C/'chapters.jsonl').read_text().splitlines()];norms=[normalized(r['text']) for r in rows];words=[v.split() for v in norms];idx32=collections.defaultdict(set);idx12=collections.defaultdict(list)
for i,w in enumerate(words):
 assert hashlib.sha256((C/rows[i]['file']).read_bytes()).hexdigest()==rows[i]['sha256']
 for off in range(len(w)-31):idx32[tuple(w[off:off+32])].add(i)
 for off in range(len(w)-11):idx12[tuple(w[off:off+12])].append((i,off))
def match(w):
 found={}
 if len(w)<12:
  for i,v in enumerate(norms):
   if v==' '.join(w):found[i]={'kind':'short_whole_document_exact'}
 elif len(w)<32:
  for i,off in idx12.get(tuple(w[:12]),[]):
   if words[i][off:off+len(w)]==w:found[i]={'kind':'full12_to31words','matched_normalized_text':' '.join(w)}
 else:
  for off in range(0,len(w)-31,16):
   for i in idx32.get(tuple(w[off:off+32]),[]):
    if i not in found:found[i]={'kind':'protected32_stride16','protected_word_offset':off,'matched_normalized_text':' '.join(w[off:off+32])}
 return found
assert 0 in match(words[0][47:79]);assert 0 in match(words[0][47:60]);assert not match(['xyznotaword']*13)
db=sqlite3.connect((R/'restart/corpus-audit-v1/audit.sqlite').as_uri()+'?mode=ro',uri=True);hits=[];counts=collections.Counter()
for ident,r in protected.items():
 if time.monotonic()-start>=110:raise TimeoutError('Supplemental110second bound')
 norm,held,families=db.execute('SELECT normalized,held,families FROM docs WHERE id=?',(ident,)).fetchone();assert hashlib.sha256(norm.encode()).hexdigest()==r['normalized_sha256'];counts[r['split']]+=1
 for i,detail in match(norm.split()).items():hits.append({'chapter':i+1,'audit_id':ident,'M0_role':r['split'],'historical_held':held,'legacy_family':r['family_id'],'families':families,**detail})
aliases=json.loads((D/'independent-verification.json').read_text())['metadata_alias_keyword_candidates']
for x in aliases:
 x['M0_split_role']=roles.get(x['audit_id'],{}).get('split','NOT_ADMITTED');x['M0_training_member']=x['M0_split_role']=='train';x['M0_protected_member']=x['M0_split_role'] in ['development','test']
 x['disposition']='LEXICAL_FALSE_POSITIVE_AUSTENITIC_STEEL' if x['audit_id']==140633 else 'AUSTEN_RELATED_METADATA_NOT_CURRENTLY_ADMITTED_OR_HISTORICALLY_HELD; exact work ancestry unresolved'
db.close();base=json.loads((D/'result.json').read_text());any_protected=bool(hits or base['protected_hit_propagates_to_chapters']);prop=list(range(1,62)) if any_protected else []
assert (not any_protected or len(prop)==61) and {x['family_id'] for x in rows}=={'austen:pride-and-prejudice:original-work-all-editions'}
result={'status':'M0_CURRENT_DEVELOPMENT_TEST_ROLES_SCREENED_NO_ADMISSION','M0_protected_counts':dict(counts),'protected_span_matches':hits,'metadata_alias_role_reconciliation':aliases,'all_matched_work_family_chapters_propagated':prop,'known_family_policy':'All61chapters and every edition/derivative of original Austen novel remain one family; known protected ancestor holds whole family.','scope_limit':'No unknown ancestry or semantic paraphrase clearance; new intake cross-source checks pending.','actual_source_sha256':'3f6bb9d6f78e0293b56acd4714dd68cb7d6d1d293402031ce9d5a216bcaf9d75','current_m0_registry_SHA256':h(M/'registry.json'),'M0_admitted_artifact_SHA256':h(M/'artifacts/admitted-documents.jsonl'),'elapsed_seconds':time.monotonic()-start,'synthetic_controls':['nonzero_candidate32word_match','full13word_match','unrelated_refused','known_protection_wholefamily_closure'],'new_admitted_documents':0,'new_admitted_tokens':0}
(D/'M0-role-supplement.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'counts':dict(counts),'matches':len(hits),'elapsed':time.monotonic()-start,'metadata_candidates':len(aliases)}))
