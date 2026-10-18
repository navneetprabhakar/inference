"""Synthetic fixture reviews only; no real-source clearance or training."""
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import pytest
pytest.importorskip('tokenizers')
from slm.common.tokenizer import train_core,BPE
from slm.common.config import Config,initialize
from slm.common.training import Trainer,Recipe
from slm.data.review import prepare,release
from slm.data.tokenized import build_shards,ShardBatches,sha
from slm.data.mixture import build_mixture,MixtureBatches,SCHEDULE
from test_review import fixture_snapshot,approved_packet
from test_resume import compare


def components(tmp_path,objective='foundation'):
    tok=tmp_path/'tokenizer';train_core(['Alpha Beta Question Answer Paragraph synthetic numbers.']*20,512).save(tok,{'scope':'Synthetic fixture'})
    out=[]
    for name in ('alpha','beta'):
        root=tmp_path/name;root.mkdir();fixture_snapshot(root/'raw',source_name=name,content_prefix=name+' ',kind='prose' if objective=='foundation' else 'dialogue')
        prepare(root/'raw',root/'review.json',30);approved_packet(root/'review.json');release(root/'raw',root/'review.json',root/'reviewed')
        r=build_shards(root/'reviewed',tok,root/'tokens',objective,context_length=64,shard_positions=128)
        out.append({'id':name,'path':root/'tokens','dataset_hash':r['dataset_hash'],'weight':3 if name=='alpha' else 1,'max_passes':2,'max_positions':100000})
    return out,tok


def build(cs,tok,out,**kwargs):
    opts=dict(objective='foundation',budget=2000,minimum=100,group_cap=100000,seed='fixture')
    opts.update(kwargs)
    return build_mixture(cs,tok,out,**opts)


def paths(cs):return {c['id']:c['path'] for c in cs}


def test_deterministic_path_independent_schedule_realized_weights_and_counts(tmp_path):
    cs,tok=components(tmp_path)
    r=build(cs,tok,tmp_path/'mix');other=build(list(reversed(cs)),tok,tmp_path/'other')
    assert r==other and (tmp_path/'mix/schedule.bin').read_bytes()==(tmp_path/'other/schedule.bin').read_bytes()
    assert r['weight_basis']=='processed_positions'
    assert .65<r['components']['alpha']['realized_metric_fraction']<.85
    assert r['planned_processed_positions']<=2000 and r['implicit_wraparound'] is False
    with MixtureBatches(tmp_path/'mix',paths(cs),tok,r['dataset_hash']) as mixed:
        assert mixed.fingerprint==r['dataset_hash']
        x=s=0
        for i in range(len(mixed)):
            a,y,m=mixed[i];x+=a.size;s+=int(m.sum());assert not a.flags.writeable
        assert (x,s)==mixed.counts(len(mixed))==(r['planned_processed_positions'],r['planned_supervised_positions'])
        assert mixed.counts(0)==(0,0)
    copied=tmp_path/'different-layout';copied.mkdir();new_paths={}
    for c in cs:
        dest=copied/(c['id']+'-relocated');shutil.copytree(c['path'],dest);new_paths[c['id']]=dest
    shutil.copytree(tmp_path/'mix',copied/'schedule')
    with MixtureBatches(copied/'schedule',new_paths,tok,r['dataset_hash']) as moved:assert moved.fingerprint==r['dataset_hash']
    manifest=(tmp_path/'mix/manifest.json').read_text();assert str(tmp_path) not in manifest


def test_exposure_caps_and_finite_reallocation_do_not_loop_small_sources(tmp_path):
    cs,tok=components(tmp_path);cs[0]['max_positions']=300
    r=build(cs,tok,tmp_path/'capped',budget=3000,minimum=500,group_cap=100000)
    assert r['components']['alpha']['metric']<=300
    assert r['components']['beta']['realized_metric_fraction']>r['components']['alpha']['realized_metric_fraction']
    assert r['repeated_processed_positions']>0
    assert r['planned_processed_positions']<=2*r['unique_prepared_processed_positions']
    exposure=[json.loads(v) for v in (tmp_path/'capped/exposure.jsonl').read_text().splitlines()]
    assert all(v['processed']<=2*v['unique_prepared_processed'] for v in exposure)
    with pytest.raises(ValueError,match='Insufficient'):build(cs,tok,tmp_path/'underfilled',budget=100000,minimum=99999)
    assert not (tmp_path/'underfilled').exists()


