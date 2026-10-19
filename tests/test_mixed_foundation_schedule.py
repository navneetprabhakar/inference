"""Version-two schedules explicitly account sources inside one packed leaf."""
# Creator: Navneet Prabhakar
import json
import pytest
from slm.data.mixture import build_mixture,MixtureBatches
from slm.data.tokenized import sha
from test_mixture import components,build,paths


def mixed_fixture(tmp_path):
    cs,tok=components(tmp_path);cs=cs[:1];root=cs[0]['path']
    # Synthetic lineage-only scheduling fixture. Student Inputs independently
    # re-encodes source rows; this fixture does not grant any source admission.
    p=root/'lineage.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
    rows[-1]['source']='second-synthetic-source'
    p.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in rows))
    m=json.loads((root/'manifest.json').read_text());m['files']['lineage.jsonl']=sha(p)
    (root/'manifest.json').write_text(json.dumps(m,sort_keys=True)+'\n');cs[0]['dataset_hash']=sha(root/'manifest.json')
    return cs,tok


def test_mixed_source_requires_explicit_v2_and_exact_source_span_accounting(tmp_path):
    cs,tok=mixed_fixture(tmp_path)
    with pytest.raises(ValueError,match='single-source'):build(cs,tok,tmp_path/'legacy')
    report=build(cs,tok,tmp_path/'v2',budget=100000,minimum=100,allow_mixed_sources=True)
    assert len(report['sources'])==2
    assert sum(x['processed'] for x in report['sources'].values())==report['planned_processed_positions']
    assert sum(x['unique_prepared_processed'] for x in report['sources'].values())==report['unique_prepared_processed_positions']
    with MixtureBatches(tmp_path/'v2',paths(cs),tok) as d:
        assert d.manifest['version']==2 and d.counts(len(d))[0]==report['planned_processed_positions']
    p=tmp_path/'v2/report.json';r=json.loads(p.read_text());r['sources'][next(iter(r['sources']))]['processed']+=1;p.write_text(json.dumps(r))
    p=tmp_path/'v2/manifest.json';m=json.loads(p.read_text());m['files']['report.json']=sha(p.parent/'report.json');p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='source exposure'):MixtureBatches(p.parent,paths(cs),tok)


def test_mixed_source_flag_does_not_enable_sft_or_implicit_scope(tmp_path):
    cs,tok=components(tmp_path)
    with pytest.raises(ValueError,match='foundation v2'):build(cs,tok,tmp_path/'sft',allow_mixed_sources=True,objective='sft')
    with pytest.raises(ValueError,match='foundation v2'):build(cs,tok,tmp_path/'truthy',allow_mixed_sources=1)
