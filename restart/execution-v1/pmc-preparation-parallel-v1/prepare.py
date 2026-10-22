"""Offline bounded PMC OAI/JATS front-matter frame preparation.

No networking, corpus admission, model operations or global-ledger mutations.
Local response manifest is a project-defined input, not an invented PMC API.
"""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

from lxml import etree

OAI='http://www.openarchives.org/OAI/2.0/'
XLINK='{http://www.w3.org/1999/xlink}href'
BASE='https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/'
MAX_ARTICLES=1200
MAX_REQUESTS=2400
MAX_RESPONSE_BYTES=8*1024*1024
MAX_FRAME_BYTES=128*1024*1024
MAX_OUTPUT_BYTES=256*1024*1024

def sha(b):return hashlib.sha256(b).hexdigest()
def norm(s):return re.sub(r'\s+',' ',s or '').strip()
def text(n):return norm(' '.join(n.itertext())) if n is not None else ''
def local(n):return etree.QName(n).localname if isinstance(n.tag,str) else ''
def children(n,name):return [x for x in n if local(x)==name]
def descendants(n,name):return [x for x in n.iter() if local(x)==name]
def one(n,name):
    xs=children(n,name)
    if len(xs)!=1:raise ValueError('expected_one_'+name)
    return xs[0]

def cc_url(s):
    u=urlparse(s)
    if u.scheme not in ['http','https'] or u.hostname not in ['creativecommons.org','www.creativecommons.org'] or u.query or u.fragment:
        return None
    path=u.path.rstrip('/')
    # Only exact unported CC BY or CC0 URI shapes; never substring-match by-sa.
    path=re.sub(r'/(?:legalcode|deed(?:\.[a-zA-Z_-]+)?)$','',path)
    if re.fullmatch(r'/licenses/by/(?:2\.0|2\.5|3\.0|4\.0)',path):return 'https://creativecommons.org'+path+'/'
    if path=='/publicdomain/zero/1.0':return 'https://creativecommons.org/publicdomain/zero/1.0/'
    return None

def identifiers(meta):
    result={}
    for x in descendants(meta,'article-id'):
        kind=x.get('pub-id-type','').lower();value=text(x)
        if kind in ['doi','pmid','pmc','pmcid']:
            if kind=='doi':value=re.sub(r'^https?://(?:dx\.)?doi\.org/','',value,flags=re.I).lower()
            if kind in ['pmc','pmcid']:kind='pmcid';value=re.sub(r'^PMC','',value,flags=re.I)
            result.setdefault(kind,[]).append(value)
    return {k:sorted(set(v)) for k,v in result.items()}

def permission_review(article,meta):
    main=children(meta,'permissions')
    allperms=descendants(article,'permissions')
    urls=[];raw=[];holds=[]
    for p in allperms:
        raw.append({'context_path':p.getroottree().getpath(p),'xml':etree.tostring(p,encoding='unicode')})
    if not main:holds.append('missing_article_permissions')
    for p in main:
        for n in p.iter():
            if local(n) in ['license','license_ref'] and any('date' in k.lower() for k in n.attrib):holds.append('time_qualified_license_requires_review')
            if local(n) in ['license','ext-link'] and n.get(XLINK):urls.append(n.get(XLINK))
            if local(n)=='license_ref' and text(n):urls.append(text(n))
        wording=(text(p)+' '+' '.join(str(v) for n in p.iter() for v in n.attrib.values())).lower()
        if re.search(r'non.?commercial|no.?derivatives?|share.?alike|\bcc[- ]by[- ](?:nc|nd|sa)\b|all rights reserved|permission (?:is )?required|except (?:as |where |for )|unless otherwise',wording):
            holds.append('restricted_or_exception_license_wording')
    if not urls:holds.append('no_explicit_article_license_uri')
    normalized=[cc_url(x) for x in urls]
    if any(x is None for x in normalized):holds.append('non_allowlisted_license_uri')
    if len(allperms)>len(main):holds.append('object_or_subarticle_permissions_need_review')
    return {'observed_license_uris':sorted(set(urls)),'allowlisted_license_uris':sorted(set(x for x in normalized if x)),
            'permissions_xml':raw,'holds':sorted(set(holds)),
            'scope':'Metadata filter only; full-text permissions/attribution/object exceptions must be rechecked.'}

