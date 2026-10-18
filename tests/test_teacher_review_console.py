"""Synthetic teacher review UI/export integration; no real human decisions."""
from copy import deepcopy
from dataclasses import replace
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from slm.data.review import prepare,release,training_examples
from slm.data.review_console import render,apply_patch,teacher_contract
from slm.data.curation import curate
from slm.data.schema import digest
from slm.teacher.bridge import snapshot,source_example,REVIEW_FIELDS
from slm.teacher.cli import PROMPT_V1
from test_teacher_bridge import fixture as teacher_fixture,source_descriptor,record_file
from test_review_console import patch,write
from test_review import approved_packet


def fixture(tmp_path):
    source,descriptor=source_descriptor(tmp_path,'fixture')
    source=replace(source,license_id='fixture');d=json.loads(descriptor.read_text());d['license_id']='fixture';write(descriptor,d)
    for index in range(20):
        def mutate(s):s['scenario_id']='synthetic-teacher-console-'+str(index)
        record,j=teacher_fixture(tmp_path,version=PROMPT_V1,mutate=mutate)
        e=source_example(record,j.path,source);rows,_=curate([e],{source.source_id:source})
        if rows[0].split=='train':break
    assert rows[0].split=='train'
    snapshot([record_file(tmp_path,record)],j.path,descriptor,tmp_path/'sample')
    prepare(tmp_path/'sample',tmp_path/'base.json');base=json.loads((tmp_path/'base.json').read_text())
    return base


def payload(path):
    text=Path(path).read_text();script=text.split('<script>')[1].split('</script>')[0]
    encoded=script.split("atob('")[1].split("')")[0];return json.loads(base64.b64decode(encoded))


def reviewed(base):
    value=deepcopy(base);value.update(reviewer='Navneet Prabhakar',human_attestation=True)
    for src in value['source_reviews'].values():src.update(approved=True,terms_reviewed=True,allowed_categories=['sfw'],evidence_note='Synthetic fixture only.')
    for e in value['examples'].values():
        e['decision'].update(approved=True,english_verified=True,privacy_verified=True,quality_verified=True,
            content_category='sfw',upstream_partition='train',partition_evidence='Synthetic train record.',teacher_review={k:True for k in REVIEW_FIELDS})
    return value


def test_teacher_render_embeds_pinned_evidence_contract_and_pending_gates(tmp_path):
    base=fixture(tmp_path);before=(tmp_path/'base.json').read_bytes();r=render(tmp_path/'sample',tmp_path/'base.json',tmp_path/'view.html')
    data=payload(tmp_path/'view.html');assert r['pinned_evidence_sources']==1
    key=next(iter(base['examples']));assert data['teacher_contract'][key]['fields']==list(REVIEW_FIELDS)
    assert data['evidence']['fixture']['license']==(tmp_path/'terms.txt').read_text()
    assert data['packet']['human_attestation'] is False and all(v is None for v in data['packet']['examples'][key]['decision']['teacher_review'].values())
    assert (tmp_path/'base.json').read_bytes()==before


@pytest.mark.parametrize('defect',['missing_object','missing_field','unknown_field','integer','string','null_object','category','record_injection'])
def test_teacher_patch_shape_cannot_drop_gates_even_for_drafts(tmp_path,defect):
    base=fixture(tmp_path);p=patch(base);entry=next(iter(p['examples'].values()))
    if defect=='missing_object':entry.pop('teacher_review')
    elif defect=='missing_field':entry['teacher_review'].pop(REVIEW_FIELDS[0])
    elif defect=='unknown_field':entry['teacher_review']['extra']=True
    elif defect=='integer':entry['teacher_review'][REVIEW_FIELDS[0]]=1
    elif defect=='string':entry['teacher_review'][REVIEW_FIELDS[0]]='yes'
    elif defect=='null_object':entry['teacher_review']=None
    elif defect=='category':entry['content_category']='adult_topic'
    else:entry['record']={}
    write(tmp_path/'patch.json',p)
    with pytest.raises(ValueError):apply_patch(tmp_path/'sample',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'out.json')
    assert not (tmp_path/'out.json').exists()


