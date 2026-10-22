"""Actual native parser synthetic paths only; no retained source/archive."""
import hashlib,json
import frame_core as c
from checks import HEADER,page,frame
checks=[]
def b36(value):
 n=int(value,16);s=''
 while n:n,k=divmod(n,36);s='0123456789abcdefghijklmnopqrstuvwxyz'[k]+s
 return s or '0'
correct=b36(hashlib.sha1(b'A & B').hexdigest())
base=page().replace(b'<text xml:',('<text sha1="'+correct+'" xml:').encode())
def record(raw):return frame(HEADER+raw)[0].pages[0]
def held(name,raw,wanted):
 p=record(raw);assert wanted in p['holds'],(name,p['holds']);assert p['page_raw_XML_SHA256']==hashlib.sha256(raw.rstrip(b'\n')).hexdigest();checks.append(name);return p
for name,old,new in [('wrong_format',b'<format>text/x-wiki</format>',b'<format>application/json</format>'),('missing_format',b'<format>text/x-wiki</format>',b'')]:held(name,base.replace(old,new),'NON_WIKI_OR_UNSPECIFIED_FORMAT')
for name,closing,extra,key in [('unknown_page',b'</page>',b'<mystery><nested>Exact unknown raw content</nested></mystery>','UNEXPECTED_PAGE_CHILD_SCHEMA'),('unknown_revision',b'</revision>',b'<mystery>Exact unknown revision value</mystery>','UNEXPECTED_REVISION_CHILD_SCHEMA')]:
 p=held(name,base.replace(closing,extra+closing),key);desc=p['unknown_schema_children'] if name=='unknown_page' else p['revisions'][0]['unknown_schema_children'];x,y=desc[0]['decoded_byte_span'];assert (HEADER+base.replace(closing,extra+closing))[x:y]==extra;checks.append(name+'_exact_unknown_subtree_span_retained')
legacy=b'<model>wikitext</model><format>text/x-wiki</format>'+('<text sha1="'+correct+'" xml:space="preserve" bytes="5">A &amp; B</text>').encode()
main=b'<slot role="main">'+legacy+b'</slot>'
def slots(content):return base.replace(legacy,b'<slots>'+content+b'</slots>')
held('aux_wikitext_is_not_main',slots(main.replace(b'role="main"',b'role="aux"')),'UNSUPPORTED_OR_MISSING_SLOT_ROLE')
held('slot_missing_role',slots(main.replace(b' role="main"',b'')),'UNSUPPORTED_OR_MISSING_SLOT_ROLE')
held('mixed_roles',slots(main+main.replace(b'role="main"',b'role="aux"')),'MIXED_SLOT_ROLES')
held('multiple_main_slots',slots(main+main),'MULTIPLE_MAIN_SLOTS')
p=held('unknown_slots_child',slots(main+b'<mystery>unknown slots child</mystery>'),'UNEXPECTED_SLOTS_CHILD_SCHEMA');assert p['revisions'][0]['unknown_slots_children'][0]['name']=='mystery'
p=held('unknown_slot_child',slots(main.replace(b'</slot>',b'<mystery>unknown main child</mystery></slot>')),'UNEXPECTED_SLOT_CHILD_SCHEMA');assert p['revisions'][0]['content_slots_or_legacy'][0]['unknown_schema_children'][0]['name']=='mystery'
def sibling(raw,value):return raw.replace(b'</revision>',value+b'</revision>')
p=record(sibling(base,('<sha1>'+correct+'</sha1>').encode()));assert p['revisions'][0]['revision_SHA1_consistency']['status']=='MATCH' and p['revisions'][0]['content_slots_or_legacy'][0]['text']['native_base36_SHA1_matches'];checks.append('legacy_sibling_and_text_attribute_match_actual_decoded_UTF8')
p=held('valid_text_attribute_wrong_sibling_hash',sibling(base,b'<sha1>0</sha1>'),'REVISION_SIBLING_SHA1_MISMATCH');assert p['revisions'][0]['content_slots_or_legacy'][0]['text']['native_base36_SHA1_matches'] is True and p['revisions'][0]['revision_SHA1_consistency']['matches_decoded_text'] is False
for name,xml,status in [('missing',b'','MISSING'),('deleted',b'<sha1 deleted="deleted"/>','DELETED'),('empty',b'<sha1/>','EMPTY_OR_INVALID_BASE36'),('invalid',b'<sha1>*</sha1>','EMPTY_OR_INVALID_BASE36'),('overflow',b'<sha1>'+b'z'*31+b'</sha1>','EMPTY_OR_INVALID_BASE36')]:
 p=record(sibling(base,xml));result=p['revisions'][0]['revision_SHA1_consistency'];assert result['status']==status and result['matches_decoded_text'] is None;checks.append('sibling_'+name+'_explicit_not_compared')
p=record(sibling(slots(main),('<sha1>'+correct+'</sha1>').encode()));assert p['revisions'][0]['revision_SHA1_consistency']['comparison_basis']=='single_explicit_main_slot' and p['revisions'][0]['revision_SHA1_consistency']['status']=='MATCH';checks.append('single_explicit_main_slot_sibling_comparison')
p=record(sibling(slots(main+main.replace(b'role="main"',b'role="aux"')),('<sha1>'+correct+'</sha1>').encode()));assert p['revisions'][0]['revision_SHA1_consistency']['status']=='UNVERIFIED_UNSUPPORTED_OR_MISSING_CONTENT_SCHEMA';checks.append('no_invented_multi_or_aux_slot_combined_revision_hash')
try:frame(HEADER+page(1,'123')+page(2,'00123'))
except ValueError as e:assert 'duplicate_revision_ID_within_prefix_123' in str(e);checks.append('numeric_canonical_revision_ID_duplicate_refused')
else:raise AssertionError('numeric duplicate missed')
print(json.dumps({'status':'PASS_ACTUAL_SYNTHETIC_PARSER_SCHEMA_ID_HASH','count':len(checks),'checks':checks,'retained_source_bytes':0},indent=2))
