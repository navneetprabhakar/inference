"""Offline transport/archive adversarial checks; uses only temporary test ledger."""
import copy,hashlib,io,json,tempfile,zipfile
from pathlib import Path
from unittest.mock import patch
import download_discovery as d
from inspect_epub import inspect,safe_xml
from prepare_frame import evaluate

HERE=Path(__file__).parent
checks={}
EXPECTED={'doi':'10.11647/OBP.TEST','authors':['Fixture Author'],'license':'http://creativecommons.org/licenses/by/4.0/','epub_isbn':'978-1-78374-125-0'}
OPF=b'''<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Fixture Author</dc:creator><dc:identifier>10.11647/OBP.TEST</dc:identifier></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="b"/><itemref idref="a"/></spine></package>'''
CONTAINER=b'<container><rootfiles><rootfile full-path="OEBPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
HTML=b'<html><body><h1>Synthetic fixture only</h1><p>https://creativecommons.org/licenses/by/4.0/</p></body></html>'

def archive(path,extra=None,opf=OPF,html=HTML,symlink=False):
    with zipfile.ZipFile(path,'w') as z:
        for name,data in [('mimetype',b'application/epub+zip'),('META-INF/container.xml',CONTAINER),('OEBPS/book.opf',opf),('OEBPS/a.xhtml',html),('OEBPS/b.xhtml',HTML)]:z.writestr(name,data)
        if extra:z.writestr(extra,b'bad')
        if symlink:
            info=zipfile.ZipInfo('linked');info.create_system=3;info.external_attr=(0o120777<<16);z.writestr(info,b'/etc/passwd')

def fails(action):
    try:action()
    except (ValueError,KeyError,zipfile.BadZipFile):return True
    return False

class Response(io.BytesIO):
    def __init__(self,body,mime='application/json',length=None,url='https://export.thoth.pub/test'):
        super().__init__(body);self.headers={'Content-Type':mime};self.url=url
        if length is not None:self.headers['Content-Length']=str(length)
    def geturl(self):return self.url
class Opener:
    def __init__(self,response):self.response=response;self.calls=0
    def open(self,*args,**kwargs):self.calls+=1;return self.response

item=json.loads((HERE/'preparation.json').read_text())['initial_discovery'][0]
metadata={'workId':item['work_id'],'workStatus':'ACTIVE','workType':'MONOGRAPH','license':item['observed_work_license'],'languages':[{'languageCode':'ENG'}],'imprint':{'publisher':{'publisherName':'Open Book Publishers'}},'doi':'https://doi.org/'+item['doi'],'titles':[{'canonical':True,'localeCode':'EN','fullTitle':item['title']}],'copyrightHolder':'; '.join(item['authors']),'publicationDate':item['publication_date'],'publications':[{'publicationType':'EPUB','isbn':item['epub_isbn'],'locations':[{'canonical':True,'fullTextUrl':item['native_epub_url_observed_in_primary_locations']}]}],'jsonGeneratedAt':'2026-08-27T02:56:54Z'}
checks['metadata_exact_identity_license_isbn_valid']=d.validate_metadata(metadata,item)['work_uuid']==item['work_id']
for field,value in [('license','https://creativecommons.org/publicdomain/zero/1.0/'),('copyrightHolder','Different Author'),('publicationDate','2016-01-01'),('workId','00000000-0000-4000-8000-000000000008')]:
    altered=copy.deepcopy(metadata);altered[field]=value
    checks['metadata_pinned_'+field+'_change_refused']=fails(lambda:d.validate_metadata(altered,item))
altered=copy.deepcopy(metadata);altered['publications'][0]['isbn']='978-0-00000-000-0'
checks['metadata_pinned_epub_isbn_change_refused']=fails(lambda:d.validate_metadata(altered,item))

