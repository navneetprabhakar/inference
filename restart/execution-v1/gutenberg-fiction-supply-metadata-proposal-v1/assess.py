"""Catalog metadata only. No book body reads/network/tokenizer/rights admission."""
from pathlib import Path
import sqlite3,json,zlib,hashlib,re,time,collections,shutil
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';START=time.clock_gettime(time.CLOCK_MONOTONIC)
SHA=lambda b:hashlib.sha256(b).hexdigest()
def check():
 if time.clock_gettime(time.CLOCK_MONOTONIC)-START>90:raise TimeoutError('metadata90sec')
def write(name,obj):
 raw=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
 if len(raw)>64000000:raise ValueError('metadata64MB')
 (HERE/name).write_bytes(raw)
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
frame=ROOT/'gutenberg-complete-English-metadata-frame-v2/frame.sqlite3';before=ident(frame.stat());c=sqlite3.connect(frame.as_uri()+'?mode=ro&immutable=1',uri=True);c.execute('pragma query_only=ON');c.execute('pragma cache_size=-4096')
first=json.loads((ROOT/'gutenberg-first-prose-cohort-proposal-v1/proposal.json').read_text());post=json.loads((ROOT/'gutenberg-post1900-body-discovery-proposal-v1/proposal.json').read_text());known=set(x['ebook_ID'] for x in first['known_development_and_diagnostic_identity_bindings'])|{x['ebook_ID'] for x in first['records']}|{x['ebook_ID'] for x in post['selected_records']}
known_families={r[0] for eid in known for r in c.execute('SELECT component_ID FROM families WHERE ebook_ID=?',(eid,))};family={eid:f for eid,f in c.execute('SELECT ebook_ID,component_ID FROM families')}
cache={}
for directory in ['gutenberg-first-prose-https-targets-v1','gutenberg-post1900-cohort-raw-v3']:
 p=ROOT/directory;receipt=json.loads((p/'worker-result.json').read_text())
 for r in receipt['records']:
  if r['status']!='RAW_DISCOVERY_COMPLETE_NOT_ADMITTED':continue
  f=p/f"pg{r['ebook_ID']}.raw"
  if f.is_file() and not f.is_symlink() and f.stat().st_size==r['bytes']:cache[r['ebook_ID']]={'path':str(f),'bytes':r['bytes'],'SHA256_inherited':r['sha256'],'stat':ident(f.stat()),'receipt':str(p/'worker-result.json')}
counts=collections.Counter();roles_count=collections.Counter();frames=[];all_role_eligible=[]
creator='{http://purl.org/dc/terms/}creator';trl='{http://id.loc.gov/vocabulary/relators/}trl'
for ordinal,eid,status,genres,rawhash,packedhash,blob in c.execute("SELECT ordinal,ebook_ID,discovery_status,genres,raw_hash,packed_hash,payload FROM frame WHERE discovery_status='ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY' ORDER BY ordinal"):
 check();counts['metadata_eligible_examined']+=1;d=zlib.decompressobj();raw=d.decompress(blob,2000001)
 if len(raw)>2000000 or not d.eof or d.unused_data or d.unconsumed_tail or SHA(raw)!=rawhash or SHA(blob)!=packedhash:raise ValueError('exact_metadata_payload_binding')
 o=json.loads(raw);gs=set(o['observed_genre_strata']);subjects=[v for s in o['subjects'] if any(x.endswith('/LCSH') for x in s['memberOf']) for v in s['values']]
 if 'narrative' not in gs or gs&{'drama','poetry'} or not any(re.search(r'\b(fiction|stories|tales)\b',s,re.I) for s in subjects):counts['not_narrative_fiction_subject_priority']+=1;continue
 counts['narrative_fiction_subject_metadata']+=1;rs=o['contributors_and_all_roles'];creators=[r for r in rs if r['role_qualified_name']==creator]
 if not creators or o['unresolved_contributor_fields']:counts['missing_creator_or_unresolved_roles']+=1;continue
 def old(r):
  dd=r['deathdates'];return len(dd)==1 and re.fullmatch('[0-9]{4}',dd[0]) and int(dd[0])<=1965 and not r['holds'] and r['stable_agent_ID'] is not None
 if not all(old(r) for r in creators):counts['creator_death_not_exact_le1965']+=1;continue
 counts['fiction_all_creators_exact_death_le1965']+=1
 for r in rs:roles_count[r['role_qualified_name']]+=1
 if not all(old(r) for r in rs):counts['other_credited_roles_date_or_reference_review']+=1;continue
 counts['fiction_all_credited_roles_exact_death_le1965']+=1
 fm=[f for f in o['all_formats'] if f.get('MIME_values')==['text/plain; charset=utf-8'] and f.get('resolved_URL')==f'https://www.gutenberg.org/ebooks/{eid}.txt.utf-8' and type(f.get('extent_bytes')) is int and f['extent_bytes']>0 and not f.get('holds')]
 if len(fm)!=1:counts['missing_unique_native_UTF8_ebooks_format']+=1;continue
 counts['fiction_dated_roles_exact_UTF8_format']+=1
 if family[eid] in known_families:counts['known_frozen_dev_family_excluded']+=1;continue
 counts['not_known_family']+=1
 if fm[0]['extent_bytes']>2400000:counts['extent_over_first_acquisition_cap']+=1;continue
 codes=sorted({v for s in o['subjects'] if any(x.endswith('/LCC') for x in s['memberOf']) for v in s['values']})
 rec={'ebook_ID':eid,'ordinal':ordinal,'frame_raw_SHA256':rawhash,'frame_packed_SHA256':packedhash,'source_binding':o['source_binding'],'family_component_ID':family[eid],'titles':o['titles'],'subjects_LCSH':subjects,'LCC':codes,'genres':sorted(gs),'all_credited_roles':[{k:r[k] for k in ['role_qualified_name','stable_agent_ID','names','birthdates','deathdates','holds']} for r in rs],'UTF8_format_metadata':fm[0],'catalog_extent_bytes_not_body_verified':fm[0]['extent_bytes'],'recorded_translator_present':any(r['role_qualified_name']==trl for r in rs),'only_creator_roles':all(r['role_qualified_name']==creator for r in rs),'creator_IDs':[r['stable_agent_ID'] for r in creators],'era':'through1900' if all(int(r['deathdates'][0])<=1900 for r in creators) else '1901through1965','original_English_proof':'UNVERIFIED; en/no named translator/PR_PS are metadata leads only','local_cached_complete_body':cache.get(eid),'priority':SHA(('gutenberg-fiction-development-batch-v1\n'+str(eid)).encode())}
 all_role_eligible.append(rec)
 # First low-translation-risk discovery lane, not a universal narrative/rights criterion.
 if rec['recorded_translator_present']:counts['first_lane_named_translation_deferred']+=1;continue
 if not any(code in {'PR','PS'} for code in codes):counts['first_lane_non_PR_PS_deferred_not_excluded_from_capacity']+=1;continue
 frames.append(rec)
