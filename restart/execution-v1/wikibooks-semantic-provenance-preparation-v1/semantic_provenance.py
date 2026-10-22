"""Hash-bound semantic WB provenance before alias dedup; no source discovery or matcher."""
import hashlib,json
WB='CURRENT_WIKIBOOKS_FINALIZED_RENDERED'
GENERIC='RETAINED_LITERAL_BODY_OR_NATIVE_CONTEXT'
def sha_obj(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def annotate(entries,canonical,frozen_file_pins):
 """Canonical stores are explicit pinned recipe inputs; aliases match all semantics."""
 known={};by_path={e['path']:e for e in entries}
 for c in canonical:
  path=c['path'];e=by_path.get(path)
  if e is None or frozen_file_pins.get(path)!=c['SHA256'] or e['adapter']!='sqlite_json_data' or e.get('table')!='rendered' or not e['required_current_candidate_body_coverage']:raise ValueError('canonical_WB_store_not_exact_frozen_required_rendered')
  key=(c['SHA256'],e['adapter'],e['table'],e['required_current_candidate_body_coverage'],e['coverage_role'])
  known.setdefault(key,[]).append(path)
 result=[]
 for e in entries:
  digest=frozen_file_pins[e['path']]
  key=(digest,e['adapter'],e.get('table'),e['required_current_candidate_body_coverage'],e['coverage_role']);paths=known.get(key,[])
  result.append({**e,'physical_source_SHA256':digest,'semantic_coverage_role':WB if paths else GENERIC,'WB_canonical_paths':sorted(paths)})
 return result
def alias_signature(entry):
 if entry['semantic_coverage_role'] not in [WB,GENERIC]:raise ValueError('unknown_semantic_role')
 return (entry['physical_source_SHA256'],entry['adapter'],entry.get('table'),entry['required_current_candidate_body_coverage'],entry['coverage_role'],entry['semantic_coverage_role'])
class WBRoleProof:
 def __init__(self,entry,expected_ordinals):
  if entry['semantic_coverage_role']!=WB:raise ValueError('non_WB_owner')
  values=list(expected_ordinals)
  if not values or len(set(values))!=len(values) or any(type(i)is not int or i<=0 for i in values):raise ValueError('expected_ordinal_inventory')
  self.entry=entry;self.expected=set(values);self.rows={};self.compared=set()
 def observe(self,metadata,text,finalizer):
  """Call for each owner row BEFORE comparison, regardless physical pathname."""
  ordinal=metadata.get('source_ordinal')
  if type(ordinal)is not int or ordinal not in self.expected or ordinal in self.rows or not isinstance(text,str):raise ValueError('owner_row_missing_duplicate_or_unexpected')
  row=finalizer.execute('select p.page_id,p.revision_id,p.family,p.text_sha256,p.holds,p.active,f.holds from pages p join final_pages f on p.source_ordinal=f.source_ordinal where p.source_ordinal=?',(ordinal,)).fetchone()
  if row is None:raise ValueError('finalizer_role_missing')
  page,revision,family,digest,prior,active,final=row
  if metadata.get('page_id')!=page or metadata.get('revision_id')!=revision or metadata.get('family')!=family or ('family_id' in metadata and metadata['family_id']!=family) or hashlib.sha256(text.encode()).hexdigest()!=digest:raise ValueError('owner_page_revision_family_text_SHA_mismatch')
  if 'extracted_text_sha256' in metadata and metadata['extracted_text_sha256']!=digest:raise ValueError('native_metadata_extracted_text_SHA_mismatch')
  prior=json.loads(prior);final=json.loads(final)
  if active not in [0,1] or not isinstance(prior,list) or not isinstance(final,list):raise ValueError('finalizer_role_schema')
  role={'source_ordinal':ordinal,'page_id':page,'revision_id':revision,'family':family,'text_sha256':digest,'prior_holds':prior,'active':active,'global_final_holds':final}
  self.rows[ordinal]=role
  return {**metadata,'current_global_finalizer_role':role}
 def note_compared(self,ordinal):
  """Only after full frozen matching policy succeeded without a required-body gap."""
  if ordinal not in self.rows or ordinal in self.compared:raise ValueError('comparison_before_validation_or_duplicate')
  self.compared.add(ordinal)
 def finish(self):
  if set(self.rows)!=self.expected:raise ValueError('owner_role_coverage_gap')
  ordered=[self.rows[i] for i in sorted(self.rows)]
  identities=[[r[k] for k in ['source_ordinal','page_id','revision_id','family','text_sha256']] for r in ordered]
  return {'owner_path':self.entry['path'],'source_signature':list(alias_signature(self.entry)),'complete_role_coverage':True,'complete_body_comparison':self.compared==self.expected,'validated_rows':len(ordered),'expected_ordinal_set_SHA256':sha_obj(sorted(self.expected)),'identity_set_SHA256':sha_obj(identities),'final_role_binding_SHA256':sha_obj(ordered),'all_prior_finalizer_holds_preserved':True}
def inherit_alias(alias,owner,proof):
 """No counter inheritance without full physical+semantic+validated owner proof."""
 sig=alias_signature(alias)
 if alias['semantic_coverage_role']!=WB:raise ValueError('non_WB_role_proof_inheritance')
 if sig!=alias_signature(owner) or list(sig)!=proof.get('source_signature') or proof.get('owner_path')!=owner['path'] or proof.get('complete_role_coverage')is not True or proof.get('complete_body_comparison')is not True or not proof.get('all_prior_finalizer_holds_preserved') or not isinstance(proof.get('validated_rows'),int) or proof['validated_rows']<=0:raise ValueError('alias_owner_unproven_or_semantically_different')
 for k in ['expected_ordinal_set_SHA256','identity_set_SHA256','final_role_binding_SHA256']:
  v=proof.get(k)
  if not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v):raise ValueError('alias_owner_proof_digest')
 return {'path':alias['path'],'exact_physical_alias_of':owner['path'],'semantic_coverage_role':alias['semantic_coverage_role'],'validated_owner_proof_SHA256':sha_obj(proof),'validated_rows_inherited':proof['validated_rows'],'role_and_body_coverage_inherited_from_complete_owner':True,'not_additional_distinct_data':True}