with tempfile.TemporaryDirectory(prefix='obp-offline-guardcheck-') as tmp:
    root=Path(tmp);good=root/'fixture.epub';archive(good)
    result=inspect(good,root/'good',EXPECTED)
    checks['spine_order_preserved']=[x['member'] for x in result['spine_order']]==['OEBPS/b.xhtml','OEBPS/a.xhtml']
    checks['original_html_preserved_byte_exact']=all(Path(x['path']).read_bytes()==HTML for x in result['preserved_original_xml_html'] if x['member'].endswith('.xhtml'))
    checks['never_admits']=result['admitted_documents']==result['admitted_tokens']==result['external_requests']==0
    aggregate=root/'aggregate';aggregate.mkdir()
    (aggregate/'raw-metadata-and-log-fixture').write_bytes(b'prior raw metadata and receipts count too')
    inspect(good,aggregate/'book1',EXPECTED,budget_root=aggregate,budget_cap=1000000)
    inspect(good,aggregate/'book2',EXPECTED,budget_root=aggregate,budget_cap=1000000)
    before=sum(x.stat().st_size for x in aggregate.rglob('*') if x.is_file())
    checks['third_book_aggregate_cap_refused_before_write']=fails(lambda:inspect(good,aggregate/'book3',EXPECTED,budget_root=aggregate,budget_cap=before+100))
    checks['third_book_refusal_creates_no_partial_output']=not(aggregate/'book3').exists() and before==sum(x.stat().st_size for x in aggregate.rglob('*') if x.is_file())
    checks['aggregate_counts_raw_metadata_and_receipts']=result['aggregate_output_budget']['all_existing_root_files_counted'] and before>sum(x.stat().st_size for x in (aggregate/'book1').rglob('*') if x.is_file())+sum(x.stat().st_size for x in (aggregate/'book2').rglob('*') if x.is_file())
    with patch.object(d,'DEST',aggregate),patch.object(d,'PROCESSED_CAP',before+10):
        checks['terminal_receipt_cap_checked_before_write']=fails(lambda:d.write(aggregate/'oversized-receipt.json',{'payload':'x'*100})) and not(aggregate/'oversized-receipt.json').exists()

    for name,bad in [('parent','../outside'),('absolute','/outside'),('backslash','a\\outside')]:
        p=root/(name+'.epub');archive(p,extra=bad)
        checks['refuse_archive_'+name]=fails(lambda:inspect(p,root/(name+'-out'),EXPECTED))
        checks['no_output_on_'+name]=not(root/(name+'-out')).exists()
    p=root/'symlink.epub';archive(p,symlink=True)
    checks['refuse_symlink_member']=fails(lambda:inspect(p,root/'symlink-out',EXPECTED))
    p=root/'entity.epub';archive(p,html=b'<!DOCTYPE html [<!ENTITY x SYSTEM "file:///etc/passwd">]><html><p>&x;</p></html>')
    checks['refuse_external_entity_before_text_read']=fails(lambda:inspect(p,root/'entity-out',EXPECTED))
    checks['refuse_utf16_entity_screen_bypass']=fails(lambda:safe_xml('<!DOCTYPE html [<!ENTITY x SYSTEM \"file:///etc/passwd\">]><html>&x;</html>'.encode('utf-16')))
    p=root/'missing.epub';archive(p,opf=OPF.replace(b'href="b.xhtml"',b'href="missing.xhtml"'))
    checks['refuse_missing_spine_file']=fails(lambda:inspect(p,root/'missing-out',EXPECTED))
    p=root/'crc.epub';archive(p)
    raw=bytearray(p.read_bytes());position=raw.find(b'Synthetic fixture only');raw[position]=ord('X');p.write_bytes(raw)
    checks['crc_corruption_refused']=fails(lambda:inspect(p,root/'crc-out',EXPECTED))
    bad_expected={**EXPECTED,'authors':['Different Author']}
    mismatch=inspect(good,root/'author-mismatch',bad_expected)
    checks['author_mismatch_flagged_for_review']='creator_name_mismatch_or_missing_needs_review' in mismatch['review_flags'] and mismatch['admitted_tokens']==0
    p=root/'license.epub';archive(p,html=HTML.replace(b'/by/4.0/',b'/by-nc-nd/4.0/'))
    mismatch=inspect(p,root/'license-out',EXPECTED)
    checks['artifact_license_conflict_flagged']='other_license_urls_require_member_and_exception_review' in mismatch['review_flags'] and mismatch['admitted_tokens']==0
    contract={'version':'synthetic-offline-test','limits':{'requests':20,'body_bytes':10000,'rows':1,'output_bytes':10000},'wall_seconds':60}
    ledger=d.IntakeLedger(root/'temporary-ledger',contract)
    with patch.object(d,'ROOT',root),patch.object(d,'storage',return_value={'protected_bytes':0}):
        try:
            opener=Opener(Response(b'{"fixture":true}'))
            receipt=d.transfer(ledger,'good','https://export.thoth.pub/test',root/'received.json',100,'metadata',d.time.monotonic(),0,opener)
            checks['successful_body_ledger_hash_bound']=ledger.db.execute('SELECT state,actual_bytes,body_sha256 FROM attempts WHERE key=?',('good',)).fetchone()==('complete',16,hashlib.sha256(b'{"fixture":true}').hexdigest())
            try:d.transfer(ledger,'good','https://export.thoth.pub/test',root/'received.json',100,'metadata',d.time.monotonic(),0,opener)
            except FileExistsError:checks['no_retry_on_existing_payload']=opener.calls==1
            else:checks['no_retry_on_existing_payload']=False
            opener=Opener(Response(b'x'*100))
            checks['body_cap_refused']=fails(lambda:d.transfer(ledger,'overflow','https://export.thoth.pub/test',root/'overflow',100,'metadata',d.time.monotonic(),0,opener))
            checks['never_reads_unreserved_probe']=(root/'overflow.partial').stat().st_size==100
            checks['failed_reservation_retained']=ledger.db.execute('SELECT state FROM attempts WHERE key=?',('overflow',)).fetchone()==('failed',) and ledger.totals()['body_bytes']==200
            opener=Opener(Response(b'{}',url='https://evil.invalid/test'))
            checks['redirected_origin_refused']=fails(lambda:d.transfer(ledger,'redirect','https://export.thoth.pub/test',root/'redirect',100,'metadata',d.time.monotonic(),0,opener))
            opener=Opener(Response(b'{}',length=50))
            checks['truncated_response_refused']=fails(lambda:d.transfer(ledger,'truncated','https://export.thoth.pub/test',root/'truncated',100,'metadata',d.time.monotonic(),0,opener))
            opener=Opener(Response(b'{}',mime='text/html'))
            checks['html_login_or_error_refused']=fails(lambda:d.transfer(ledger,'mime','https://export.thoth.pub/test',root/'mime',100,'metadata',d.time.monotonic(),0,opener))
            before=ledger.totals().copy()
            opener=Opener(Response(b'{}'))
            checks['per_run_budget_refused_before_request']=fails(lambda:d.transfer(ledger,'local-limit','https://export.thoth.pub/test',root/'local-limit',100,'metadata',d.time.monotonic(),d.TOTAL_CAP-99,opener)) and opener.calls==0 and ledger.totals()==before
            with patch.object(d,'storage',side_effect=ValueError('synthetic low disk')):
                checks['disk_floor_refused_before_reserve']=fails(lambda:d.transfer(ledger,'disk-floor','https://export.thoth.pub/test',root/'disk-floor',100,'metadata',d.time.monotonic(),0,opener)) and ledger.totals()==before
        finally:ledger.close()
assert all(checks.values()),checks
report={'status':'PASS_OFFLINE_DISCOVERY_GUARDS','checks':checks,'checks_count':len(checks),'source_corpus_downloaded':False,'global_intake_ledger_opened':False,'global_ledger_mutated':False,'models_initialized':0,'code_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['download_discovery.py','inspect_epub.py','prepare_frame.py']}}
(HERE/'discovery-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
