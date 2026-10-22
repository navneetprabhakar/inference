"""Finite synthetic controls only. No retained source files are opened."""
import hashlib,json
import semantic as s

NS='http://www.mediawiki.org/xml/export-0.11/'
HEADER=f'<mediawiki xmlns="{NS}"><siteinfo><base>https://en.wikipedia.org/wiki/Main_Page</base><namespaces><namespace key="0"/><namespace key="4">Project</namespace></namespaces></siteinfo>'.encode()
checks=[]
def b36(b):
    n=int(hashlib.sha1(b).hexdigest(),16);out=''
    while n:n,x=divmod(n,36);out='0123456789abcdefghijklmnopqrstuvwxyz'[x]+out
    return out or '0'
def rev(text=b'A &amp; B',rid=b'11',extra=b'',attrs=b''):
    decoded=b'A & B' if text==b'A &amp; B' else text
    return b'<revision'+attrs+b'><id>'+rid+b'</id><parentid>10</parentid><contributor><username>Person</username><id>999</id></contributor><model>wikitext</model><format>text/x-wiki</format><text xml:space="preserve" bytes="'+str(len(decoded)).encode()+b'" sha1="'+b36(decoded).encode()+b'">'+text+b'</text><sha1>'+b36(decoded).encode()+b'</sha1>'+extra+b'</revision>'
def page(r=None,pid=b'1',title=b'Example',extra=b''):
    return b'<page><title>'+title+b'</title><ns>0</ns><id>'+pid+b'</id>'+extra+(rev() if r is None else r)+b'</page>'
def parse(raw,step=65536,limits=None,close=True,collect=True):
    pp=[];rr=[]
    m=s.Metadata(pp.append if collect else lambda x:None,rr.append if collect else lambda x:None,limits=limits)
    data=HEADER+raw+(b'</mediawiki>' if close else b'')
    for i in range(0,len(data),step):m.feed(data[i:i+step])
    receipt=m.finish() if close else m.finish_prefix()
    return pp,rr,receipt,m
def ok(name,fn):fn();checks.append(name)
def held(name,raw,flag):
    pp,rr,_,_=parse(raw);assert flag in pp[0]['holds'],(name,pp[0]);checks.append(name);return pp,rr
def refuses(name,raw,error,**kw):
    try:parse(raw,**kw)
    except Exception as e:assert error in str(e),(name,e);checks.append(name)
    else:raise AssertionError(name+' accepted')

baseline=page()
for size in [1,2,7,31,65536]:
    pp,rr,r,m=parse(baseline,step=size)
    assert pp[0]['raw_XML']['SHA256']==hashlib.sha256(baseline).hexdigest()
    assert pp[0]['page_ID']==1 and rr[0]['revision_ID']==11 and rr[0]['page_ID']==1
    assert rr[0]['contributor']['id']['value']=='999'
    assert rr[0]['sibling_SHA1']['status']=='MATCH' and rr[0]['contents'][0]['status']['attribute_SHA1_status']=='MATCH'
    a,b=rr[0]['span'];assert (HEADER+baseline)[a:b]==rev()
    assert pp[0]['holds']==[],pp[0]['holds'];checks.append('raw_spans_directIDs_hash_chunk_'+str(size))

for name,rid in [('leadingzeros',b'00011'),('signedint64max',str(2**63-1).encode())]:
    _,rr,_,_=parse(page(rev(rid=rid)));assert rr[0]['revision_ID']==int(rid);checks.append(name)
for name,rid in [('zero',b'0'),('negative',b'-1'),('overflow',str(2**63).encode()),('missing',b''),('unicode',b'&#x661;')]:
    refuses('revision_'+name,page(rev(rid=rid)),'direct_identity')
