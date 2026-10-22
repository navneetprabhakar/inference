"""Synthetic literal edit/inverse tests only; no actual derivative produced."""
import copy,hashlib,json
import literal_core as c

def run():
 checks=[]
 def yes(name,fn,fail=False):
  try:fn()
  except (ValueError,KeyError,TypeError):
   if not fail:raise
   checks.append({'check':name,'PASS':True});return
  if fail:raise AssertionError('accepted '+name)
  checks.append({'check':name,'PASS':True})
 raw=b'PREFIX\n[[Target|label]] "quote" <ref>x</ref>\n{{As of|2011}} census paragraph\nEND'
 specs=[(0,7,b'','omit_metadata'),(7,23,b'label','displayed_link'),(32,44,b'[1]','citation_marker'),(45,78,b'','hold_complete_template_unit')]
 # Derive offsets from literal fixture identities to avoid source assumptions.
 specs=[]
 for old,new,kind in [(b'PREFIX\n',b'','omit_metadata'),(b'[[Target|label]]',b'label','displayed_link'),(b'<ref>x</ref>',b'[1]','citation_marker'),(b'{{As of|2011}} census paragraph\n',b'','hold_complete_template_unit'),(b'END',b'','omit_end')]:
  a=raw.index(old);specs.append((a,a+len(old),new,kind))
 ops=[{'start_byte':a,'end_exclusive_byte':b,'original_hex':raw[a:b].hex(),'original_SHA256':c.sha(raw[a:b]),'replacement_hex':new.hex(),'operation':kind} for a,b,new,kind in specs]
 recipe={'source_text_SHA256':c.sha(raw),'source_text_bytes':len(raw),'operations':ops,'derivative_content_bytes_arithmetic_only':len(raw)+sum(len(n)-(b-a) for a,b,n,k in specs)}
 def good():
  derived,inverse=c.apply(raw,recipe);assert derived==b'label "quote" [1]\n' and c.restore(derived,inverse)==raw
 yes('synthetic_link_quote_citation_and_whole_inline_template_hold_inverse',good)
 yes('wrong_source_hash',lambda:c.apply(raw+b'x',recipe),True)
 for field,value in [('original_hex','00'),('original_SHA256','0'*64),('start_byte',-1),('end_exclusive_byte',999999)]:
  r=copy.deepcopy(recipe);r['operations'][1][field]=value;yes('tamper_'+field,lambda r=r:c.apply(raw,r),True)
 r=copy.deepcopy(recipe);r['operations'].reverse();yes('out_of_order',lambda:c.apply(raw,r),True)
 r=copy.deepcopy(recipe);r['derivative_content_bytes_arithmetic_only']+=1;yes('size_mismatch',lambda:c.apply(raw,r),True)
 derived,inverse=c.apply(raw,recipe);yes('inverse_tamper_replacement',lambda:c.restore(derived.replace(b'label',b'wrong'),inverse),True)
 # Unit boundaries around a wholly omitted template paragraph collapse exactly.
 a=raw.index(b'{{As of');b=raw.index(b'END');yes('whole_template_unit_zero_preview_span',lambda:None if c.mapped_boundary(a,recipe)==c.mapped_boundary(b,recipe) else (_ for _ in ()).throw(AssertionError()))
 yes('boundary_inside_edit_rejected',lambda:c.mapped_boundary(1,recipe),True)
 source=b'{{As of|2011}} India census remains awkward.'
 old=b'{{As of|2011}}';new=b'As of 2011';op={'start_byte':0,'end_exclusive_byte':len(old),'original_hex':old.hex(),'original_SHA256':c.sha(old),'replacement_hex':new.hex(),'operation':'parent_manually_adjudicated_exact_literal_semantic_mapping'}
 r={'source_text_SHA256':c.sha(source),'source_text_bytes':len(source),'operations':[op],'derivative_content_bytes_arithmetic_only':len(source)-len(old)+len(new)}
 def semantic_mapping():
  out,inverse=c.apply(source,r);assert out==b'As of 2011 India census remains awkward.' and c.restore(out,inverse)==source
 yes('synthetic_explicit_manual_As_of_mapping_no_grammar_rewrite_inverse',semantic_mapping)
 return {'status':'PASS_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'actual_source_derivatives_materialized':0,'network_requests':0}
if __name__=='__main__':print(json.dumps(run(),indent=2))
