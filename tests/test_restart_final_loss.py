import copy,hashlib,json
import numpy as np
import pytest
from slm.restart.final_loss import FinalTokens,paired_bootstrap,assess
from slm.restart.development_loss import DevelopmentTokens,summarize


def make(root,*,documents=500,length=1000,split='test',selection='all documents',partial=False):
    root.mkdir(exist_ok=True)
    values=np.full((documents,length),10,dtype='<u2');values[:,-1]=1 if not partial else 10
    rows=[dict(audit_id=str(i),family_id='family-'+str(i),split=split,offset=i*length,targets=length,
        full_document_targets=length+int(partial),partial=partial,scored_utf8_bytes=2*length) for i in range(documents)]
    (root/'tokens.u16').write_bytes(values.tobytes())
    (root/'index.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    manifest=dict(split=split,selection=selection,documents=documents,families=documents,targets=documents*length,
        scored_utf8_bytes=2*documents*length,files={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('tokens.u16','index.jsonl')})
    (root/'manifest.json').write_text(json.dumps(manifest))
    return hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()


def payload(store,loss):
    records=[dict(document=part.document,first=part.first,last=part.last,target_ids=list(part.targets),nll=[loss]*len(part.targets)) for part in store.segments()]
    result=dict(manifest_sha256=store.manifest_sha256,records=records)
    result['metrics']=summarize(store,result);return result


def test_whole_final_coverage_and_loss_gate(tmp_path):
    pin=make(tmp_path);store=FinalTokens(tmp_path,manifest_sha256=pin,vocab_size=16)
    assert store.targets==500000 and len(list(store.segments()))==1000
    neural=payload(store,1.5);baseline=payload(store,2.)
    result=assess(store,neural,{'unigram':payload(store,3.),'modified_kneser_ney':baseline})
    assert result['passed'] and result['better_frozen_baseline']=='modified_kneser_ney'
    assert result['bootstrap']['resamples']==10000
    assert result['bootstrap']['interval_95']==[.5,.5]
    assert result['neural']['bits_per_byte']==pytest.approx(1.5/np.log(2)/2)
    # A statistically positive result still needs at least 10% NLL reduction.
    result=assess(store,payload(store,1.9),{'unigram':baseline,'modified_kneser_ney':baseline})
    assert result['bootstrap']['positive_improvement'] and not result['passed']
    with pytest.raises(ValueError):DevelopmentTokens(tmp_path,manifest_sha256=pin,vocab_size=16)


@pytest.mark.parametrize('change',[{'documents':499},{'length':999},{'split':'development'},
    {'selection':'subset'},{'documents':1,'partial':True}])
def test_insufficient_or_wrong_final_release_refused(tmp_path,change):
    pin=make(tmp_path,**change)
    with pytest.raises(ValueError):FinalTokens(tmp_path,manifest_sha256=pin,vocab_size=16)


def test_bootstrap_is_paired_token_weighted_and_deterministic():
    a={'small':(1,1.),'large':(100,100.)};b={'small':(1,3.),'large':(100,200.)}
    result=paired_bootstrap(a,b)
    assert result==paired_bootstrap(a,b)
    assert result['observed_improvement']==pytest.approx(102/101)
    assert result['interval_95']==[1.,2.]
    assert paired_bootstrap(a,a)['positive_improvement'] is False


@pytest.mark.parametrize('baseline',[{'other':(1,2.)},{'a':(2,2.)},{'a':(1,float('nan'))},{'a':(1,-1.)}])
def test_bootstrap_rejects_unpaired_or_invalid_evidence(baseline):
    with pytest.raises(ValueError):paired_bootstrap({'a':(1,1.)},baseline)
