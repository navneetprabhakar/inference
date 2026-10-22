"""Synthetic protocol/security/transport checks; no live PMC or global ledger."""
import copy,datetime,gzip,hashlib,io,json,tempfile,zlib
from pathlib import Path
from unittest.mock import patch
import discover as d

HERE=Path(__file__).parent;checks={}
Q={'verb':'ListRecords','metadataPrefix':'pmc','set':'pmc-open',**d.SCOPE}
BY='https://creativecommons.org/licenses/by/4.0/'
def record(number=1,license_url=BY,related='',language='en',author=True,body=True,article_type='research-article'):
    names='<contrib-group><contrib contrib-type="author"><name><surname>Fixture</surname><given-names>Author</given-names></name></contrib></contrib-group>' if author else ''
    contents='<body><sec><title>Introduction</title><p>Entirely synthetic guard-check prose, never a real article or training record.</p></sec></body>' if body else ''
    return f'<record><header><identifier>oai:pubmedcentral.nih.gov:{number}</identifier><datestamp>2026-01-02</datestamp><setSpec>pmc-open</setSpec></header><metadata><article xmlns="" xmlns:xlink="http://www.w3.org/1999/xlink" xml:lang="{language}" article-type="{article_type}"><front><journal-meta><journal-title-group><journal-title>Fixture Journal</journal-title></journal-title-group></journal-meta><article-meta><article-id pub-id-type="pmc">{number}</article-id><article-id pub-id-type="doi">10.0000/fixture.{number}</article-id><title-group><article-title>Fixture full article</article-title></title-group>{names}<pub-date pub-type="epub"><year>2020</year></pub-date><permissions><license xlink:href="{license_url}"><license-p>Creative Commons Attribution</license-p></license></permissions>{related}</article-meta></front>{contents}</article></metadata></record>'
def envelope(records,token='',query=Q):
    attrs=' '.join(f'{k}="{v}"' for k,v in query.items())
    return ('<OAI-PMH xmlns="'+d.pmc.OAI+'"><responseDate>2026-01-03T00:00:00Z</responseDate><request '+attrs+'>'+d.BASE+'</request><ListRecords>'+''.join(records)+'<resumptionToken>'+token+'</resumptionToken></ListRecords></OAI-PMH>').encode()
def refused(fn):
    try:fn()
    except (ValueError,KeyError,zlib.error):return True
    return False
raw=envelope([record()],token='remaining-cursor')
rows,extras,token,date=d.parse(raw,Q,0)
checks['native_full_JATS_identity_and_body']=rows[0]['pmcid']=='1' and rows[0]['metadata_filter_eligible'] and b'Synthetic' not in extras[0]['article_xml'] and rows[0]['fulltext_body_characters']>0
checks['incomplete_cursor_preserved']=token=='remaining-cursor'
checks['source_hash_distinct_from_derivative']=rows[0]['source_original_decoded_response_sha256']==d.sha(raw) and rows[0]['serialized_article_sha256']!=d.sha(raw)
checks['no_human_authorship_certification']='not independently certified' in rows[0]['authorship_scope']
for name,url in [('NC','https://creativecommons.org/licenses/by-nc/4.0/'),('ND','https://creativecommons.org/licenses/by-nd/4.0/'),('SA','https://creativecommons.org/licenses/by-sa/4.0/'),('spoof','https://creativecommons.org.evil.invalid/licenses/by/4.0/'),('credentials','https://evil@creativecommons.org/licenses/by/4.0/')]:
    checks['hold_license_'+name]=not d.parse(envelope([record(license_url=url)]),Q,0)[0][0]['metadata_filter_eligible']
checks['CC0_candidate']=d.parse(envelope([record(license_url='https://creativecommons.org/publicdomain/zero/1.0/')]),Q,0)[0][0]['metadata_filter_eligible']
checks['nonEnglish_hold']=not d.parse(envelope([record(language='fr')]),Q,0)[0][0]['metadata_filter_eligible']
checks['missing_named_author_hold']=not d.parse(envelope([record(author=False)]),Q,0)[0][0]['metadata_filter_eligible']
checks['missing_body_hold']=not d.parse(envelope([record(body=False)]),Q,0)[0][0]['metadata_filter_eligible']
checks['retraction_article_hold']=not d.parse(envelope([record(article_type='retraction')]),Q,0)[0][0]['metadata_filter_eligible']
rel='<related-article related-article-type="retracted-article" ext-link-type="doi" xlink:href="10.0000/fixture.2"/>'
family=d.parse(envelope([record(related=rel),record(2)]),Q,0)[0]
checks['unrelated_target_provisional_eligibility_before_join']=family[1]['metadata_filter_eligible'] is True
d.finalize(family)
checks['observed_retraction_family_propagation']=family[0]['family_id']==family[1]['family_id'] and all(not x['metadata_filter_eligible'] for x in family)
checks['final_eligibility_recomputed_after_join']=all(row['metadata_filter_eligible']==(not row['holds']) and row['eligibility_scope']=='POST_OBSERVED_LOCAL_FAMILY_CHECKS_NO_EXTERNAL_STATUS_CLEARANCE' for row in family)
deleted='<record><header status="deleted"><identifier>oai:pubmedcentral.nih.gov:9</identifier><datestamp>2026-01-02</datestamp></header></record>'
deleted_rows,deleted_extras,_,_=d.parse(envelope([deleted]),Q,0)
checks['deleted_noarticle_explicit_held_eligibility']=deleted_extras==[None] and deleted_rows[0]['metadata_filter_eligible'] is False and 'no_full_JATS_article_held' in deleted_rows[0]['holds']
d.finalize(deleted_rows)
checks['deleted_final_counting_safe']=sum(r['metadata_filter_eligible'] for r in deleted_rows)==0 and deleted_rows[0]['eligibility_scope']=='POST_OBSERVED_LOCAL_FAMILY_CHECKS_NO_EXTERNAL_STATUS_CLEARANCE'
checks['nondeleted_missing_article_fails_closed']=refused(lambda:d.parse(envelope([deleted.replace(' status="deleted"','')]),Q,0))