def test_family_caps_use_record_spans_across_packed_foundation_batches(tmp_path):
    cs,tok=components(tmp_path)
    r=build(cs,tok,tmp_path/'family',group_cap=80,budget=2000,minimum=100)
    assert r['max_family_metric_positions']<=80 and r['excluded_candidates'].get('family_cap',0)>0
    with MixtureBatches(tmp_path/'family',paths(cs),tok) as d:assert d.counts(len(d))[0]==r['planned_processed_positions']


def test_sft_weights_and_group_limits_count_only_supervised_positions(tmp_path):
    cs,tok=components(tmp_path,'sft')
    r=build(cs,tok,tmp_path/'sft',objective='sft',budget=200,minimum=100,group_cap=20)
    assert r['weight_basis']=='supervised_positions' and r['planned_supervised_positions']<=200
    assert r['planned_processed_positions']>r['planned_supervised_positions']
    with MixtureBatches(tmp_path/'sft',paths(cs),tok) as d:
        assert d.counts(len(d))==(r['planned_processed_positions'],r['planned_supervised_positions'])


@pytest.mark.parametrize('defect',['unpinned','duplicate_id','duplicate_data','objective','legacy','categories','too_many_passes','raw'])
def test_invalid_or_overlapping_components_fail_without_publishing(tmp_path,defect):
    cs,tok=components(tmp_path)
    if defect=='unpinned':cs[0]['dataset_hash']=None
    elif defect=='duplicate_id':cs[1]['id']=cs[0]['id']
    elif defect=='duplicate_data':cs[1].update(path=cs[0]['path'],dataset_hash=cs[0]['dataset_hash'])
    elif defect=='objective':
        with pytest.raises(ValueError):build(cs,tok,tmp_path/'out',objective='sft')
        return
    elif defect in ('legacy','categories'):
        p=cs[0]['path']/'manifest.json';m=json.loads(p.read_text())
        if defect=='legacy':m.pop('lineage_schema')
        else:m['allowed_categories']=['adult_topic']
        p.write_text(json.dumps(m));cs[0]['dataset_hash']=sha(p)
    elif defect=='too_many_passes':cs[0]['max_passes']=3
    elif defect=='raw':cs[0].update(path=tmp_path/'alpha/raw',dataset_hash=sha(tmp_path/'alpha/raw/manifest.json'))
    with pytest.raises((ValueError,KeyError)):build(cs,tok,tmp_path/'out')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.mixture-*'))