def parse_response(payload,response_ref,expected_query=None):
    if len(payload)>MAX_RESPONSE_BYTES:raise ValueError('response_byte_limit')
    if re.search(br'<!DOCTYPE|<!ENTITY',payload,re.I):raise ValueError('DTD_or_entity_declaration_forbidden')
    parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False)
    root=etree.fromstring(payload,parser)
    if root.tag!='{'+OAI+'}OAI-PMH':raise ValueError('unknown_OAI_envelope')
    if root.find('{'+OAI+'}error') is not None:raise ValueError('OAI_error_response')
    response_date=text(root.find('{'+OAI+'}responseDate'))
    if not response_date:raise ValueError('missing_response_date')
    datetime.strptime(response_date,'%Y-%m-%dT%H:%M:%SZ')
    request=root.find('{'+OAI+'}request')
    if request is None or text(request)!=BASE:raise ValueError('missing_or_unknown_OAI_request_binding')
    if expected_query is not None and dict(request.attrib)!=expected_query:raise ValueError('payload_request_manifest_mismatch')
    listing=root.find('{'+OAI+'}ListRecords')
    if listing is None:raise ValueError('expected_ListRecords_front_matter')
    records=[]
    for r in listing.findall('{'+OAI+'}record'):
        header=r.find('{'+OAI+'}header')
        if header is None:raise ValueError('missing_OAI_header')
        ident=text(header.find('{'+OAI+'}identifier'))
        match=re.fullmatch(r'oai:pubmedcentral\.nih\.gov:([1-9][0-9]*)',ident)
        if not match:raise ValueError('unknown_OAI_identifier')
        stamp=text(header.find('{'+OAI+'}datestamp'))
        if not stamp:raise ValueError('missing_OAI_datestamp')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z)?',stamp):raise ValueError('invalid_OAI_datestamp')
        datetime.strptime(stamp,'%Y-%m-%dT%H:%M:%SZ' if 'T' in stamp else '%Y-%m-%d')
        row={'oai_identifier':ident,'pmcid':match.group(1),'oai_datestamp':stamp,
             'oai_set_specs':[text(n) for n in header.findall('{'+OAI+'}setSpec')],
             'source_response_sha256':sha(payload),'source_response_ref':response_ref,
             'response_date':response_date,'training_admitted':False,'holds':[]}
        if header.get('status')=='deleted':
            row.update({'metadata_filter_eligible':False,'holds':['OAI_deleted_record'],'identifiers':{'pmcid':[match.group(1)]},'related_articles':[]})
            records.append(row);continue
        md=r.find('{'+OAI+'}metadata')
        arts=[] if md is None else [x for x in md if local(x)=='article']
        if len(arts)!=1:raise ValueError('unknown_JATS_metadata_article_shape')
        article=arts[0];front=one(article,'front');meta=one(front,'article-meta')
        ids=identifiers(meta)
        if ids.get('pmcid') and ids['pmcid']!=[row['pmcid']]:raise ValueError('PMCID_header_metadata_mismatch')
        ids.setdefault('pmcid',[row['pmcid']])
        related=[{'attributes':dict(n.attrib),'text':text(n),'xml':etree.tostring(n,encoding='unicode')} for n in descendants(article,'related-article')]
        risk_type=article.get('article-type','').lower()
        if re.search(r'retract|withdraw|correct|errat|expression.of.concern|addendum',risk_type):row['holds'].append('correction_retraction_or_update_article_type')
        if any(re.search(r'retract|withdraw|correct|errat|concern|updated|version|addendum',str(x['attributes']),re.I) for x in related):row['holds'].append('related_correction_retraction_or_version_status')
        language=article.get('{http://www.w3.org/XML/1998/namespace}lang')
        if language!='en':row['holds'].append('English_language_not_explicitly_confirmed')
        permission=permission_review(article,meta);row['holds']+=permission['holds']
        title_nodes=descendants(meta,'article-title')
        if len(title_nodes)!=1:row['holds'].append('missing_or_multiple_titles')
        journal_nodes=descendants(front,'journal-title')
        dates=[{'attributes':dict(n.attrib),'text':text(n),'xml':etree.tostring(n,encoding='unicode')} for n in descendants(meta,'pub-date')]
        row.update({'identifiers':ids,'title':text(title_nodes[0]) if title_nodes else '',
                    'journal_titles':[text(x) for x in journal_nodes],'publication_dates':dates,
                    'article_type':article.get('article-type'),'language':language,
                    'article_versions':[etree.tostring(n,encoding='unicode') for n in descendants(meta,'article-version')],
                    'history_xml':[etree.tostring(n,encoding='unicode') for n in descendants(meta,'history')],
                    'authors_xml':[etree.tostring(n,encoding='unicode') for n in descendants(meta,'contrib-group')],
                    'related_articles':related,'permission_review':permission,
                    'conflict_statements_xml':[etree.tostring(n,encoding='unicode') for n in article.iter() if local(n)=='conflict-of-interest' or local(n)=='fn' and re.search('conflict|competing',n.get('fn-type',''),re.I)],
                    'canonical_url':'https://pmc.ncbi.nlm.nih.gov/articles/PMC'+row['pmcid']+'/',
                    'metadata_filter_eligible':not row['holds'],
                    'serialized_article_sha256':sha(etree.tostring(article)),
                    'serialization_caveat':'Serialized XML hash differs from original response bytes; source response hash is authoritative.'})
        records.append(row)
    token=listing.find('{'+OAI+'}resumptionToken')
    return records,text(token) if token is not None else '',response_date

