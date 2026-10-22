"""Synthetic three-WB adaptation and existing tokenizer preflight; no candidate encode."""
import json,pathlib,tempfile,importlib.util
import audit,overlap_core
def run():
 cases=[];c={'file':'derivative','captured_raw_source_ancestor':{'path':'parent','SHA256':'sourcehash'},'source_ordinal':12,'page_id':30,'revision_id':40,'family_ID':'family'}
 role={'page_id':30,'revision_id':40,'text_sha256':'sourcehash','family':'family'}
 assert audit.own_ancestor(c,'derivative#text',{});assert audit.own_ancestor(c,'parent#text',{});cases.append('exact_registered_parent_and_derivative_aliases')
 metadata={'source_ordinal':12,'current_global_finalizer_role':role}
 assert audit.own_ancestor(c,'renderer#12',metadata);cases.append('bound_renderer_page_revision_hash_family_alias')
 for field,value in [('source_ordinal',13)]:
  assert not audit.own_ancestor(c,'renderer#12',{**metadata,field:value})
 for field in ['page_id','revision_id','text_sha256','family']:
  assert not audit.own_ancestor(c,'renderer#12',{**metadata,'current_global_finalizer_role':{**role,field:'wrong'}})
 cases.append('wrong_ordinal_page_revision_hash_family_not_alias')
 assert overlap_core.disposition(True,audit.own_ancestor(c,'parent#text',{}))=='PROTECTED_FAMILY_HOLD';cases.append('protected_role_overrides_proven_own_ancestor')
 original=audit.BASE
 with tempfile.TemporaryDirectory() as t:
  audit.BASE=pathlib.Path(t);p=audit.BASE/'gutenberg-four-longWB-delta-preparation-v1';p.mkdir();norm='synthetic source words'
  r={'source_ordinal':12,'source_outer_page_id':30,'source_outer_revision_id':40,'source_family':'family','normalized_SHA256':overlap_core.sha(norm.encode()),'normalized_words':3};(p/'measurement.json').write_text(json.dumps({'records':[r]}));meta={'source_ordinal':12,'page_id':30,'revision_id':40,'family_id':'family'}
  assert audit.approved_large_WB(norm,meta)
  assert not audit.approved_large_WB(norm+' extra',meta)
  assert not audit.approved_large_WB(norm,{**meta,'page_id':31});cases.append('allowlisted_large_body_exact_identity_hash_wordcount_only')
 audit.BASE=original
 rulepath=audit.BASE/'wikibooks-language-token-preparation-v1/rules.py';spec=importlib.util.spec_from_file_location('existing_pinned_M1',rulepath);rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
 profile=json.loads((rulepath.parent/'profile.json').read_text());tok=rules.load_tokenizer(profile)
 sample='Synthetic English definition.\n\nSecond paragraph with unchanged whitespace.'
 before=sample.encode();n=audit.count_text(sample,tok);assert n>0 and before==sample.encode() and audit.count_text(sample,tok)==n;cases.append('actual_M1_import_load_and_production_synthetic_count_no_source_encoding')
 return {'status':'PASS','count':len(cases),'cases':cases,'retained_candidate_tokenization_or_corpus_scan':False}
if __name__=='__main__':print(json.dumps(run(),indent=2))