def test_exact_content_and_family_overlap_cannot_bypass_cross_component_caps(tmp_path):
    cs,tok=components(tmp_path);p=cs[1]['path']/'lineage.jsonl'
    rows=[json.loads(v) for v in p.read_text().splitlines()]
    first=json.loads((cs[0]['path']/'lineage.jsonl').read_text().splitlines()[0])
    rows[0]['content_sha256']=first['content_sha256']
    p.write_text(''.join(json.dumps(v)+'\n' for v in rows))
    manifest=cs[1]['path']/'manifest.json';m=json.loads(manifest.read_text());m['files']['lineage.jsonl']=sha(p);manifest.write_text(json.dumps(m));cs[1]['dataset_hash']=sha(manifest)
    with pytest.raises(ValueError,match='Duplicate content'):build(cs,tok,tmp_path/'duplicate')


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_mixture_accumulation_same_backend_resume_and_cpu_mlx_roundtrip(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    cs,tok=components(tmp_path);r=build(cs,tok,tmp_path/'mix')
    with MixtureBatches(tmp_path/'mix',paths(cs),tok) as data:
        c=Config(vocab_size=data.vocab_size);recipe=Recipe(accumulation_steps=3,embedding_implementation='dense-onehot-v1')
        a=Trainer(c,initialize(c),data,backend,recipe=recipe,tokenizer_hash=data.tokenizer_hash)
        a.update();a.save(tmp_path/'state');b=Trainer.resume(tmp_path/'state',data,backend,tokenizer_hash=data.tokenizer_hash)
        for _ in range(2):assert a.update()==b.update();compare(a,b,True)
        b.save(tmp_path/'next')
        moved=Trainer.resume(tmp_path/'next',data,'torch',tokenizer_hash=data.tokenizer_hash)
        a.update();moved.update();compare(a,moved)


def rehash(path,file):
    p=path/'manifest.json';m=json.loads(p.read_text());m['files'][file]=sha(path/file);p.write_text(json.dumps(m))


@pytest.mark.parametrize('defect',['reference','prefix','repeat','group_cap','component_cap'])
def test_rehashed_index_still_has_to_obey_token_and_exposure_contract(tmp_path,defect):
    cs,tok=components(tmp_path);build(cs,tok,tmp_path/'mix')
    p=tmp_path/'mix/schedule.bin';rows=np.fromfile(p,dtype=SCHEDULE)
    if defect=='reference':rows[0]['batch']=999999
    elif defect=='prefix':rows[0]['prefix_tokens']=1
    elif defect=='repeat':rows[0]['pass']=1
    else:
        m=json.loads((tmp_path/'mix/manifest.json').read_text())
        if defect=='group_cap':m['group_cap']=1
        else:m['components'][0]['max_positions']=1
        (tmp_path/'mix/manifest.json').write_text(json.dumps(m))
    rows.tofile(p);rehash(tmp_path/'mix','schedule.bin')
    with pytest.raises(ValueError):MixtureBatches(tmp_path/'mix',paths(cs),tok)


def test_pinned_identity_live_mutations_and_interrupted_publication(tmp_path,monkeypatch):
    cs,tok=components(tmp_path);r=build(cs,tok,tmp_path/'mix')
    with pytest.raises(ValueError,match='fingerprint'):MixtureBatches(tmp_path/'mix',paths(cs),tok,'0'*64)
    with MixtureBatches(tmp_path/'mix',paths(cs),tok) as d:
        with (tmp_path/'mix/report.json').open('a') as f:f.write(' ')
        with pytest.raises(ValueError,match='changed'):d[0]
    import slm.data.mixture as module
    def fail(*args):raise OSError('fixture interrupted rename')
    monkeypatch.setattr(module.os,'rename',fail)
    with pytest.raises(OSError):build(cs,tok,tmp_path/'interrupted')
    assert not (tmp_path/'interrupted').exists() and not list(tmp_path.glob('.mixture-*'))


def test_inconsistent_parent_alias_is_rejected_and_shared_global_family_has_one_cap(tmp_path):
    cs,tok=components(tmp_path);first=json.loads((cs[0]['path']/'lineage.jsonl').read_text().splitlines()[0])
    p=cs[1]['path']/'lineage.jsonl';rows=[json.loads(v) for v in p.read_text().splitlines()]
    rows[0]['parent_group_id']=first['parent_group_id']
    def save():
        p.write_text(''.join(json.dumps(v)+'\n' for v in rows));mfile=cs[1]['path']/'manifest.json';m=json.loads(mfile.read_text());m['files']['lineage.jsonl']=sha(p);mfile.write_text(json.dumps(m));cs[1]['dataset_hash']=sha(mfile)
    save()
    with pytest.raises(ValueError,match='parent-family'):build(cs,tok,tmp_path/'alias')
    rows[0]['split_group']=first['split_group'];save()
    r=build(cs,tok,tmp_path/'global',group_cap=80)
    assert r['max_family_metric_positions']<=80


def test_source_selection_preserves_review_guard_and_declared_inventory(tmp_path):
    cs,tok=components(tmp_path)
    with pytest.raises(ValueError,match='No eligible'):
        build_shards(tmp_path/'alpha/reviewed',tok,tmp_path/'none','foundation',allowed_sources=('unknown',))
    r=build_shards(tmp_path/'alpha/reviewed',tok,tmp_path/'selected','foundation',allowed_sources=('alpha',))
    m=json.loads((tmp_path/'selected/manifest.json').read_text())
    assert m['allowed_sources']==['alpha'] and set(r['sources'])=={'alpha'}
    with pytest.raises(ValueError,match='sample-only'):
        build_shards(tmp_path/'alpha/raw',tok,tmp_path/'unreviewed','foundation',allowed_sources=('alpha',))


def test_config_cli_resolves_relative_components(tmp_path):
    import subprocess
    import sys
    cs,tok=components(tmp_path)
    for c in cs:c['path']=str(c['path'].relative_to(tmp_path))
    config={'components':cs,'objective':'foundation','budget':2000,'minimum':100,'group_cap':100000,'seed':'cli'}
    (tmp_path/'config.json').write_text(json.dumps(config))
    result=subprocess.run([sys.executable,'-m','slm.data.mixture','--config',str(tmp_path/'config.json'),
        '--tokenizer',str(tok),'--output',str(tmp_path/'cli')],check=True,capture_output=True,text=True)
    report=json.loads(result.stdout)
    with MixtureBatches(tmp_path/'cli',{c['id']:tmp_path/c['path'] for c in cs},tok,report['dataset_hash']) as data:
        assert data.counts(len(data))[0]==report['planned_processed_positions']