refuses('duplicate_direct_page_id',page(extra=b'<id>2</id>'),'duplicate_direct_identity')
refuses('duplicate_direct_revision_id',page(rev(extra=b'<id>12</id>')),'duplicate_direct_identity')
pp,rr,_,m=parse(page(rev()+rev(rid=b'0011'))+page(rev(),pid=b'2'))
assert [x['revision_ID'] for x in rr]==[11,11,11] and [x['revision_ordinal'] for x in rr]==[1,2,1]
assert pp[0]['main_text'] is None and 'MULTIPLE_REVISIONS_NO_CANONICAL_SELECTION' in pp[0]['holds']
assert not hasattr(m,'ids') and not hasattr(m,'pages_list');checks.append('all_same_and_cross_page_revision_occurrences_retained')
refuses('revision_perpage_cap',page(rev()+rev()),'per_page_revision_limit',limits={'revisions_per_page':1})
held('no_revision',page(b''),'NO_REVISION')
held('container_character_data',page(rev().replace(b'<revision>',b'<revision>unmodeled prose')),'NONWHITESPACE_CONTAINER_CHARACTER_DATA')
held('nonwiki_format',page(rev().replace(b'text/x-wiki',b'application/json')),'NON_WIKI_OR_MISSING_FORMAT')
held('missing_format',page(rev().replace(b'<format>text/x-wiki</format>',b'')),'NON_WIKI_OR_MISSING_FORMAT')
held('nonwiki_model',page(rev().replace(b'wikitext',b'json')),'NON_WIKITEXT_OR_MISSING_MODEL')
held('deleted_text',page(rev().replace(b'<text ',b'<text deleted="deleted" ')),'DELETED_TEXT')
held('wrong_text_bytes',page(rev().replace(b'bytes="5"',b'bytes="6"')),'TEXT_BYTE_MISMATCH')
held('wrong_attribute_hash',page(rev().replace(b'sha1="'+b36(b'A & B').encode()+b'"',b'sha1="0"')),'TEXT_ATTRIBUTE_SHA1_MISMATCH_OR_INVALID')
held('wrong_sibling_hash',page(rev().replace(b'<sha1>'+b36(b'A & B').encode(),b'<sha1>0')),'SIBLING_SHA1_MISMATCH')
held('invalid_sibling',page(rev().replace(b'<sha1>'+b36(b'A & B').encode(),b'<sha1>*')),'SIBLING_SHA1_DELETED_OR_INVALID')
_,rr,_,_=parse(page(rev().replace(b'<sha1>'+b36(b'A & B').encode()+b'</sha1>',b'')))
assert rr[0]['sibling_SHA1']['status']=='MISSING';checks.append('missing_sibling_explicit_not_compared')

content=b'<model>wikitext</model><format>text/x-wiki</format><text>A &amp; B</text>'
def slots(body):return page(b'<revision><id>11</id><slots>'+body+b'</slots><sha1>'+b36(b'A & B').encode()+b'</sha1></revision>')
main=b'<slot role="main">'+content+b'</slot>'
pp,rr,_,_=parse(slots(main));assert not pp[0]['holds'] and rr[0]['sibling_SHA1']['status']=='MATCH';checks.append('single_main_slot')
held('aux_slot',slots(main.replace(b'"main"',b'"aux"')),'UNSUPPORTED_OR_MISSING_SLOT_ROLE')
held('missing_role',slots(main.replace(b' role="main"',b'')),'UNSUPPORTED_OR_MISSING_SLOT_ROLE')
held('multiple_main',slots(main+main),'MULTIPLE_MAIN_SLOTS')
held('mixed_slots',slots(main+main.replace(b'"main"',b'"aux"')),'MIXED_SLOT_ROLES')
held('empty_slots',slots(b''),'EMPTY_SLOTS')
held('legacy_and_slot',slots(main).replace(b'<slots>',b'<text>legacy</text><slots>'),'AMBIGUOUS_LEGACY_AND_SLOTS')
refuses('slot_cap',slots(main+main),'slot_count_limit',limits={'slots_per_revision':1})
for name,raw in [('page_child',page(extra=b'<extra>u</extra>')),('revision_child',page(rev(extra=b'<extra>u</extra>'))),('slot_child',slots(main.replace(b'</slot>',b'<extra>x</extra></slot>'))),('slots_child',slots(main+b'<extra/>'))]:
    held('unknown_'+name,raw,'UNKNOWN_CHILD_SCHEMA')
refuses('title_nested_schema',page(title=b'X<extra>Y</extra>'),'direct_title_missing_or_unsupported')
held('unknown_text_attribute',page(rev().replace(b'<text ',b'<text mystery="x" ')),'UNKNOWN_ATTRIBUTE_SCHEMA')
held('unknown_namespaced_attribute',page(rev().replace(b'<text ',b'<text xmlns:z="urn:z" z:mystery="x" ')),'UNKNOWN_ATTRIBUTE_SCHEMA')
pp,_,r,_=parse(page(extra=b'<extra>'+b'x'*1000+b'</extra>'),limits={'scalar_bytes':128})
assert 'OVERSIZED_SCALAR_METADATA' in pp[0]['holds'] and pp[0]['unknown_examples'][0]['value'] is None and r['max_scalar_retained_bytes']<=128;checks.append('unknown_oversized_scalar_hash_count_no_unbounded_value')
pp,_,_,_=parse(page(extra=b'<extra>x</extra>'*40),limits={'unknown_examples':2})
assert pp[0]['unknown_count']==40 and len(pp[0]['unknown_examples'])==2;checks.append('bounded_unknown_examples_explicit_count_digest')

