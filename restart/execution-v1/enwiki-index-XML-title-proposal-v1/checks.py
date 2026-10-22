"""Synthetic strict XML text reference checks; no retained native data."""
import json,xml.parsers.expat
from title_decode import decode_once,MAX_RAW_UTF8
checks=[]
def good(raw,want):
    r=decode_once(raw);assert r['raw_index_title']==raw and r['semantic_expected_title']==want
    oracle=[];p=xml.parsers.expat.ParserCreate();p.CharacterDataHandler=oracle.append;p.Parse(('<title>'+raw+'</title>').encode(),True)
    assert ''.join(oracle)==want
    checks.append(['PASS',raw[:80]])
def bad(raw):
    try:decode_once(raw)
    except ValueError:checks.append(['REFUSED',str(raw)[:80]])
    else:raise AssertionError('invalid reference accepted')
for raw,want in [
 ('British &amp; Irish Lions','British & Irish Lions'),
 ('&amp;&lt;&gt;&quot;&apos;','&<>"\''),
 ('&#38; &#x26; &#X26;','unused')]:
    if '&#X' in raw:bad(raw)
    else:good(raw,want)
for raw,want in [('&amp;amp;','&amp;'),('&amp;#38;','&#38;'),('&amp;nbsp;','&nbsp;'),
 ('a &lt;b&gt; c','a <b> c'),('a]]&gt;b','a]]>b'),('&#9;&#10;&#13;','\t\n\r'),
 ('&#x1F600;','😀'),('&#128512;','😀'),('&#00000000000000000000038;','&'),
 ('café e\u0301 A_B','café e\u0301 A_B'),('  A\tB  ','  A\tB  '),
 ('0xA0\u00a0Arabicالعربية','0xA0\u00a0Arabicالعربية'),('', '')]:good(raw,want)
for raw in ['&nbsp;','&apos','A & B','&#;','&#x;','&#X26;','&#-1;','&#x+26;','&# 38;',
 '&#x110000;','&#1114112;','&#0;','&#1;','&#xD800;','&#xFFFE;','&#xFFFF;',
 '<b>title</b>','<!--comment-->','<?pi x?>','<!DOCTYPE x>','x]]>y','\x00','\ud800','x\ny','x\ry',b'bytes',
 '&#'+'9'*1000+';', 'a'*(MAX_RAW_UTF8+1)]:bad(raw)
# No recursion: valid decoded content is not interpreted as another reference.
assert decode_once('&amp;#x110000;')['semantic_expected_title']=='&#x110000;'
checks.append(['PASS','no_recursive_reparse_invalid_inner_numeric'])
print(json.dumps({'status':'PASS','count':len(checks),'checks':checks,'retained_source_body_reads':0,'production_files_modified':0},ensure_ascii=True,indent=2))
