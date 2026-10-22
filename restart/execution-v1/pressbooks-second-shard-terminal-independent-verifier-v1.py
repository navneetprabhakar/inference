import pathlib,json,hashlib,sqlite3,sys,os,signal,time,collections
B=pathlib.Path(__file__).resolve().parent;P=B/'pressbooks-second-shard-inventory-preparation-v1';D=B/'m2-intake/pressbooks-second-shard-inventory-v1';O=B/'pressbooks-second-shard-terminal-independent-verification-v1';start=time.monotonic()
def alarm(*a):raise TimeoutError('110second_verification_cap')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,110)
h=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());own=json.loads((D/'ownership.json').read_text());pr=json.loads((P/'profile.json').read_text());pins=json.loads((P/'code-pins.json').read_text())['SHA256'];assert all(h(p)==v for p,v in pins.items())
assert h(D/'result.json')==s['result_SHA256']=='e36cf4405e91ad423b973f88fb91f6fbb6d359ea832b421c13f5baf12c35ce72' and s['worker_exit_code']==0 and r['status']=='COMPLETE_SECOND_SHARD_METADATA_FRAME_NO_ADMISSION'
for k in ['worker_PID','supervisor_PID']:
 try:os.kill(own[k],0)
 except ProcessLookupError:pass
 else:raise AssertionError('owner_live')
for n,a in r['artifacts'].items():assert h(D/n)==a['SHA256'] and (D/n).stat().st_size==a['bytes']
sys.path.insert(0,str(P));import source_guard,inventory
assert source_guard.ident(pathlib.Path(pr['source']['path']).stat())==pr['source']['stat'];proof=json.loads(pathlib.Path(pr['integrity_receipt']).read_text());assert proof['SHA256']==r['counts']['compressed_SHA256']==pr['source']['SHA256'] and proof['bytes']==r['counts']['compressed_bytes']==174453169
assert r['counts']['gzip_CRC_EOF_members']>=1 and r['counts']['trailing_absent']
p=D/'frame.sqlite';before=p.stat();db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('pragma query_only=ON');db.execute('pragma temp_store=MEMORY');db.execute('pragma cache_size=-8192');assert db.execute('pragma integrity_check').fetchall()==[('ok',)]
loc=hashlib.sha256();offset=0;count=0;totals=[0]*5;flags=collections.Counter();licenses=collections.Counter();first=None
for row in db.execute('SELECT * FROM records ORDER BY ordinal'):
 ordinal,off,n,lf,sha,fl=row[:6];assert ordinal==count+1 and off==offset and n>0 and lf in [0,1] and type(sha) is bytes and len(sha)==32 and fl>=0 and fl<4096
 if ordinal<r['rows']:assert lf==1
 loc.update(json.dumps([ordinal,off,n,lf,sha.hex()],separators=(',',':')).encode()+b'\n');count+=1;offset+=n
 for name,bit in r['flag_bits'].items():flags[name]+=int(bool(fl&bit))
 assert row[17] is None or (type(row[17]) is bytes and len(row[17])==32)
 assert all(x is None or (type(x) is str and len(x.encode('utf8'))<=4096) for x in row[6:17])
 assert (row[18] is None and row[19] is None) or (row[18]>=row[19]>=0)
 if row[20] is not None:assert row[20]==inventory.family(row[12],row[11])
 licenses[row[10]]+=1
 totals[0]+=1;totals[1]+=n;totals[2]+=row[18] or 0;totals[3]+=row[19] or 0;totals[4]+=row[20] is not None
 if ordinal==1:first=row