# A synthetic large ordinary text is generated in fixed chunks; no 10MB page/tree copy.
huge_pages=[];huge_revisions=[]
m=s.Metadata(huge_pages.append,huge_revisions.append)
for b in [HEADER,b'<page><title>Huge</title><ns>0</ns><id>1</id><revision><id>11</id><model>wikitext</model><format>text/x-wiki</format><text>']:m.feed(b)
for _ in range(160):m.feed(b'x'*65536)
for b in [b'</text></revision></page>',b'</mediawiki>']:m.feed(b)
r=m.finish();assert huge_revisions[0]['contents'][0]['text']['decoded_UTF8_bytes']==10485760 and huge_pages[0]['main_text']['decoded_UTF8_bytes']==10485760
assert r['raw']['max_retained_source_bytes']<150000 and r['max_scalar_retained_bytes']<65536;checks.append('10MiB_ordinary_text_streamed_without_page_buffer')

for text,expected in [(b'&#233; &amp; &#x1f642;', 'é & 🙂'.encode()),(b'<![CDATA[x </page> y]]>',b'x </page> y'),(b'a\r\nb\rc',b'a\nb\nc')]:
    raw=page(b'<revision><id>11</id><model>wikitext</model><format>text/x-wiki</format><text>'+text+b'</text></revision>')
    pp,rr,_,_=parse(raw,step=1);assert rr[0]['contents'][0]['text']['decoded_SHA256']==hashlib.sha256(expected).hexdigest();checks.append('decoded_UTF8_hash_'+str(len(checks)))
refuses('mixed_element_namespace',page(extra=b'<x xmlns="urn:other"/>'),'mixed_native_namespace')
refuses('depth_limit',page(extra=b'<x>'*10+b'</x>'*10),'semantic_depth_limit',limits={'depth':8})
refuses('attribute_limit',page(extra=b'<x a="1" b="2"/>'),'semantic_attribute_limit',limits={'attributes':1})
held('single_main_slot_hash_conflict',slots(main.replace(b'</slot>',b'<sha1>0</sha1></slot>')),'CONTENT_SIBLING_SHA1_INVALID_DELETED_OR_MISMATCH')
held('duplicate_slot_containers',slots(main).replace(b'</slots>',b'</slots><slots/>'),'DUPLICATE_CONTAINER_SCHEMA')
pp,rr,r,m=parse(page(),close=False)
assert r['raw']['actual_root_closed'] is False and r['scope'].startswith('PREFIX_ONLY') and len(m.stack)==1
assert r['root_namespace_declarations']==[{'prefix':None,'URI':NS}] and r['root_attributes']=={} and r['siteinfo_fields']['base']['value']=='https://en.wikipedia.org/wiki/Main_Page'
checks.append('complete_page_prefix_open_root_no_fabricated_close')
for size in [1,2,7,31,65536]:
    a,b,c,d=parse(page(),close=False,step=size)
    assert len(a)==1 and len(b)==1 and c['raw']['actual_root_closed'] is False
    checks.append('prefix_chunk_invariance_'+str(size))
try:m.feed(b'</mediawiki>')
except ValueError:checks.append('prefix_sealed_terminal')
else:raise AssertionError('prefix not sealed')
_,_,r,_=parse(page(rev(),pid=b'1')*5000,collect=False)
assert r['pages']==5000 and r['revision_occurrences']==5000 and not r['root_holds']
checks.append('5000_pages_root_count_and_whitespace_no_page_list')
pp,rr,_,_=parse(page(rev()).replace(b'<revision>',b'<revision><comment>'+b' '*65537+b'</comment>'))
assert 'OVERSIZED_SCALAR_METADATA' in pp[0]['holds'];checks.append('large_known_comment_metadata_explicit_hold')
pp,rr,_,_=parse(page(extra=b'<mystery><id>555</id><revision><id>999</id></revision></mystery>'))
assert pp[0]['page_ID']==1 and rr[0]['revision_ID']==11 and pp[0]['unknown_count']>=4
checks.append('unknown_ancestry_cannot_supply_direct_IDs')
nsdecl=b' '.join(('xmlns:z%d="urn:%d"'%(i,i)).encode() for i in range(33))
refuses('namespace_declaration_cap',page(extra=b'<x '+nsdecl+b'/>'),'namespace_declaration_limit')
try:
    m=s.Metadata(lambda x:None,lambda x:None,token_cap=128,feed_cap=64)
    for i in range(0,len(HEADER),64):m.feed(HEADER[i:i+64])
    for _ in range(5):m.feed(b'<!--'+b'x'*60 if _==0 else b'x'*64)
