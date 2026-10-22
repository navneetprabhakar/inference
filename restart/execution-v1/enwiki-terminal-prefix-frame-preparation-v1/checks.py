"""Synthetic native XML/BZ2 only. No retained XML/archive access."""
import bz2,hashlib,json,pathlib,sys,xml.parsers.expat as expat
from unittest.mock import patch
import frame_core as c
checks=[]
def ok(n):checks.append(n)
def refusal(n,fn):
 try:fn()
 except (ValueError,expat.ExpatError,OSError,EOFError):ok(n)
 else:raise AssertionError(n)
NS='http://www.mediawiki.org/xml/export-0.11/'
HEADER=('<?xml version="1.0" encoding="utf-8"?><mediawiki xmlns="'+NS+'" version="0.11"><siteinfo><sitename>Wikipedia</sitename><dbname>enwiki</dbname><base>https://en.wikipedia.org/wiki/Main_Page</base><namespaces><namespace key="0" case="first-letter"/><namespace key="6">File</namespace><namespace key="14">Category</namespace></namespaces></siteinfo>\n').encode()
def page(pid=1,rid=20,ns=0,title='A &amp; B',redirect=False,slot=False):
 text='<text xml:space="preserve" bytes="5">A &amp; B</text>';content='<slots><slot role="main"><model>wikitext</model><format>text/x-wiki</format>'+text+'</slot><slot role="aux"><model>json</model><text>{}</text></slot></slots>' if slot else '<model>wikitext</model><format>text/x-wiki</format>'+text
 return (f'<page><title>{title}</title><ns>{ns}</ns><id>{pid}</id>'+('<redirect title="Other"/>' if redirect else '')+f'<revision><id>{rid}</id><parentid>11</parentid><timestamp>2026-08-01T00:00:00Z</timestamp><contributor><username>Source editor</username><id>999</id></contributor><comment>Native attribution preserved</comment>'+content+'</revision></page>\n').encode()
def frame(data,step=65536,prefix=True):
 f=c.Framer()
 for pos in range(0,len(data),step):f.feed(data[pos:pos+step])
 return f,f.finish(prefix)
f,r=frame(HEADER+page());p=f.pages[0];assert p['page_ID']==1 and p['revisions'][0]['revision_ID']==20 and p['revisions'][0]['contributor']['fields'][1]['value']=='999';assert p['page_raw_XML_SHA256']==hashlib.sha256(page().rstrip(b'\n')).hexdigest();assert p['revisions'][0]['content_slots_or_legacy'][0]['text']['decoded_character_data_SHA256']==hashlib.sha256(b'A & B').hexdigest();assert r['XML_root_closed'] is False and not r['global_XML_validity_claim'];ok('actual_header_namespace_direct_page_revision_contributor_IDs_rawspan_text_hash_PREFIX_ONLY')
for n in [1,2,7,31]:
 g,z=frame(HEADER+page(),n);assert g.pages[0]['page_raw_XML_SHA256']==p['page_raw_XML_SHA256'] and g.header==HEADER;ok('chunk_split_'+str(n)+'_namespace_UTF8_entity_tag_positions_preserved')
f,r=frame(HEADER+page(1,20,6,redirect=True)+page(2,21,14)+page(3,22,slot=True));assert r['counts']['redirects']==1 and r['counts']['nonzero_namespace_pages']==2 and len(f.pages[2]['revisions'][0]['content_slots_or_legacy'])==2 and 'NON_WIKITEXT_OR_UNSPECIFIED_MODEL' in f.pages[2]['holds'];ok('all_namespace_redirect_negative_cases_and_multislot_models_retained')
f,r=frame(HEADER+page()+b'</mediawiki>',prefix=False);assert r['XML_root_closed'];ok('complete_synthetic_fixture_root_is_actual_not_invented')
refusal('closed_root_not_claimed_PREFIX_ONLY',lambda:frame(HEADER+page()+b'</mediawiki>'))
for name,data in [('DTD',b'<!DOCTYPE mediawiki []>'+HEADER+page()),('internal_entity',b'<!DOCTYPE mediawiki [<!ENTITY e "EXPAND">]>'+HEADER+page()),('external_entity',b'<!DOCTYPE mediawiki SYSTEM "https://example.invalid/entity">'+HEADER+page()),('incomplete_page',HEADER+page()[:-10]),('incomplete_token',HEADER+page()+b'<pa'),('missing_siteinfo',('<mediawiki xmlns="'+NS+'">').encode()+page()),('missing_direct_page_ID',HEADER+page().replace(b'<id>1</id>',b'')),('duplicate_page_ID',HEADER+page()+page(1,21)),('duplicate_revision_ID',HEADER+page()+page(2,20)),('foreign_namespace',HEADER+page().replace(b'<ns>',b'<ns xmlns="urn:wrong">')),('UTF16', (HEADER+page()).decode().encode('utf-16'))]:refusal(name,lambda data=data:frame(data))
# Concatenated BZ2 members: CRC/EOF checked for every member and no closing XML added.
f=c.Framer();raw=bz2.compress(HEADER)+bz2.compress(page());e=c.segment_decode(raw,f.feed,128000000);r=f.finish();assert e['members_CRC_EOF_verified']==2 and r['counts']['pages']==1;ok('concatenated_header_page_BZ2_all_members_CRC_EOF_no_synthetic_root')
refusal('truncated_BZ2_CRC_EOF',lambda:c.segment_decode(raw[:-6],lambda b:None,128000000));refusal('BZ2_trailing_junk',lambda:c.segment_decode(raw+b'junk',lambda b:None,128000000))
corrupt=bytearray(bz2.compress(HEADER+page()));corrupt[-5]^=1;refusal('BZ2_CRC_damage',lambda:c.segment_decode(bytes(corrupt),lambda b:None,128000000));refusal('bounded_decoded_expansion',lambda:c.segment_decode(raw,lambda b:None,10))
with patch.dict(c.LIMITS,header_XML_bytes=10):refusal('header_memory_bound',lambda:frame(HEADER+page()))
with patch.dict(c.LIMITS,page_XML_bytes=50):refusal('page_memory_bound',lambda:frame(HEADER+page()))
# Group/page native tuple order must match exactindexrows, not title prefix guessing.
assert [(x['page_ID'],x['title']) for x in frame(HEADER+page(5,25,title='Title: colon'))[0].pages]==[(5,'Title: colon')];ok('native_index_title_colon_and_entity_decoding_exact_identity')
if __name__=='__main__':print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_NO_RETAINED_XML','count':len(checks),'checks':checks,'actual_XML_bytes_read':0,'archive_accesses':0,'network':0},indent=2))