# Freeze deterministic300 across two creator-era strata, max2works percreator, unique provisionalfamily.
selected=[];seenfamilies=set();author_counts=collections.Counter()
for era,quota in [('through1900',150),('1901through1965',150)]:
 chosen=0
 for r in sorted((x for x in frames if x['era']==era),key=lambda r:(r['priority'],r['ebook_ID'])):
  if r['family_component_ID'] in seenfamilies or any(author_counts[a]>=2 for a in r['creator_IDs']):continue
  selected.append(r);seenfamilies.add(r['family_component_ID']);author_counts.update(r['creator_IDs']);chosen+=1
  if chosen>=quota:break
 assert chosen==quota,(era,chosen)
assert len(selected)==300
# Ledger metadata-only transaction: no exclusive writer lock/reservation.
ledger=ROOT/'charges/ledger.sqlite';lc=sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True);lc.execute('pragma query_only=ON');lc.execute('BEGIN');charges=[json.loads(r[0]) for r in lc.execute('SELECT charge FROM attempts')];totals={k:sum(x.get(k,0) for x in charges) for k in ['body_bytes','output_bytes','requests']};pending=lc.execute("SELECT count(*) FROM attempts WHERE state='pending'").fetchone()[0];lc.execute('COMMIT');lc.close();c.close();assert before==ident(frame.stat())
write('ordered-frame.json',sorted(frames,key=lambda r:(r['priority'],r['ebook_ID'])))
write('all-dated-role-fiction-candidates.json',all_role_eligible)
write('selected300.json',selected)
write('known-exclusions.json',{'ebook_IDs':sorted(known),'complete_provisional_family_components_excluded':sorted(known_families),'scope':'Known prior PG catalog/body development identities and exact family components; not authorwide exclusion, not final split assignment.'})
write('cached-body-metadata.json',{'verified_acquisition_receipt_complete_rawbody_metadata':cache,'body_bytes_read':0,'fresh_body_hashes':0,'candidate_available_after_knownfamily_exclusion':sum(r['local_cached_complete_body'] is not None for r in all_role_eligible),'note':'Rawbody receipt/stat only. Excluded known development bodies remain useful for extractor regression, not new unbiased corpus sample.'})
write('assessment.json',{'status':'COMPLETE_METADATA_ONLY_FICTION_SUPPLY_PROPOSAL_NO_RIGHTS_OR_BODY_ADMISSION','frame_path':str(frame),'frame_stat_before_after':before,'inherited_frame_SHA256':'621f093245d28c25ba14ac3b0f82e52ef2023479b8f03b1ab246622d3b076ae2','counts':dict(counts),'roles_among_creator_eligible_fiction':dict(roles_count),'all_role_candidate_count':len(all_role_eligible),'all_role_catalog_extent_sum':sum(r['catalog_extent_bytes_not_body_verified'] for r in all_role_eligible),'first_priority_lane_count':len(frames),'first_lane_era_counts':dict(collections.Counter(r['era'] for r in frames)),'first_lane_catalog_extent_sum':sum(r['catalog_extent_bytes_not_body_verified'] for r in frames),'selected':len(selected),'selected_era_counts':dict(collections.Counter(r['era'] for r in selected)),'selected_catalog_extent_sum':sum(r['catalog_extent_bytes_not_body_verified'] for r in selected),'selected_distinct_creators':len(author_counts),'max_selected_per_creator':max(author_counts.values()),'ledger_metadata_snapshot':{'reserved':totals,'remaining_body_80GB':80000000000-totals['body_bytes'],'remaining_output_80GB':80000000000-totals['output_bytes'],'pending_allocations':pending,'no_writer_lock_or_mutation':True},'disk':{'free_bytes':shutil.disk_usage(ROOT).free},'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-START,'book_bodies_read':0,'network_requests':0,'new_usable_documents':0,'new_usable_tokens':0,'limits':{'seconds':90,'output_per_file_bytes':64000000,'native_metadata_record_bytes':2000000}})
