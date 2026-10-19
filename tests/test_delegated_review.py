"""Delegated authority must never become human attestation or corpus approval."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
import pytest
from test_review import fixture_snapshot, approved_packet
from slm.data.review import prepare,release,training_examples,check_packet
from slm.data.review_stream import export_packet,release as stream_release,open_checked,DEFAULT_LIMITS


def delegated_packet(tmp_path):
    fixture_snapshot(tmp_path/'input');p=tmp_path/'packet.json'
    prepare(tmp_path/'input',p,30);packet=approved_packet(p)
    packet.update(review_mode='delegated_expert',reviewer='delegated_expert',human_attestation=False,
        review_authorization=dict(version=1,authorized_by='Navneet Prabhakar',instruction='Review these sampled rows as expert.',
            scope='explicit_rows_only',dataset_manifest_sha256=packet['dataset_manifest_sha256'],recorded_on='2026-10-19'))
    p.write_text(json.dumps(packet));return p,packet


@pytest.mark.parametrize('streamed',[False,True])
def test_delegated_release_keeps_mode_and_checks_content(tmp_path,streamed):
    p,packet=delegated_packet(tmp_path)
    packet['examples']['fixture:3']['decision']['approved']=False
    p.write_text(json.dumps(packet))
    if streamed:
        export_packet(p,tmp_path/'export')
        header=json.loads((tmp_path/'export/header.json').read_text())
        assert header['human_attestation'] is False and header['review_authorization']==packet['review_authorization']
        stream_release(tmp_path/'input',tmp_path/'export',tmp_path/'out',limits=DEFAULT_LIMITS)
    else:release(tmp_path/'input',p,tmp_path/'out')
    rows=list(training_examples(tmp_path/'out'))
    assert rows and all(r['validation_results']['quality_review']=='delegated_expert_reviewed' for r in rows)
    assert all('human_review' not in r['validation_results'] and 'delegated_expert_review' in r['validation_results'] for r in rows)
    assert not {'fixture:0','fixture:1','fixture:3'}&{r['example_id'] for r in rows}
    with open_checked(tmp_path/'out') as checked:assert list(checked.values())==rows


@pytest.mark.parametrize('defect',['missing','false_human','reviewer','scope','dataset','instruction','author','unknown','downgrade','integer_attestation','extra_field'])
def test_delegated_authority_cannot_be_missing_misbound_or_laundered(tmp_path,defect):
    p,packet=delegated_packet(tmp_path);bad=deepcopy(packet)
    if defect=='missing':bad.pop('review_authorization')
    elif defect=='false_human':bad['human_attestation']=True
    elif defect=='reviewer':bad['reviewer']='Navneet Prabhakar'
    elif defect=='scope':bad['review_authorization']['scope']='whole_corpus'
    elif defect=='dataset':bad['review_authorization']['dataset_manifest_sha256']='f'*64
    elif defect=='instruction':bad['review_authorization']['instruction']=' '
    elif defect=='author':bad['review_authorization']['authorized_by']='unknown'
    elif defect=='unknown':bad['review_mode']='automatic'
    elif defect=='downgrade':bad.pop('review_mode');bad.update(reviewer='Navneet Prabhakar',human_attestation=True)
    elif defect=='integer_attestation':bad['human_attestation']=0
    else:bad['review_authorization']['extra']='ignored?'
    with pytest.raises(ValueError):check_packet(bad,json.loads((tmp_path/'input/sources.json').read_text()))
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):release(tmp_path/'input',p,tmp_path/'out')
    assert not (tmp_path/'out').exists()