except ValueError as e:assert 'lexical' in str(e);checks.append('incomplete_lexical_token_refused')
else:raise AssertionError('unbounded lexical token')
try:
    m=s.Metadata(lambda x:None,lambda x:None);m.feed(b'<!DOCTYPE mediawiki [<!ENTITY x "y">]>')
except ValueError as e:assert 'DTD_or_entity' in str(e);checks.append('DTD_refused')
else:raise AssertionError('DTD accepted')
try:
    m=s.Metadata(lambda x:None,lambda x:None);m.feed(HEADER+page()[:-3]);m.finish()
except Exception:checks.append('truncated_actual_document_refused')
else:raise AssertionError('truncated accepted')

# Header fidelity uses original prefix declarations, not invented default xmlns.
prefix=(b'<mw:mediawiki xmlns:mw="'+NS.encode()+b'" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="'+NS.encode()+b' schema.xsd">')
original=HEADER+page()+b'</mediawiki>'
# Prefix every actual element only in this small synthetic fixture.
import re
prefixed=re.sub(rb'<(/?)([a-z][a-z0-9]*)(?=[ />])',lambda m:b'<'+m[1]+b'mw:'+m[2],original)
opening=prefixed[:prefixed.index(b'>')+1]
prefixed=prefix+prefixed[len(opening):]
pp=[];rr=[];m=s.Metadata(pp.append,rr.append)
for b in prefixed:m.feed(bytes([b]))
r=m.finish()
assert r['root_namespace_declarations']==[{'prefix':'mw','URI':NS},{'prefix':'xsi','URI':'http://www.w3.org/2001/XMLSchema-instance'}]
assert r['root_attributes']['http://www.w3.org/2001/XMLSchema-instance}schemaLocation']==NS+' schema.xsd'
assert r['root_expanded_name']==NS+'}mediawiki' and prefixed[slice(*r['root_opening_span'])]==prefix
assert r['siteinfo_base_status']=='VERIFIED_HTTPS_ENWIKI_BASE' and r['siteinfo_fields']['base']['value']=='https://en.wikipedia.org/wiki/Main_Page'
checks.append('exact_prefixed_root_namespace_schemaLocation_base_header_fidelity')
for invalid in [b'http://en.wikipedia.org/wiki/Main_Page',b'https://evil.test/wiki/Main_Page',b'https://en.wikipedia.org.evil.test/',b' https://en.wikipedia.org/',b'https://en.wikipedia.org@evil.test/']:
    raw=(HEADER+page()+b'</mediawiki>').replace(b'https://en.wikipedia.org/wiki/Main_Page',invalid)
    pp=[];m=s.Metadata(pp.append,lambda x:None)
    for i in range(0,len(raw),65536):m.feed(raw[i:i+65536])
    r=m.finish();assert r['siteinfo_base_status']=='UNSUPPORTED_OR_MISSING' and 'SITEINFO_BASE_UNSUPPORTED_OR_MISSING' in pp[0]['holds']
    checks.append('invalid_siteinfo_base_'+str(len(checks)))

for ch in ['\u00a0','\u007f','\u0085','\u200b']:
    raw=(HEADER+page()+b'</mediawiki>').replace(b'https://en.wikipedia.org/wiki/Main_Page',('https://en.wikipedia.org/wiki/Main_Page'+ch).encode())
    pp=[];m=s.Metadata(pp.append,lambda x:None)
    m.feed(raw);r=m.finish()
    assert r['siteinfo_base_status']=='UNSUPPORTED_OR_MISSING' and 'SITEINFO_BASE_UNSUPPORTED_OR_MISSING' in pp[0]['holds']
    checks.append('Unicode_base_control_'+str(ord(ch)))
pp=[];rr=[];m=s.Metadata(pp.append,rr.append,boundary_flush_cap=128)
for b in HEADER:m.feed(bytes([b]))
for i in range(128):
    raw=page(pid=str(i+1).encode())
    for b in raw:m.feed(bytes([b]))
    r=m.flush_boundary();assert r['pages']==i+1 and r['raw']['boundary_flushes']==i+1 and m.span.root_closed is False
r=m.finish_prefix();assert len(pp)==128 and len(rr)==128
checks.append('128_onebyte_groups_nonterminal_flush_then_prefix_seal')
print(json.dumps({'status' :'SYNTHETIC_ONLY_PASS','count':len(checks),'checks':checks,
 'retained_source_body_reads':0,'helper_version':'v4 pending independent review; synthetic-only integration'},indent=2))