def query(url):
    u=urlparse(url)
    if u.scheme!='https' or u.netloc!='pmc.ncbi.nlm.nih.gov' or u.path!='/api/oai/v1/mh/' or u.fragment:raise ValueError('wrong_PMC_endpoint')
    q=parse_qs(u.query,keep_blank_values=True)
    if any(len(v)!=1 for v in q.values()):raise ValueError('ambiguous_query')
    return {k:v[0] for k,v in q.items()}

def family_assign(rows):
    parent={r['pmcid']:r['pmcid'] for r in rows}
    def find(x):
        parent.setdefault(x,x)
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b);parent[max(a,b)]=min(a,b)
    keys={}
    for r in rows:
        for kind,values in r['identifiers'].items():
            for value in values:
                k=kind+':'+value
                if k in keys:union(r['pmcid'],keys[k])
                keys[k]=r['pmcid']
    for r in rows:
        for rel in r['related_articles']:
            attrs=rel['attributes'];href=attrs.get(XLINK,'')
            if attrs.get('ext-link-type')=='doi':
                target=keys.get('doi:'+re.sub(r'^https?://(?:dx\.)?doi\.org/','',href,flags=re.I).lower())
                if target:union(r['pmcid'],target)
            pmc=re.search(r'(?:^PMC|/PMC)([0-9]+)',href)
            if pmc:union(r['pmcid'],pmc.group(1))
    risk={find(r['pmcid']) for r in rows if any('retract' in x or 'correction' in x or 'version_status' in x for x in r['holds'])}
    for r in rows:
        r['family_id']='pmc:connected:'+find(r['pmcid'])
        r['family_definition']='Connected PMCID/PMID/DOI and related-article targets within frozen frame; unresolved outside-frame links remain held.'
        if find(r['pmcid']) in risk:r['holds'].append('connected_correction_retraction_family_requires_review')
        if r['related_articles']:r['holds'].append('related_article_link_requires_external_status_resolution')
        r['holds']=sorted(set(r['holds']));r['metadata_filter_eligible']=not r['holds']

