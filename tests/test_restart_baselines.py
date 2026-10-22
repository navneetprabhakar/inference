import numpy as np
import pytest
from slm.restart.baselines import Unigram

def test_unigram_normalization_and_exact_probability():
    b=Unigram(np.array([2,0,1],dtype=np.uint64),1.)
    np.testing.assert_allclose(np.exp(b.logp),[3/6,1/6,2/6],rtol=1e-14)
    assert abs(np.exp(b.logp).sum()-1)<1e-14
    assert b.score(np.array([0,1,2]))==pytest.approx(-np.log(3/6)-np.log(1/6)-np.log(2/6))

@pytest.mark.parametrize('counts,alpha',[([0,0],1),([-1,2],1),([1.,2.],1),([1,2],0),([1,2],float('nan'))])
def test_invalid_baseline_refused(counts,alpha):
    with pytest.raises(ValueError):Unigram(np.array(counts),alpha)
