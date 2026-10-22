"""Independent synthetic probes; no source/index/SQLite/network/ledger calls."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'enwiki-semantic-SAX-metadata-preparation-v2/semantic.py'
spec=importlib.util.spec_from_file_location('independent_semantic_v2',SOURCE)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
NS='http://www.mediawiki.org/xml/export-0.11/'
BASE='https://en.wikipedia.org/wiki/Main_Page'


def b36(raw):
    n=int(hashlib.sha1(raw).hexdigest(),16);result=''
    while n:n,c=divmod(n,36);result='0123456789abcdefghijklmnopqrstuvwxyz'[c]+result
    return result or '0'


def header(base=BASE):
    return ('<mediawiki xmlns="'+NS+'" version="0.11" xml:lang="en"><siteinfo><base>'+base+'</base><namespaces><namespace key="0"/><namespace key="4">Project</namespace></namespaces></siteinfo>').encode()


def revision(xml=b'hello',decoded=b'hello',identity=b'11'):
    h=b36(decoded).encode()
    return b'<revision><id>'+identity+b'</id><contributor><id>999</id></contributor><model>wikitext</model><format>text/x-wiki</format><text bytes="'+str(len(decoded)).encode()+b'" sha1="'+h+b'">'+xml+b'</text><sha1>'+h+b'</sha1></revision>'


def page(rev=None,identity=b'1',extra=b''):
    return b'<page><title>Example</title><ns>0</ns><id>'+identity+b'</id>'+extra+(revision() if rev is None else rev)+b'</page>'


def parse(body,step=31,prefix=False,base=BASE,tail=b''):
    pages=[];revisions=[];m=s.Metadata(pages.append,revisions.append)
    raw=header(base)+body+tail+(b'' if prefix else b'</mediawiki>')
    for i in range(0,len(raw),step):m.feed(raw[i:i+step])
    result=m.finish_prefix() if prefix else m.finish()
    return pages,revisions,result,m,raw


def run():
    passed=[];failures=[]
    def failclosed(name,action):
        try:action()
        except Exception as e:passed.append({'name':name,'error':type(e).__name__+':'+str(e)})
        else:raise AssertionError(name+' accepted')
    for value in [b'',b'0',b'-1',str(2**63).encode(),b'1 ',b'&#x661;']:
        failclosed('invalid_direct_page_identity_'+value.decode(),lambda value=value:parse(page(identity=value)))
    failclosed('opaque_revision_ID_cannot_fill_missing_direct_ID',lambda:parse(page(revision().replace(b'<id>11</id>',b'<mystery><id>11</id></mystery>'))))
    p,r,x,m,raw=parse(page(extra=b'<mystery><id>321</id><revision><id>456</id><text>fake</text></revision></mystery>'))
    assert p[0]['page_ID']==1 and len(r)==1 and r[0]['revision_ID']==11 and 'UNKNOWN_CHILD_SCHEMA' in p[0]['holds']
    passed.append({'name':'opaque_known_names_never_emit_semantic_ID_or_text'})
    p,r,x,m,raw=parse(page(revision()+revision(identity=b'0011'))+page(identity=b'2'))
    assert [(a['revision_ID'],a['page_ordinal'],a['revision_ordinal']) for a in r]==[(11,1,1),(11,1,2),(11,2,1)]
    assert p[0]['main_text'] is None and 'MULTIPLE_REVISIONS_NO_CANONICAL_SELECTION' in p[0]['holds']
    passed.append({'name':'same_and_cross_page_revision_ID_multimap_not_canonicalized'})
    for xml,decoded in [(b'a\r\nb\rc&#13;d','a\nb\nc\rd'.encode()),
                        (b'&#233; &#x1f642; &amp;', 'é 🙂 &'.encode()),
                        (b'<![CDATA[a </page> <revision> & b]]>',b'a </page> <revision> & b'),
                        (b'',b'')]:
        for step in [1,2,7,31,65536]:
            p,r,x,m,raw=parse(page(revision(xml,decoded)),step=step)
            text=r[0]['contents'][0]['text'];status=r[0]['contents'][0]['status']
            assert text['decoded_SHA1']==hashlib.sha1(decoded).hexdigest() and text['decoded_UTF8_bytes']==len(decoded)
            assert status['byte_status']==status['attribute_SHA1_status']=='MATCH' and r[0]['sibling_SHA1']['status']=='MATCH'
            a,b=p[0]['raw_XML']['start'],p[0]['raw_XML']['end']
            assert hashlib.sha256(raw[a:b]).hexdigest()==p[0]['raw_XML']['SHA256']
            passed.append({'name':'decoded_normalization_and_native_SHA_and_raw_span','xml_hex':xml.hex(),'chunk':step})
    slot=b'<slot role="main"><model>wikitext</model><format>text/x-wiki</format><text>hello</text></slot>'
    slotted=b'<revision><id>11</id><slots>'+slot+slot.replace(b'role="main"',b'role="aux"')+b'</slots><sha1>'+b36(b'hello').encode()+b'</sha1></revision>'
    p,r,x,m,raw=parse(page(slotted));assert p[0]['main_text'] is None and r[0]['sibling_SHA1']['status']=='UNVERIFIED_UNSUPPORTED_CONTENT' and 'MIXED_SLOT_ROLES' in p[0]['holds']
    passed.append({'name':'ambiguous_slots_no_main_or_native_SHA_certification'})
    for attr in [b' xmlns:q="urn:extra" q:id="4"',b' bogus="yes"']:
        p,r,x,m,raw=parse(page(revision().replace(b'<revision>',b'<revision'+attr+b'>')))
        assert 'UNKNOWN_ATTRIBUTE_SCHEMA' in p[0]['holds'];passed.append({'name':'unknown_attributes_held','attrs':attr.decode()})
    failclosed('foreign_namespace_even_when_local_field_known',lambda:parse(page(revision().replace(b'<model>',b'<model xmlns="urn:foreign">'))))
    # Root schema holds discovered after provisional pages remain frame-global.
    p,r,x,m,raw=parse(page(),tail=b'<unmodeled>tail</unmodeled>')
    assert 'UNKNOWN_CHILD_SCHEMA' in x['root_holds'] and p[0]['holds']==[]
    passed.append({'name':'late_header_hold_requires_global_caller_gate_not_prior_page_rewrite'})
    for step in [1,2,7,31,65536]:
        p,r,x,m,raw=parse(page(),step=step,prefix=True)
        assert len(p)==1 and x['raw']['actual_root_closed'] is False and len(m.stack)==1
        failclosed('sealed_prefix_feed_'+str(step),lambda:m.feed(b'</mediawiki>'))
        failclosed('sealed_prefix_fullfinish_'+str(step),m.finish)
    failclosed('partial_page_cannot_be_prefix',lambda:parse(page()[:-3],prefix=True))
    # Exact reproductions of the header-policy contract violation.
    for character,description in [('\u00a0','NBSP Unicode whitespace'),('\u007f','DEL control'),('\u0085','NEXT LINE C1 whitespace/control'),('\u200b','ZERO WIDTH SPACE format control'),('\u202e','RIGHT TO LEFT OVERRIDE format control'),('\u2066','LEFT TO RIGHT ISOLATE format control')]:
        value=BASE+character;p,r,x,m,raw=parse(page(),base=value)
        expected='UNSUPPORTED_OR_MISSING'
        record={'name':'raw_whitespace_or_control_base_must_not_be_verified','character':hex(ord(character)),
                'description':description,'base_UTF8_hex':value.encode().hex(),'fixture_XML_SHA256':hashlib.sha256(raw).hexdigest(),
                'actual_status':x['siteinfo_base_status'],'expected_status':expected,'root_holds':x['root_holds'],'page_holds':p[0]['holds']}
        if x['siteinfo_base_status']!=expected or 'SITEINFO_BASE_UNSUPPORTED_OR_MISSING' not in x['root_holds']:failures.append(record)
        else:passed.append(record)
    return {'status':'FAIL_NARROW_HEADER_URL_WHITESPACE_CONTROL_POLICY' if failures else 'PASS',
        'passed_controls':len(passed),'passes':passed,'failures':failures,
        'retained_native_or_index_body_reads':0,'network_ledger_model_training':0}


if __name__=='__main__':print(json.dumps(run(),indent=2))