def prepare(manifest_path,output):
    if manifest_path.stat().st_size>2*1024*1024:raise ValueError('manifest_byte_limit')
    m=json.loads(manifest_path.read_text())
    if m.get('metadata_prefix')!='pmc_fm' or not m.get('scope') or not m.get('responses'):raise ValueError('missing_explicit_frame_scope')
    for bound in ['from','until']:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',m['scope'].get(bound,'')):raise ValueError('explicit_day_scope_required')
        datetime.strptime(m['scope'][bound],'%Y-%m-%d')
    if m['scope']['from']>m['scope']['until']:raise ValueError('reversed_date_bounds')
    if len(m['responses'])>MAX_REQUESTS:raise ValueError('response_count_limit')
    output.mkdir(exist_ok=False,parents=True)
    rows=[];seen=set();nexttoken=None;bytes_read=0;sources=[]
    for i,ref in enumerate(m['responses']):
        q=query(ref['request_url'])
        if q.get('verb')!='ListRecords':raise ValueError('wrong_frame_verb')
        if i==0:
            if q!={'verb':'ListRecords','metadataPrefix':'pmc_fm','set':'pmc-open','from':m['scope']['from'],'until':m['scope']['until']}:
                raise ValueError('first_request_scope_mismatch')
        elif q!={'verb':'ListRecords','resumptionToken':nexttoken}:raise ValueError('broken_resumption_chain')
        p=(manifest_path.parent/ref['path']).resolve()
        if p.stat().st_size>MAX_RESPONSE_BYTES:raise ValueError('response_byte_limit')
        data=p.read_bytes();bytes_read+=len(data)
        if bytes_read>MAX_FRAME_BYTES:raise ValueError('aggregate_frame_input_limit')
        if sha(data)!=ref['sha256']:raise ValueError('source_response_hash_mismatch')
        rs,nexttoken,date=parse_response(data,ref['path'],q)
        for r in rs:
            if not m['scope']['from']<=r['oai_datestamp'][:10]<=m['scope']['until']:raise ValueError('record_outside_frozen_datestamp_scope')
            if r['pmcid'] in seen:raise ValueError('duplicate_article_or_moving_snapshot_requires_reconciliation')
            seen.add(r['pmcid']);rows.append(r)
            if len(rows)>MAX_ARTICLES:raise ValueError('1200_article_cap')
        sources.append({'path':ref['path'],'sha256':ref['sha256'],'request_url':ref['request_url'],'response_date':date,'next_resumption_token':nexttoken})
        if not nexttoken and i!=len(m['responses'])-1:raise ValueError('responses_after_terminal_cursor')
    if nexttoken:raise ValueError('incomplete_frame_resumption_token_remaining')
    family_assign(rows)
    content=''.join(json.dumps(r,sort_keys=True)+'\n' for r in sorted(rows,key=lambda x:int(x['pmcid']))).encode()
    source_content=json.dumps(sources,indent=2).encode()
    if len(content)+len(source_content)>MAX_OUTPUT_BYTES-16384:raise ValueError('aggregate_output_limit')
    (output/'frame.jsonl').write_bytes(content);(output/'source-responses.json').write_bytes(source_content)
    receipt={'status':'FROZEN_METADATA_FRAME_ONLY_NO_ADMISSION','frame_complete_for_declared_OAI_datestamp_scope':True,
             'scope':m['scope'],'rows':len(rows),'metadata_filter_eligible':sum(r['metadata_filter_eligible'] for r in rows),
             'frame_sha256':sha(content),'source_manifest_sha256':sha(manifest_path.read_bytes()),
             'source_responses_sha256':sha(source_content),'code_sha256':sha(Path(__file__).read_bytes()),
             'new_admitted_documents':0,'new_admitted_tokens':0,
             'limits':'OAI datestamps reflect repository changes, not publication-year sampling. A completed cursor chain is a bounded harvest, not an immutable PMC snapshot. Status updates outside frame must be reconciled before admission.'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def sample_frame(frame_path,receipt_path,k,seed):
    receipt=json.loads(receipt_path.read_text());data=frame_path.read_bytes()
    if receipt.get('status')!='FROZEN_METADATA_FRAME_ONLY_NO_ADMISSION' or not receipt.get('frame_complete_for_declared_OAI_datestamp_scope') or sha(data)!=receipt['frame_sha256']:raise ValueError('unfrozen_or_changed_frame')
    rows=[json.loads(l) for l in data.splitlines()]
    eligible=[r for r in rows if r['metadata_filter_eligible']]
    if not 1<=k<=min(len(eligible),MAX_ARTICLES):raise ValueError('invalid_sample_size')
    selected=sorted(eligible,key=lambda r:(sha((seed+'\n'+r['oai_identifier']).encode()),r['oai_identifier']))[:k]
    return {'scope':'Uniform deterministic article sample from exact eligible metadata frame; not fulltext quality acceptance','frame_sha256':receipt['frame_sha256'],'seed':seed,'N':len(eligible),'k':k,'inclusion_probability':{'numerator':k,'denominator':len(eligible)},'selected':[{'oai_identifier':r['oai_identifier'],'family_id':r['family_id'],'fulltext_request_url':BASE+'?'+urlencode({'verb':'GetRecord','metadataPrefix':'pmc','identifier':r['oai_identifier']})} for r in selected],'network_requests_executed':0}

class SerialRequestGuard:
    """Pure future-acquisition guard. Caller owns persistent ledger and I/O.

    No retries, sleeping, requests or scheduling occur here. Counter state must
    be restored from a parent-owned ledger across restarts before future use.
    """
    def __init__(self,planned_requests,charged_requests=0,charged_article_ids=(),last_start_utc=None):
        if type(planned_requests) is not int or not 1<=planned_requests<=MAX_REQUESTS:raise ValueError('request_cap')
        self.planned=planned_requests;self.count=charged_requests;self.articles=set(charged_article_ids)
        if not 0<=charged_requests<=planned_requests or len(self.articles)>MAX_ARTICLES:raise ValueError('invalid_persisted_budget')
        self.active=False;self.last_start=None;self.last_start_utc=last_start_utc
        if charged_requests and (last_start_utc is None or last_start_utc.tzinfo is None):raise ValueError('persisted_last_start_required')
    def start(self,now_monotonic,now_utc,article_id=None):
        if self.active:raise ValueError('concurrent_request_forbidden')
        if not isinstance(now_monotonic,(int,float)) or not math.isfinite(now_monotonic):raise ValueError('finite_monotonic_time_required')
        if self.count>=self.planned:raise ValueError('request_budget_exhausted')
        if self.last_start is not None and now_monotonic-self.last_start<1:raise ValueError('one_request_per_second_limit')
        if now_utc.tzinfo is None:raise ValueError('timezone_required')
        if self.last_start_utc is not None and (now_utc-self.last_start_utc).total_seconds()<1:raise ValueError('one_request_per_second_or_clock_regression')
        eastern=now_utc.astimezone(ZoneInfo('America/New_York'))
        if self.planned>100 and eastern.weekday()<5 and 5<=eastern.hour<21:raise ValueError('PMC_peak_hours_block')
        if article_id is not None and article_id not in self.articles and len(self.articles)>=MAX_ARTICLES:raise ValueError('1200_article_cap')
        self.count+=1;self.last_start=now_monotonic;self.last_start_utc=now_utc;self.active=True
        if article_id is not None:self.articles.add(article_id)
        return {'charged_requests':self.count,'charged_article_ids':sorted(self.articles),'last_start_utc':now_utc.isoformat(),'headers':{'Accept-Encoding':'gzip, deflate'},'requires_parent_write_ahead_ledger_before_IO':True}
    def finish(self):
        if not self.active:raise ValueError('no_active_request')
        self.active=False

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:print(json.dumps(prepare(a.manifest,a.output),indent=2))
    except Exception as exc:
        if a.output.exists():(a.output/'failure.json').write_text(json.dumps({'status':'TERMINAL_PREPARATION_FAILURE','reason':str(exc)[:2000],'training_admitted':False},indent=2)+'\n')
        raise

if __name__=='__main__':main()
