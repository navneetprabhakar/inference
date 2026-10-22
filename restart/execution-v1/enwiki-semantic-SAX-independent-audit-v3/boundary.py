"""Independent bounded semantic boundary fixtures, never native sources."""
import hashlib
import importlib.util
import json
from pathlib import Path

SOURCE=Path(__file__).resolve().parent.parent/'enwiki-semantic-SAX-metadata-preparation-v3/semantic.py'
spec=importlib.util.spec_from_file_location('independent_v3_boundary',SOURCE)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
NS=b'http://www.mediawiki.org/xml/export-0.11/'
HEADER=b'<mw:mediawiki xmlns:mw="'+NS+b'" xml:lang="en"><mw:siteinfo><mw:base>https://en.wikipedia.org/wiki/Main_Page</mw:base><mw:namespaces><mw:namespace key="0"/></mw:namespaces></mw:siteinfo>'


def page(i):
    return ('<mw:page><mw:title>Title é '+str(i)+'</mw:title><mw:ns>0</mw:ns><mw:id>'+str(i+1)+'</mw:id><mw:revision><mw:id>11</mw:id><mw:model>wikitext</mw:model><mw:format>text/x-wiki</mw:format><mw:text><![CDATA[fake </page>]]> &amp; &#13; 雪</mw:text></mw:revision></mw:page>').encode()


def feed(m,raw,step):
    for i in range(0,len(raw),step):m.feed(raw[i:i+step])


def run():
    passed=[];current=None;position=len(HEADER);page_count=0;revision_count=0
    def on_page(row):
        nonlocal page_count
        assert row['raw_XML']['start']==position and row['raw_XML']['end']==position+len(current)
        assert row['raw_XML']['SHA256']==hashlib.sha256(current).hexdigest()
        assert not row['holds'];page_count+=1
    def on_revision(row):
        nonlocal revision_count
        assert row['revision_ID']==11
        assert row['contents'][0]['text']['decoded_SHA256']==hashlib.sha256('fake </page> & \r 雪'.encode()).hexdigest()
        revision_count+=1
    m=s.Metadata(on_page,on_revision,boundary_flush_cap=10000)
    feed(m,HEADER,1)
    for i in range(10000):
        current=page(i)
        feed(m,current,[1,2,7,31,65536][i%5])
        result=m.flush_boundary()
        assert result['pages']==i+1 and result['revision_occurrences']==i+1
        assert result['raw']['scope']=='XML_BOUNDARY_ONLY_EXTERNAL_CRC_INDEX_PROOF_REQUIRED'
        assert result['raw']['boundary_flushes']==i+1 and m.span.parser.GetReparseDeferralEnabled()
        assert m.span.active is None and m.current is None and m.rev is None and m.pending is None and len(m.stack)==1
        position+=len(current)
    m.feed(b'</mw:mediawiki>');result=m.finish()
    assert result['pages']==page_count==revision_count==10000 and result['raw']['actual_root_closed']
    assert result['raw']['max_retained_source_bytes']<2048 and result['max_scalar_retained_bytes']<128
    passed.append({'name':'10000_prefixed_semantic_groups_mixed_chunks_rawspans_text_normalization_nativeIDs_constant_retention_then_actual_rootfinish','decoded_bytes':result['raw']['decoded_bytes'],'max_retained_source':result['raw']['max_retained_source_bytes'],'max_scalar':result['max_scalar_retained_bytes']})
    # Bad group endings poison the raw parser and restore streaming deferral.
    for tail in [b'<mw:page>',b'<!-- incomplete',b'<mw:page><mw:title>x']:
        m=s.Metadata(lambda row:None,lambda row:None)
        feed(m,HEADER+page(0)+tail,1)
        try:m.flush_boundary()
        except Exception as e:
            assert m.span.failed and m.span.parser.GetReparseDeferralEnabled()
            try:m.feed(b' ')
            except ValueError:pass
            else:raise AssertionError('boundary failure not terminal')
            passed.append({'name':'incomplete_semantic_group_boundary_fails_terminal_restores_deferral','tail_hex':tail.hex(),'error':type(e).__name__+':'+str(e)})
        else:raise AssertionError('incomplete group accepted')
    m=s.Metadata(lambda row:None,lambda row:None,boundary_flush_cap=1)
    feed(m,HEADER+page(0),1);m.flush_boundary()
    try:m.flush_boundary()
    except ValueError as e:
        assert 'count_limit' in str(e) and m.span.failed
        passed.append({'name':'semantic_boundary_count_cap_no_unbounded_reparse'})
    else:raise AssertionError('extra boundary accepted')
    return {'status':'PASS_INDEPENDENT_BOUNDARY_SEMANTICS_SYNTHETIC_ONLY','controls':len(passed),'cases':passed,'actual_native_index_network_ledger_model_training_operations':0}


if __name__=='__main__':print(json.dumps(run(),indent=2))