assert count==r['rows']==r['committed_rows']==32938 and offset==r['counts']['decoded_bytes'] and totals==r['stored_row_line_text_totals'] and dict(flags)==r['flag_counts'] and loc.hexdigest()==r['ordered_line_locator_SHA256']
for known in pr['known_holds']:assert first[0]==known['source_ordinal']==1 and first[4].hex()==known['line_SHA256'] and first[6]==known['id'] and first[17].hex()==known['text_SHA256'] and first[5]&1024
for col,want in r['exact_duplicate_signal_groups_and_occurrences'].items():assert list(db.execute('SELECT count(*),coalesce(sum(n),0) FROM (SELECT count(*) n FROM records WHERE '+col+' IS NOT NULL GROUP BY '+col+' HAVING count(*)>1)').fetchone())==want
assert db.execute('SELECT count(DISTINCT derived_book_root) FROM records').fetchone()==(r['distinct_derived_book_roots_not_complete_books'],)
dup=db.execute('SELECT coalesce(sum(n-1),0),coalesce(sum((n-1)*b),0),coalesce(sum(b),0) FROM (SELECT count(*) n,min(text_UTF8_bytes) b FROM records WHERE text_SHA256 IS NOT NULL GROUP BY text_SHA256)').fetchone()
conflict=db.execute('SELECT count(*) FROM (SELECT id FROM records WHERE id IS NOT NULL GROUP BY id HAVING count(*)>1 AND count(DISTINCT text_SHA256)>1)').fetchone()[0]
unresolved=db.execute('SELECT count(*),sum(text_UTF8_bytes) FROM records WHERE flags & 64').fetchone();assert unresolved[0]==9724
db.close();assert p.stat()==before
ex=(D/'schema-holds.jsonl').read_bytes();ev=[json.loads(x) for x in ex.splitlines()];assert len(ev)==r['schema_exceptions']['events']==0 and len(ex)==r['schema_exceptions']['bytes'] and hashlib.sha256(ex).hexdigest()==r['schema_exceptions']['ordered_SHA256']
j=(D/'frame.sqlite-journal').read_bytes();assert len(j)<=8000000 and not j[:28].strip(b'\x00') and r['SQLite_journal_mode']=='PERSIST'
assert s['elapsed_seconds']<600 and s['peak_observed_RSS_bytes']<1000000000 and sum(x.stat().st_size for x in D.iterdir() if x.is_file())==s['all_output_bytes']<128000000
O.mkdir(exist_ok=False);v={'status':'PASS_SECOND_SHARD_STORED_METADATA_NOT_USABLE_COUNT','input_pins_verified':len(pins),'rows':count,'decoded_line_bytes':offset,'text_UTF8_bytes':totals[2],'text_chars':totals[3],'all32938_ordinals_contiguous_offsets_lengths_linehash_shapes_and_locator_digest_reconciled':True,'local_knownhold_count':r['flag_counts']['KNOWN_REVIEW_HOLD'],'cross_source_firsthold_metadata_preserved':bool(pr['cross_source_known_holds']),'SQLite_integrity':'ok','SQLite_SHA256':h(p),'source_original_stat_and_parent_integrity_receipt_unchanged':True,'gzip_CRC_EOF_source_size_hash_receipts_consistent':True,'allflags_schemaexceptions_duplicate_aggregates_reconciled':True,'distinct_derived_roots_not_completebooks':r['distinct_derived_book_roots_not_complete_books'],'resolved_rows':totals[4],'family_unresolved_rows_and_text_bytes':list(unresolved),'text_duplicate_excess_occurrences':dup[0],'repeated_text_hash_bytes':dup[1],'distinct_text_hash_bytes_NOT_USABLE':dup[2],'duplicateIDs_with_conflicting_text_hashes':conflict,'raw_license_variants':dict(licenses),'PERSIST_zeroheader_journal_bytes':len(j),'owned_PIDs_absent':True,'new_admitted_documents':0,'new_admitted_tokens':0,'source_body_reads':0,'limitations':'Stored rawline hashes and text hashes reconcile receipt/provenance and all row coverage; no raw gzip line/text recomputation performed. Existing parent second-shard full compressed hash and producer CRC/EOF retained. Distinct text hashes/roots/license strings are diagnostics, not quality/language/rights/leakage or complete-book admission.','elapsed_seconds':time.monotonic()-start,'output_pins':{x.name:h(x) for x in D.iterdir() if x.is_file()}}
(O/'verification.json').write_text(json.dumps(v,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'verification.json':h(O/'verification.json'),'verifier_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'verification.json'),h(O/'manifest.json'))
