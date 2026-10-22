import hashlib,json
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart import final_baselines as final,kneser_ney
from slm.restart.segments import Segment


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    root=tmp_path/'restart/execution-v1';train=root/'data-train';train.mkdir(parents=True)
    counts=np.zeros(8192,dtype=np.uint64);counts[10]=1;counts[1]=1
    np.save(train/'unigram-counts.npy',counts)
    manifest={'split':'train','targets':2,'files':{'unigram-counts.npy':digest(train/'unigram-counts.npy')}}
    (train/'manifest.json').write_text(json.dumps(manifest));train_pin=digest(train/'manifest.json')
    uni={'status':'PASS','training_targets':2,'train_manifest_sha256':train_pin,
         'selected':{'alpha':.01,'development_nll':2.},'trials':[{'alpha':.01,'development_nll':2.},{'alpha':1.,'development_nll':3.}]}
    (root/'unigram-receipt.json').write_text(json.dumps(uni))
    kn=root/'kn-preparation/model';kn.parent.mkdir()
    kneser_ney.build(np.array([[0,0,0,0,10],[0,0,0,10,1]],dtype='<u2'),kn)
    receipt={'status':'PASS','training_targets':2,'selected':{'scale':1.,'development_nll':2.},
        'trials':[{'scale':1.,'development_nll':2.},{'scale':.8,'development_nll':3.}],
        'files':{path.name:digest(path) for path in kn.iterdir()}}
    (kn/'receipt.json').write_text(json.dumps(receipt))
    pins={name:digest(root/name) for name in ('data-train/manifest.json','unigram-receipt.json','kn-preparation/model/receipt.json')}
    monkeypatch.setattr(final,'PINS',pins)
    rows=[{'audit_id':'a','family_id':'fa','offset':0,'targets':2},{'audit_id':'b','family_id':'fb','offset':2,'targets':2}]
    parts=[Segment(name,0,2,(0,10),(10,1)) for name in ('a','b')]
    store=SimpleNamespace(tokens=np.array([10,1,10,1],dtype='<u2'),rows=rows,targets=4,scored_bytes=8,
                          manifest_sha256='fixture-final',segments=lambda:iter(parts))
    context={'event':'final_research_evaluation','checkpoint_sha256':'a'*64}
    return tmp_path,root,store,context,pins


def test_frozen_references_score_every_target_with_document_boundary_reset(fixture):
    project,_,store,context,_=fixture;model=final.FrozenBaselines(project);ticks=[]
    results,receipt=model.score(store,context=context,heartbeat=lambda:ticks.append(True))
    assert receipt['selection']=={'unigram_alpha':.01,'modified_kneser_ney_scale':1.}
    assert receipt['refitted'] is False and len(receipt['artifact_sha256'])==15
    for payload in results.values():
        assert payload['metrics']['targets']==4 and payload['context']==context
        assert payload['records'][0]['nll']==payload['records'][1]['nll']
    assert results['unigram']['metrics']['nll']==pytest.approx(-model.unigram.logp[10])
    assert ticks


def test_changed_reference_refused_before_scoring(fixture,monkeypatch):
    project,root,store,context,_=fixture;model=final.FrozenBaselines(project)
    (root/'data-train/unigram-counts.npy').write_bytes(b'changed')
    monkeypatch.setattr(model.kn,'probabilities',lambda query:pytest.fail('Changed reference must not score'))
    with pytest.raises(ValueError):model.score(store,context=context,heartbeat=lambda:None)


def test_changed_reference_during_scoring_is_rejected(fixture):
    project,root,store,context,_=fixture;model=final.FrozenBaselines(project);ticks=[]
    def heartbeat():
        ticks.append(True)
        if len(ticks)==2:(root/'unigram-receipt.json').write_text('{}')
    with pytest.raises(ValueError):model.score(store,context=context,heartbeat=heartbeat)


def test_final_data_cannot_reselect_smoothing(fixture):
    project,root,_,_,pins=fixture;path=root/'unigram-receipt.json'
    receipt=json.loads(path.read_bytes());receipt['selected']=receipt['trials'][1];path.write_text(json.dumps(receipt))
    pins['unigram-receipt.json']=digest(path)
    with pytest.raises(ValueError,match='development'):final.FrozenBaselines(project)


@pytest.mark.parametrize('values',[np.zeros(4),np.full(4,np.nan),np.full(4,1.01),np.ones(3)])
def test_invalid_reference_probabilities_are_not_clipped_or_dropped(fixture,monkeypatch,values):
    project,_,store,context,_=fixture;model=final.FrozenBaselines(project)
    monkeypatch.setattr(model.kn,'probabilities',lambda query:values)
    with pytest.raises(ValueError):model.score(store,context=context,heartbeat=lambda:None)


def test_development_event_cannot_invoke_final_reference_path(fixture):
    project,_,store,_,_=fixture;model=final.FrozenBaselines(project)
    with pytest.raises(ValueError):model.score(store,context={'event':'dev_loss_checkpoint'},heartbeat=lambda:None)
