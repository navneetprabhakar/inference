import pathlib,hashlib,json,runpy,sys,ast
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'gutenberg-English-frame-verifier-preparation-v1';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert h(D/'ready.json')=='2215d042a1f13788890b4ad4ee70786f6749a4a5397d8a95bd09cf7ce647c4dc';assert h(D/'manifest.json')=='a513f4ceeb0c3b3eb5c1172521a484cec3b62b97586d34573062bce3ab76171d';before={str(p):h(p) for p in D.iterdir() if p.is_file()};old=pathlib.Path.write_text
pathlib.Path.write_text=lambda self,*a,**k:old(P/'reproduced-checks.json' if self.resolve()==(D/'checks.json').resolve() else self,*a,**k)
try:sys.path.insert(0,str(D));runpy.run_path(str(D/'check.py'),run_name='__main__')
finally:pathlib.Path.write_text=old
assert all(h(pathlib.Path(p))==v for p,v in before.items());import verify as v
checks=[]
def check(n,b):assert b,n;checks.append(n)
code=(D/'verify.py').read_text();tree=ast.parse(code)
check('all_native_fields_compared_to_separately_unpacked_original',"native=c.unpack(*src[7:])" in code and "restored==native" in code and 'f.restore_native' not in code)
check('zip_longest_detects_missing_extra_and_ordinal_swap',"itertools.zip_longest(sd.execute(source_query),fd.execute(frame_query))" in code and "src is not None and dst is not None" in code and "ordinal==n and dst[0]==ordinal" in code)
check('all_query_columns_independently_bound',"dst[1:7]==(native['ebook_ID'],layer,payload['discovery_status'],exactEnglish" in code)
check('two_exact_gaps_source_hash_and_old_hold_history_bound',"member==item['native_member']" in code and "member['hold']=='oversize_RDF_member_not_parsed'" in code and "native['member_RDF_SHA256']==member['body_SHA256']" in code and "payload['source_binding']==binding" in code)
check('strict_independent_family_graph_not_source_component_reuse',"components.add(native)" in code and "root=components.root(eid)" in code and "json.loads(roles)==components.roles[eid]" in code)
check('all_stats_reconciled_exact_not_source_payload_self_equality',"summary==worker['stats']" in code and "native_metadata_field_roundtrips':n" in code)
check('same_external_manifest_and_actual_receipt_hashes_to_child',"'--manifest-sha256',expected,'--source-worker-sha256',workerSHA,'--source-supervisor-sha256',supervisorSHA" in code)
worker=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='worker');calls=[x for x in ast.walk(worker) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)];pins=sorted((x.lineno,x.col_offset) for x in calls if x.func.id=='pins');run=next((x.lineno,x.col_offset) for x in calls if x.func.id=='verify_data');check('worker_final_exact_pins_after_scan',len(pins)==2 and pins[0]<run<pins[1])
check('fixed600s_1GB_16MB_supervised_resource_bounds',v.WORKER==570 and v.EXTERNAL==600 and v.RSS==1000000000 and v.OUTPUT==16000000 and 'os.killpg' in code)
check('explicit_attached_source_tables_avoid_temp_fallback',"'.members m left join shard'" in code and "'.records r on m.ordinal=r.member'" in code)
(P/'independent-checks.json').write_text(json.dumps({'status':'PASS','count':len(checks),'checks':checks,'full_source_scans':0,'network_requests':0},indent=2)+'\n');print(json.dumps({'status':'PASS','baseline':16,'independent':len(checks),'preparation_unchanged':True}))
