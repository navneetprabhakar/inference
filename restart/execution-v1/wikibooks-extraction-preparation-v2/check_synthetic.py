"""Exercise real extraction failure modes on synthetic fixtures only."""
import copy
import hashlib
import io
import json
import tarfile
import tempfile
from argparse import Namespace
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

import extract

HERE=Path(__file__).resolve().parent

def fixture(title='Example Book/Chapter One',page=1,html=None):
    return {'name':title,'identifier':page,'url':'https://en.wikibooks.org/wiki/'+quote(title.replace(' ','_'),safe='/'),
            'namespace':{'identifier':0},'is_part_of':{'identifier':'enwikibooks'},
            'version':{'identifier':100+page},
            'license':[{'identifier':'CC-BY-SA-4.0','url':'https://creativecommons.org/licenses/by-sa/4.0/'}],
            'article_body':{'html':html or '<html><body><h1>A chapter</h1><p>'+('This synthetic paragraph explains a useful idea with enough detail to read independently. '*4)+'</p></body></html>'}}

def expect_error(f,label):
    try:f()
    except (ValueError,TypeError,AttributeError):return
    raise AssertionError(label)

def main():
    cases=[]
    a=fixture();d=extract.extract_record(a)
    assert not d['holds'] and d['original_html']==a['article_body']['html'] and d['page_id']==1 and d['revision_id']==101
    cases.append('preserve_ids_license_original_html_and_hash')
    b=fixture('Example Book/Chapter Two',2)
    assert d['family_id']==extract.extract_record(b)['family_id']==extract.extract_record(fixture('Example Book',3))['family_id']
    cases.append('root_and_subpages_share_whole_book_family')
    m=fixture(html='<p>Equation: <math alttext="x^2"><semantics><mi>x</mi></semantics></math></p>')
    md=extract.extract_record(m)
    assert 'math_requires_lossless_representation' in md['holds'] and 'FORMULA REQUIRES REVIEW: x^2' in md['text']
    cases.append('math_not_silently_erased')
    t=fixture(html='<p>See the following table.</p><table><tr><th>Food</th><th>Count</th></tr><tr><td>Apples</td><td>2</td></tr></table>')
    td=extract.extract_record(t)
    assert 'table_structure_requires_review' in td['holds'] and 'Apples' in td['text']
    cases.append('table_preserved_and_held')
    for html,reason in [('<p>{{unexpanded}}</p>','unexpanded_markup'),('<span typeof="mw:Error">Failed expansion</span>','render_or_template_error'),('<p>See figure below</p><img src="image.svg"/>','visual_dependency'),('<p><a class="new" href="/wiki/Template:Missing">Template missing</a></p>','missing_link_or_template_dependency')]:
        assert reason in extract.extract_record(fixture(html=html))['holds']
        cases.append(reason)
    nav=fixture(html='<nav>UNWANTED NAV</nav><span class="mw-editsection">EDIT</span>'+a['article_body']['html'])
    nd=extract.extract_record(nav)
    assert 'UNWANTED NAV' not in nd['text'] and 'EDIT' not in nd['text']
    cases.append('navigation_removed_without_removing_lesson')
    trans=fixture(html='<section typeof="mw:Transclusion"><p>'+('Rendered template lesson prose. '*12)+'</p></section>')
    assert 'Rendered template lesson prose' in extract.extract_record(trans)['text']
    cases.append('rendered_transclusions_not_blanket_deleted')
    assert 'print_or_aggregate_page' in extract.extract_record(fixture('Example Book/Print version',4))['holds']
    cases.append('print_aggregate_held_not_combined_with_chapters')
    for key in ['license','version','identifier']:
        broken=copy.deepcopy(a);del broken[key]
        expect_error(lambda:extract.extract_record(broken),'missing '+key)
    cases.append('unknown_or_missing_schema_fails_closed')
    wrong=copy.deepcopy(a);wrong['url']='https://en.wikipedia.org/wiki/Example'
    expect_error(lambda:extract.extract_record(wrong),'wrong project')
    cases.append('project_boundary_enforced')
    with tempfile.TemporaryDirectory(dir=HERE) as tmp:
        p=Path(tmp);data=p/'fixture.ndjson'
        # Parent contains same substantive paragraph as chapter: exactly one
        # survives without a detected hold, irrespective of archive order.
        records=[fixture('Example Book',10),fixture('Example Book/Chapter One',11),fixture('Other Book/Chapter One',12)]
        data.write_text(''.join(json.dumps(r)+'\n' for r in records))
        args=Namespace(input=data,sha256=extract.file_sha(data),output=p/'output',max_pages=10,max_line_bytes=1024*1024,max_decompressed_bytes=4*1024*1024,max_output_bytes=16*1024*1024,prefix_discovery=False)
        receipt=extract.run(args)
        rows=[json.loads(l) for l in (p/'output/extracted.jsonl').read_text().splitlines()]
        assert len(rows)==3 and sum(not x['holds'] for x in rows)==2
        assert next(x for x in rows if x['page_id']==10)['overlap_blocks'][0]['owner_page_id']==11
        assert all(x['training_admitted'] is False for x in rows)
        cases.append('chapter_first_cross_page_overlap_hold_and_no_admission')
        rev=p/'reverse.ndjson';rev.write_text(''.join(json.dumps(r)+'\n' for r in reversed(records)))
        args.input=rev;args.sha256=extract.file_sha(rev);args.output=p/'reverse-output';extract.run(args)
        reverse=[json.loads(l) for l in (args.output/'extracted.jsonl').read_text().splitlines()]
        assert [(x['page_id'],x['holds']) for x in rows]==[(x['page_id'],x['holds']) for x in reverse]
        cases.append('overlap_outcome_independent_of_source_order')
        cases.append('source_record_bytes_and_line_hashes_preserved')
        assert (p/'output/source-records.jsonl').read_bytes()==data.read_bytes()
        expect_error(lambda:list(extract.stream_lines(data,20,100000)),'record cap')
        expect_error(lambda:list(extract.stream_lines(data,100000,20)),'decoded cap')
        cases.append('line_and_decoded_read_limits_enforced')
        archive=p/'fixture.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            payload=data.read_bytes();info=tarfile.TarInfo('../../not-extracted.ndjson');info.size=len(payload);tar.addfile(info,io.BytesIO(payload))
        assert len(list(extract.stream_lines(archive,100000,100000)))==3
        assert not (p.parent/'not-extracted.ndjson').exists()
        cases.append('tar_stream_does_not_extract_paths')
        archive2=p/'bad.tar.gz'
        with tarfile.open(archive2,'w:gz') as tar:
            info=tarfile.TarInfo('evil');info.type=tarfile.SYMTYPE;info.linkname='/tmp/evil';tar.addfile(info)
        expect_error(lambda:list(extract.stream_lines(archive2,100000,100000)),'symlink cap')
        cases.append('tar_nonregular_members_rejected')
        expect_error(lambda:list(extract.stream_lines(archive,100000,1000)),'tar full decoded cap')
        cases.append('tar_headers_padding_and_member_sizes_bounded')
        # A huge declared member may contain a bounded readable prefix. Its
        # unavailable tail must not be consumed or skipped when page cap hits.
        import gzip
        truncated=p/'large-declared.tar.gz'
        info=tarfile.TarInfo('large.ndjson');info.size=2*1024**3
        first=(json.dumps(fixture())+'\n').encode()
        with gzip.open(truncated,'wb') as f:f.write(info.tobuf());f.write(first+b' '*12000)
        args.input=truncated;args.sha256=extract.file_sha(truncated);args.output=p/'prefix';args.prefix_discovery=True;args.max_pages=1;args.max_decompressed_bytes=64*1024
        prefix=extract.run(args)
        assert prefix['counts']['pages']==1 and prefix['prefix_limit_reached'] and not prefix['full_archive_processed']
        cases.append('explicit_prefix_stops_before_large_unread_member_tail')
        expect_error(lambda:list(extract.stream_lines(truncated,100000,1000,True)),'prefix actual decoded byte cap')
        cases.append('large_declared_prefix_still_enforces_actual_decoded_cap')
        args.prefix_discovery=False;args.max_pages=10;args.max_decompressed_bytes=4*1024*1024
        budget_dir=p/'budget';budget_dir.mkdir();(budget_dir/'existing').write_bytes(b'a'*30000)
        budget=extract.OutputBudget(budget_dir,65536,0)
        expect_error(lambda:budget.check(30000),'aggregate output cap')
        cases.append('aggregate_output_counts_all_files_including_spool')
        budget.free_floor=1
        with patch('extract.shutil.disk_usage',return_value=Namespace(free=0)):
            expect_error(lambda:budget.check(),'free disk floor')
        cases.append('disk_floor_guard')
        bad=p/'bad.ndjson';bad.write_text(json.dumps({'unknown':'schema'})+'\n')
        args.input=bad;args.sha256=extract.file_sha(bad);args.output=p/'schema-failure'
        expect_error(lambda:extract.run(args),'schema failure diagnostic')
        assert json.loads((args.output/'failure.json').read_text())['status']=='TERMINAL_EXTRACTION_FAILURE_NO_ADMISSION'
        cases.append('unknown_schema_retains_terminal_failure_diagnostic')
        args.input=data;args.sha256=extract.file_sha(data);args.output=p/'space-failure'
        with patch('extract.shutil.disk_usage',return_value=Namespace(free=35_000_000_000)):
            expect_error(lambda:extract.run(args),'weights reservation')
        assert 'weights' in json.loads((args.output/'failure.json').read_text())['reason']
        cases.append('weights_reservation_preflight_and_diagnostic')
    result={'status':'PASS','scope':'Synthetic HTML/schema/container fixtures only; no real corpus processed or quality claim.','cases':cases,'case_count':len(cases),'extractor_sha256':extract.file_sha(HERE/'extract.py'),'test_sha256':extract.file_sha(Path(__file__))}
    (HERE/'synthetic-check-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
