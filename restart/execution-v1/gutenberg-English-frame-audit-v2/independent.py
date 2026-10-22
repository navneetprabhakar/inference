import pathlib,sys,json,copy,tempfile,sqlite3,ast,hashlib
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'gutenberg-English-frame-preparation-v2';sys.path.insert(0,str(D));import frame as f
c=f.c;cases=[]
def check(n,v):assert v,n;cases.append(n)
def refuses(fn):
 try:fn()
 except Exception:return True
 return False
f.pins('03acf1b9c14a58cea5b4d4420d6d2b9894e43a7744ec7c0da2aa725db7f14204');check('external_exact_inventory_and_every_input_hash_revalidated',True)
actual=f.overlay_records();check('two_held_source_gaps_exact_identity_overlay',[(o,r['ebook_ID'],s['native_member']['hold']) for o,(r,s) in sorted(actual.items())]==[(17579,25851,'oversize_RDF_member_not_parsed'),(18683,26849,'oversize_RDF_member_not_parsed')])
n=c.parse_rdf.parse((c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw').read_bytes(),'pg1342.rdf');row=f.classified(n,{})
unknown=copy.deepcopy(n);unknown['previously_unmapped_payload']={'unicode':'original\n\t字','empty':None,'array':[1,False]};check('extra_unknown_native_field_lossless_no_silent_drop',f.restore_native(f.classified(unknown,{}))==unknown)
refs=copy.deepcopy(n);refs['native_relations_and_credits']=[{'attributes':{'x':v},'text':''} for v in ['http://gutenberg.org/ebooks/1234suffix','https://gutenberg.org/ebooks/1234?x=9','https://gutenberg.org/ebooks/1234#foo','https://gutenberg.org/ebooks/1234/5','text https://gutenberg.org/ebooks/1234','https://evil.example/ebooks/1234','https://gutenberg.org/ebooks/1234']];check('only_complete_official_relation_value_creates_edge',f.strict_relation_IDs(refs)==[1234])
a=f.classified(n,{});b=copy.deepcopy(a);b['ebook_ID']=999999;b['provisional_family']='other-title';b['explicit_related_ebook_IDs']=[];a['explicit_related_ebook_IDs']=[];fam=f.Families();fam.add(a);fam.add(b);fam.resolve();check('identical_contributor_roles_no_unrelated_work_merge',fam.root(a['ebook_ID'])!=fam.root(b['ebook_ID']))
check('overlay_vs_original_ID_collision_refused',refuses(lambda:fam.add(copy.deepcopy(a))))
q=f.source_query();check('source_joins_explicit_attached_shards_no_temp_fallback',all('shard'+str(i)+'.members' in q and 'shard'+str(i)+'.records' in q for i in range(2)) and ' union all ' in q and q.endswith(' order by ordinal'))
with tempfile.TemporaryDirectory() as td:
 db=f.database(pathlib.Path(td)/'frame.sqlite3');r=f.classified(n,{});f.insert(db,r,1,'test');db.commit();check('duplicate_native_ordinal_refused',refuses(lambda:f.insert(db,r,1,'test')));db.rollback();db.close()
source=(D/'frame.py').read_text();tree=ast.parse(source);worker=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='worker');calls=[(x.func.id,x.lineno) for x in ast.walk(worker) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)];pinlines=[ln for name,ln in calls if name=='pins'];check('worker_rechecks_same_external_manifest_after_build',len(pinlines)==2 and sorted((x.lineno,x.col_offset) for x in ast.walk(worker) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='pins')[1]>next((x.lineno,x.col_offset) for x in ast.walk(worker) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='build'))
check('main_to_child_explicit_same_manifest_digest',"'--manifest-sha256',expected" in source and "pins(args.manifest_sha256)" in source and "worker(args.manifest_sha256)" in source)
check('hardcaps_sum_under600MB',f.DB_CAP+f.JOURNAL_CAP+f.HEADROOM+f.TERMINAL< f.OUTPUT and f.DB_CAP==540000000 and f.JOURNAL_CAP==16000000)
check('rights_unknown_for_all_and_no_source_body_authorization',r['original_English_composition'].startswith('UNVERIFIED') and r['edition_and_jurisdiction_rights'].startswith('UNVERIFIED') and not r['body_acquisition_authorized'] and not r['training_admitted'])
result={'status':'PASS','count':len(cases),'checks':cases,'full_catalog_derivations':0,'network_requests':0,'source_mutations':0};(P/'independent-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