@pytest.mark.parametrize('state',[None,False])
def test_attested_generic_approval_or_false_teacher_gate_cannot_materialize(tmp_path,state):
    base=fixture(tmp_path);value=reviewed(base);entry=next(iter(value['examples'].values()))
    entry['decision']['teacher_review'][REVIEW_FIELDS[0]]=state
    write(tmp_path/'patch.json',patch(base,value,True))
    with pytest.raises(ValueError,match='Explicit teacher'):apply_patch(tmp_path/'sample',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'out.json')
    assert not (tmp_path/'out.json').exists()


def test_valid_teacher_patch_preserves_receipt_then_existing_release_checks_it(tmp_path):
    base=fixture(tmp_path);write(tmp_path/'patch.json',patch(base,reviewed(base),True))
    r=apply_patch(tmp_path/'sample',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'reviewed.json');assert not r['training_release_created']
    value=json.loads((tmp_path/'reviewed.json').read_text());key=next(iter(base['examples']))
    assert value['examples'][key]['record']==base['examples'][key]['record']
    release(tmp_path/'sample',tmp_path/'reviewed.json',tmp_path/'released')
    rows=list(training_examples(tmp_path/'released'));assert len(rows)==1 and rows[0]['validation_results']['teacher_bridge']['training_eligible'] is False


def test_teacher_draft_can_save_decisions_but_cannot_release(tmp_path):
    base=fixture(tmp_path);write(tmp_path/'patch.json',patch(base,reviewed(base),False))
    apply_patch(tmp_path/'sample',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'draft.json')
    with pytest.raises(ValueError,match='attestation'):release(tmp_path/'sample',tmp_path/'draft.json',tmp_path/'released')


@pytest.mark.parametrize('defect',['missing','changed'])
def test_teacher_source_evidence_cannot_be_omitted_or_laundered(tmp_path,defect):
    fixture(tmp_path);p=tmp_path/'sample/source-license.txt'
    if defect=='missing':p.unlink()
    else:p.write_text('Changed evidence')
    # Even rehashing the outer manifest/packet cannot replace the pinned Source evidence.
    manifest=json.loads((tmp_path/'sample/manifest.json').read_text())
    if defect=='missing':manifest['files'].pop(p.name)
    else:manifest['files'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    write(tmp_path/'sample/manifest.json',manifest);base=json.loads((tmp_path/'base.json').read_text());base['dataset_manifest_sha256']=hashlib.sha256((tmp_path/'sample/manifest.json').read_bytes()).hexdigest();write(tmp_path/'base.json',base)
    with pytest.raises(ValueError,match='evidence'):render(tmp_path/'sample',tmp_path/'base.json',tmp_path/'out.html')
    assert not (tmp_path/'out.html').exists()


def test_teacher_dom_export_flows_through_python_publisher(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Optional Node.js unavailable')
    base=fixture(tmp_path);render(tmp_path/'sample',tmp_path/'base.json',tmp_path/'view.html')
    subprocess.run([node,'scripts/check-review-console.mjs',str(tmp_path/'view.html'),str(tmp_path/'patch.json'),str(tmp_path/'dom.json')],check=True,capture_output=True)
    report=json.loads((tmp_path/'dom.json').read_text())
    assert report['teacher_fixture'] and report['teacher_missing_false_gates_refused'] and report['controlled_teacher_category_locked']
    assert not report['browser_runtime_verified'] and not report['real_human_review']
    apply_patch(tmp_path/'sample',tmp_path/'base.json',tmp_path/'patch.json',tmp_path/'reviewed.json')
    release(tmp_path/'sample',tmp_path/'reviewed.json',tmp_path/'released');assert len(list(training_examples(tmp_path/'released')))==1
