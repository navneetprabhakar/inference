"""Offline decisions cannot rewrite frozen data or bypass publication gates."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from slm.data.review import prepare,release,training_examples
from slm.data.review_console import render,apply_patch,evidence,SOURCE_FIELDS
from slm.data.schema import digest
from test_review import fixture_snapshot,approved_packet


def fixture(tmp_path):
    fixture_snapshot(tmp_path/'raw');prepare(tmp_path/'raw',tmp_path/'base.json',30)
    return json.loads((tmp_path/'base.json').read_text())


def patch(base,reviewed=None,attest=False):
    reviewed=base if reviewed is None else reviewed
    return {'version':1,'review_packet_sha256':digest(base),'reviewer':'Navneet Prabhakar','human_attestation':attest,
        'sources':{k:{f:v[f] for f in SOURCE_FIELDS} for k,v in reviewed['source_reviews'].items()},
        'examples':{k:deepcopy(v['decision']) for k,v in reviewed['examples'].items()}}


def write(path,value):path.write_text(json.dumps(value))


def test_pending_console_is_offline_escaped_and_does_not_approve_or_modify_packet(tmp_path):
    base=fixture(tmp_path);before=(tmp_path/'base.json').read_bytes()
    result=render(tmp_path/'raw',tmp_path/'base.json',tmp_path/'review.html')
    html=(tmp_path/'review.html').read_text();assert (tmp_path/'base.json').read_bytes()==before
    assert result['human_attestation_changed'] is False and html.count('<script>')==1
    script=html.split('<script>')[1].split('</script>')[0];style=html.split('<style>')[1].split('</style>')[0]
    for text in (script,style):assert 'sha256-'+base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() in html
    assert "connect-src 'none'" in html and "$('attest').checked=false" in script
    assert 'Question 0' not in html and 'innerHTML' not in script
    with pytest.raises(FileExistsError):render(tmp_path/'raw',tmp_path/'base.json',tmp_path/'review.html')


def test_valid_human_patch_materializes_without_publishing_then_existing_release_preserves_holdouts(tmp_path):
    base=fixture(tmp_path);write(tmp_path/'human.json',base);reviewed=approved_packet(tmp_path/'human.json')
    write(tmp_path/'patch.json',patch(base,reviewed,True))
    result=apply_patch(tmp_path/'raw',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'reviewed.json')
    assert not result['training_release_created'] and json.loads((tmp_path/'base.json').read_text())==base
    release(tmp_path/'raw',tmp_path/'reviewed.json',tmp_path/'released')
    rows=list(training_examples(tmp_path/'released'));assert rows and all(v['split']=='train' for v in rows)
    assert not {'fixture:0','fixture:1','fixture:2'}&{v['example_id'] for v in rows}


def test_draft_patch_cannot_release_training_data(tmp_path):
    base=fixture(tmp_path);write(tmp_path/'patch.json',patch(base))
    result=apply_patch(tmp_path/'raw',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'draft.json')
    assert result['human_attestation'] is False and result['approved_decisions']==0
    with pytest.raises(ValueError,match='attestation'):release(tmp_path/'raw',tmp_path/'draft.json',tmp_path/'release')
    assert not (tmp_path/'release').exists()


@pytest.mark.parametrize('defect',['record_injection','source_injection','stale','missing_example','integer_boolean','category','incomplete_attestation'])
def test_bad_patch_is_refused_without_output(tmp_path,defect):
    base=fixture(tmp_path);p=patch(base);first=next(iter(p['examples']))
    if defect=='record_injection':p['examples'][first]['record']={'messages':[]}
    elif defect=='source_injection':p['sources']['fixture']['source_record']={'revision':'changed'}
    elif defect=='stale':p['review_packet_sha256']='0'*64
    elif defect=='missing_example':p['examples'].pop(first)
    elif defect=='integer_boolean':p['examples'][first]['approved']=1
    elif defect=='category':p['sources']['fixture']['allowed_categories']=['unreviewed']
    else:p['human_attestation']=True;p['examples'][first]['approved']=True
    write(tmp_path/'patch.json',p)
    with pytest.raises(ValueError):apply_patch(tmp_path/'raw',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'output.json')
    assert not (tmp_path/'output.json').exists()


def test_rehashed_base_record_still_must_match_frozen_input(tmp_path):
    base=fixture(tmp_path);first=next(iter(base['examples']));entry=base['examples'][first]
    entry['record']['messages'][0]['content']='</script><script>untrusted()</script>';entry['record_sha256']=digest(entry['record'])
    write(tmp_path/'base.json',base)
    with pytest.raises(ValueError,match='identity'):render(tmp_path/'raw',tmp_path/'base.json',tmp_path/'bad.html')
    assert not (tmp_path/'bad.html').exists()


def test_source_evidence_is_hashed_and_rendered_as_text(tmp_path):
    root=tmp_path/'evidence/source';root.mkdir(parents=True)
    card=b'</script><script>untrusted()</script>';license=b'Synthetic license evidence only.'
    source={'source_id':'fixture','revision':'a'*40,'card_sha256':hashlib.sha256(card).hexdigest(),'license_text_sha256':hashlib.sha256(license).hexdigest()}
    write(root/'source.json',source);(root/'card.txt').write_bytes(card);(root/'license.txt').write_bytes(license)
    packet={'source_reviews':{'fixture':{'source_record':source}}}
    assert evidence(packet,tmp_path)['fixture']['card']==card.decode()
    (root/'card.txt').write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum'):evidence(packet,tmp_path)


def test_duplicate_json_fields_are_rejected_before_materialization(tmp_path):
    base=fixture(tmp_path);p=json.dumps(patch(base));p=p.replace('"version": 1','"version": 1, "version": 1')
    (tmp_path/'patch.json').write_text(p)
    with pytest.raises(ValueError,match='Duplicate'):apply_patch(tmp_path/'raw',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'output')


def test_source_script_markup_remains_encoded_in_the_html_payload(tmp_path):
    injection='</script><script>document.title="injected"</script>'
    fixture_snapshot(tmp_path/'raw',content_prefix=injection);prepare(tmp_path/'raw',tmp_path/'packet',6)
    render(tmp_path/'raw',tmp_path/'packet',tmp_path/'view.html');html=(tmp_path/'view.html').read_text()
    assert injection not in html and html.count('<script>')==1


def test_dom_simulation_exports_synthetic_decisions_that_existing_python_checks_accept(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Optional Node.js DOM unit simulation unavailable')
    fixture(tmp_path);render(tmp_path/'raw',tmp_path/'base.json',tmp_path/'view.html')
    subprocess.run([node,'scripts/check-review-console.mjs',str(tmp_path/'view.html'),str(tmp_path/'patch.json'),str(tmp_path/'dom.json')],check=True,capture_output=True)
    report=json.loads((tmp_path/'dom.json').read_text());assert report['synthetic_only'] and not report['browser_runtime_verified']
    apply_patch(tmp_path/'raw',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'review.json')
    release(tmp_path/'raw',tmp_path/'review.json',tmp_path/'release')
    items=list(training_examples(tmp_path/'release'));assert len(items)==1 and items[0]['split']=='train'
