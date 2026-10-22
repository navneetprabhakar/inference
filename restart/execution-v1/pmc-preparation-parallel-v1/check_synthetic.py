"""Synthetic OAI/JATS fixtures; no assertion of observed live record shape."""
import copy
import json
import tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path

import prepare

HERE=Path(__file__).resolve().parent
BY='https://creativecommons.org/licenses/by/4.0/'

def record(pmc=1,license_url=BY,extra='',attrs='',license_words='Creative Commons Attribution',doi=None):
    return f'''<record><header><identifier>oai:pubmedcentral.nih.gov:{pmc}</identifier><datestamp>2026-01-02</datestamp><setSpec>pmc-open</setSpec></header><metadata><article xmlns="" xmlns:xlink="http://www.w3.org/1999/xlink" xml:lang="en" article-type="research-article" {attrs}><front><journal-meta><journal-title-group><journal-title>Fixture journal</journal-title></journal-title-group></journal-meta><article-meta><article-id pub-id-type="pmc">{pmc}</article-id><article-id pub-id-type="doi">{doi or '10.0000/fixture.'+str(pmc)}</article-id><title-group><article-title>Fixture research exposition</article-title></title-group><pub-date pub-type="epub"><year>2025</year></pub-date><permissions><license xlink:href="{license_url}"><license-p>{license_words}</license-p></license></permissions>{extra}</article-meta></front><back><fn fn-type="conflict"><p>No conflicts declared in fixture.</p></fn></back></article></metadata></record>'''

def envelope(records,token=''):
    return ('<OAI-PMH xmlns="'+prepare.OAI+'"><responseDate>2026-01-03T00:00:00Z</responseDate><request verb="ListRecords" metadataPrefix="pmc_fm" set="pmc-open" from="2026-01-01" until="2026-01-03">'+prepare.BASE+'</request><ListRecords>'+''.join(records)+'<resumptionToken>'+token+'</resumptionToken></ListRecords></OAI-PMH>').encode()

def fail(f):
    try:f()
    except (ValueError,KeyError):return
    raise AssertionError('expected refusal')