checks['wrong_request_binding_refused']=refused(lambda:d.parse(raw,{'verb':'GetRecord'},0))
checks['unexpected_page_size_refused']=refused(lambda:d.parse(envelope([record(i) for i in range(1,12)]),Q,0))
checks['xml_entity_refused']=refused(lambda:d.parse(b'<!DOCTYPE x [<!ENTITY p SYSTEM "file:///etc/passwd">]>'+raw,Q,0))
checks['utf16_screen_bypass_refused']=refused(lambda:d.parse(raw.decode().encode('utf-16'),Q,0))
compressed=gzip.compress(raw)
checks['gzip_decodes_with_hashable_wire']=d.decode(compressed,'gzip')==raw
checks['deflate_decodes']=d.decode(zlib.compress(raw),'deflate')==raw
checks['decompression_bomb_refused']=refused(lambda:d.decode(gzip.compress(b'x'*10000),'gzip',limit=100))
checks['truncated_gzip_refused']=refused(lambda:d.decode(compressed[:-5],'gzip'))
checks['concatenated_stream_refused']=refused(lambda:d.decode(compressed+compressed,'gzip'))
checks['unknown_encoding_refused']=refused(lambda:d.decode(compressed,'br'))
guard=d.pmc.SerialRequestGuard(5);stamp=datetime.datetime(2026,10,21,12,tzinfo=datetime.timezone.utc)
guard.start(10,stamp)
checks['concurrent_request_refused']=refused(lambda:guard.start(11,stamp+datetime.timedelta(seconds=1)))
guard.finish();checks['subsecond_rate_refused']=refused(lambda:guard.start(10.5,stamp+datetime.timedelta(seconds=.5)))
checks['offpeak_required_when_over100']=refused(lambda:d.pmc.SerialRequestGuard(101).start(10,stamp))
class Response(io.BytesIO):
    def __init__(self,body,url,mime='application/xml',encoding=None,length=None):
        super().__init__(body);self.url=url;self.headers={'Content-Type':mime}
        if encoding:self.headers['Content-Encoding']=encoding
        if length is not None:self.headers['Content-Length']=str(length)
    def geturl(self):return self.url
class Opener:
    def __init__(self,response):self.response=response;self.calls=0;self.request=None
    def open(self,request,**kwargs):self.calls+=1;self.request=request;return self.response
with tempfile.TemporaryDirectory(prefix='pmc-discovery-offline-') as temp:
    root=Path(temp);dest=root/'outputs';dest.mkdir();ledger=d.IntakeLedger(root/'temporary-ledger',{'version':'synthetic-test','limits':{'requests':20,'body_bytes':20000000,'rows':200,'output_bytes':500000000},'wall_seconds':60})
    with patch.object(d,'ROOT',root),patch.object(d,'DEST',dest),patch.object(d,'storage',return_value={'protected_bytes':0}),patch.object(d,'RESPONSE_CAP',10000):
        try:
            url=d.BASE+'?'+d.urlencode(Q);op=Opener(Response(compressed,url,encoding='gzip',length=len(compressed)))
            plain,receipt=d.fetch(ledger,d.pmc.SerialRequestGuard(5),Q,0,d.time.monotonic(),0,opener=op)
            checks['wire_charge_and_decoded_hash_verified']=plain==raw and receipt['body_bytes']==len(compressed) and receipt['decoded_sha256']==d.sha(raw) and ledger.db.execute('SELECT actual_bytes FROM attempts').fetchone()[0]==len(compressed)
            checks['compression_accept_header_exact']=op.request.headers['Accept-encoding']=='gzip, deflate'
            checks['no_retry_success_one_request']=op.calls==1
            op=Opener(Response(b'x'*10000,url));g=d.pmc.SerialRequestGuard(5)
            checks['wire_cap_refused']=refused(lambda:d.fetch(ledger,g,Q,1,d.time.monotonic(),10000,opener=op))
            checks['wire_cap_no_extra_probe']=(dest/'response-001.body.partial').stat().st_size==10000
            checks['failed_charge_durable']=ledger.db.execute('SELECT state FROM attempts WHERE key=?',('pmc-native-oai-discovery-v1-page-001',)).fetchone()==('failed',)
            before=ledger.totals().copy();op=Opener(Response(b'{}',url))
            checks['local_cap_before_reservation']=refused(lambda:d.fetch(ledger,d.pmc.SerialRequestGuard(5),Q,2,d.time.monotonic(),d.BODY_CAP,opener=op)) and op.calls==0 and ledger.totals()==before
            used=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())
            with patch.object(d,'OUTPUT_CAP',used+10):
                checks['aggregate_output_before_io']=refused(lambda:d.fetch(ledger,d.pmc.SerialRequestGuard(5),Q,2,d.time.monotonic(),0,opener=op)) and op.calls==0 and ledger.totals()==before
                checks['aggregate_receipt_prewrite']=refused(lambda:d.save(dest/'large.json',{'x':'a'*100})) and not(dest/'large.json').exists()
        finally:ledger.close()
assert all(checks.values()),checks
result={'status':'PASS_OFFLINE_PROTOCOL_AND_RESOURCE_GUARDS','checks':checks,'case_count':len(checks),'live_source_requests':0,'global_ledger_opened':False,'training_or_admission':False,'code_sha256':d.sha((HERE/'discover.py').read_bytes())}
(HERE/'offline-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