def main():
    cases=[]
    rows,token,date=prepare.parse_response(envelope([record()]),'synthetic.xml')
    assert rows[0]['metadata_filter_eligible'] and rows[0]['pmcid']=='1' and rows[0]['permission_review']['allowlisted_license_uris']==[BY]
    assert rows[0]['publication_dates'] and rows[0]['conflict_statements_xml'] and rows[0]['source_response_sha256']
    cases.append('explicit_CC_BY_metadata_candidate_preserves_identity_dates_permissions_conflicts')
    zero='https://creativecommons.org/publicdomain/zero/1.0/'
    assert prepare.parse_response(envelope([record(license_url=zero)]),'s')[0][0]['metadata_filter_eligible']
    cases.append('explicit_CC0_allowed')
    for bad in ['https://creativecommons.org/licenses/by-nc/4.0/','https://creativecommons.org/licenses/by-nd/4.0/','https://creativecommons.org/licenses/by-sa/4.0/','https://creativecommons.org/licenses/by/4.0/us/','https://creativecommons.org.evil.invalid/licenses/by/4.0/','https://example.org/open-access']:
        assert not prepare.parse_response(envelope([record(license_url=bad)]),'s')[0][0]['metadata_filter_eligible']
    cases.append('NC_ND_SA_ported_unknown_and_host_spoof_rejected')
    assert not prepare.parse_response(envelope([record(license_words='For non-commercial use only')]),'s')[0][0]['metadata_filter_eligible']
    cases.append('URI_and_restrictive_wording_conflict_held')
    temporal=record().replace('<license xlink:href=','<license start_date="2099-01-01" xlink:href=')
    assert not prepare.parse_response(envelope([temporal]),'s')[0][0]['metadata_filter_eligible']
    cases.append('time_qualified_license_held')
    fail(lambda:prepare.parse_response(envelope([record()]),'s',{'verb':'GetRecord'}))
    cases.append('response_request_binding_must_match_manifest')
    fig=record().replace('</article>','<body><fig><permissions><copyright-statement>Third party</copyright-statement></permissions></fig></body></article>')
    assert 'object_or_subarticle_permissions_need_review' in prepare.parse_response(envelope([fig]),'s')[0][0]['holds']
    cases.append('object_permissions_do_not_inherit_article_license')
    deleted='<record><header status="deleted"><identifier>oai:pubmedcentral.nih.gov:8</identifier><datestamp>2026-01-02</datestamp></header></record>'
    assert not prepare.parse_response(envelope([deleted]),'s')[0][0]['metadata_filter_eligible']
    cases.append('deleted_records_retained_excluded')
    fail(lambda:prepare.parse_response(b'<!DOCTYPE article [<!ENTITY evil SYSTEM "file:///etc/passwd">]>'+envelope([record()]),'s'))
    cases.append('DTD_external_entity_rejected')
    fail(lambda:prepare.parse_response(envelope([record()]).replace(b'<article xmlns=""',b'<unexpected xmlns=""').replace(b'</article>',b'</unexpected>'),'s'))
    cases.append('unknown_metadata_schema_fails_closed')
    fail(lambda:prepare.parse_response(envelope([record()]).replace(b'pub-id-type="pmc">1',b'pub-id-type="pmc">2'),'s'))
    cases.append('header_PMCID_conflict_refused')
    related='<related-article related-article-type="retracted-article" ext-link-type="doi" xlink:href="10.0000/fixture.2"/>'
    family=prepare.parse_response(envelope([record(extra=related),record(2)]),'s')[0];prepare.family_assign(family)
    assert family[0]['family_id']==family[1]['family_id'] and all(not x['metadata_filter_eligible'] for x in family)
    cases.append('related_retraction_propagates_to_target_family')
    family=prepare.parse_response(envelope([record(1,doi='10.0000/shared'),record(2,doi='10.0000/shared')]),'s')[0];prepare.family_assign(family)
    assert family[0]['family_id']==family[1]['family_id']
    cases.append('shared_DOI_unifies_version_family')
    with tempfile.TemporaryDirectory(dir=HERE) as temp:
        p=Path(temp);r=p/'response.xml';r.write_bytes(envelope([record(),record(2)]))
        url=prepare.BASE+'?verb=ListRecords&metadataPrefix=pmc_fm&set=pmc-open&from=2026-01-01&until=2026-01-03'
        manifest={'metadata_prefix':'pmc_fm','scope':{'from':'2026-01-01','until':'2026-01-03','interpretation':'repository OAI datestamp, not publication date'},'responses':[{'path':'response.xml','sha256':prepare.sha(r.read_bytes()),'request_url':url}]}
        m=p/'manifest.json';m.write_text(json.dumps(manifest));out=p/'prepared'
        receipt=prepare.prepare(m,out);assert receipt['rows']==2 and receipt['metadata_filter_eligible']==2
        sample=prepare.sample_frame(out/'frame.jsonl',out/'receipt.json',1,'fixture-seed')
        assert sample['N']==2 and sample['inclusion_probability']=={'numerator':1,'denominator':2} and sample['network_requests_executed']==0
        cases.append('closed_frame_then_reproducible_probability_sample_without_network')
        sample2=prepare.sample_frame(out/'frame.jsonl',out/'receipt.json',1,'fixture-seed');assert sample==sample2
        cases.append('deterministic_sample_exact_frame_hash_bound')
        with (out/'frame.jsonl').open('a') as f:f.write(' ')
        fail(lambda:prepare.sample_frame(out/'frame.jsonl',out/'receipt.json',1,'fixture-seed'))
        cases.append('changed_frame_refuses_sampling')
        r.write_bytes(envelope([record()],token='next-token'));manifest['responses'][0]['sha256']=prepare.sha(r.read_bytes());m.write_text(json.dumps(manifest))
        fail(lambda:prepare.prepare(m,p/'incomplete'))
        cases.append('nonterminal_resumption_token_prevents_frozen_frame')
        r.write_bytes(envelope([record(),record()]));manifest['responses'][0]['sha256']=prepare.sha(r.read_bytes());m.write_text(json.dumps(manifest))
        fail(lambda:prepare.prepare(m,p/'duplicate'))
        cases.append('duplicate_or_moving_article_versions_require_reconciliation')
        r.write_bytes(envelope([record()]).replace(b'2026-01-02</datestamp>',b'2026-02-02</datestamp>'));manifest['responses'][0]['sha256']=prepare.sha(r.read_bytes());m.write_text(json.dumps(manifest))
        fail(lambda:prepare.prepare(m,p/'out-of-scope'))
        cases.append('record_datestamp_bound_enforced')
    # All timing is simulated; the guard does no sleeping or I/O.
    t=datetime(2026,1,4,0,0,tzinfo=timezone.utc) # weekend US Eastern
    guard=prepare.SerialRequestGuard(1200)
    state=guard.start(0,t,'PMC1');fail(lambda:guard.start(2,t+timedelta(seconds=2),'PMC2'));guard.finish()
    cases.append('concurrent_requests_denied')
    fail(lambda:guard.start(.5,t+timedelta(seconds=.5),'PMC2'))
    fail(lambda:guard.start(float('nan'),t+timedelta(seconds=2),'PMC2'))
    cases.append('one_rps_and_nonfinite_timing_denied')
    guard.start(1,t+timedelta(seconds=1),'PMC2');guard.finish()
    cases.append('serial_one_rps_permitted')
    peak=datetime(2026,1,5,15,0,tzinfo=timezone.utc)
    fail(lambda:prepare.SerialRequestGuard(101).start(0,peak,'PMC1'))
    cases.append('planned_over100_peak_hours_denied')
    restored=prepare.SerialRequestGuard(1200,1,['PMC1'],t)
    fail(lambda:restored.start(0,t+timedelta(seconds=.5),'PMC2'))
    fail(lambda:prepare.SerialRequestGuard(1200,1,['PMC1']))
    cases.append('restart_requires_persisted_last_request_and_spacing')
    full=prepare.SerialRequestGuard(2400,1200,[str(i) for i in range(1200)],t)
    fail(lambda:full.start(2,t+timedelta(seconds=2),'new'))
    cases.append('1200_unique_article_cap')
    result={'status':'PASS','case_count':len(cases),'cases':cases,'scope':'Synthetic OAI/JATS/clock fixtures only; no actual PMC response, requests, downloads, admissions or model operations.','code_sha256':prepare.sha((HERE/'prepare.py').read_bytes()),'checks_sha256':prepare.sha(Path(__file__).read_bytes())}
    (HERE/'synthetic-check-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
