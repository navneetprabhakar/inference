"""Train-only add-alpha reference; no neural weights or final-set selection."""
import numpy as np

class Unigram:
    def __init__(self,counts,alpha):
        counts=np.asarray(counts)
        if counts.ndim!=1 or len(counts)<2 or counts.dtype.kind not in 'iu' or np.any(counts<0) or counts.sum()==0:raise ValueError('Nonempty nonnegative integer counts required')
        if type(alpha) not in (int,float) or not np.isfinite(alpha) or alpha<=0:raise ValueError('Positive finite smoothing required')
        self.counts=counts.copy();self.alpha=alpha
        self.logp=np.log(self.counts.astype(np.float64)+alpha)-np.log(float(counts.sum())+alpha*len(counts))

    def score(self,targets):
        x=np.asarray(targets)
        if x.dtype.kind not in 'iu' or x.size==0 or x.min()<0 or x.max()>=len(self.counts):raise ValueError('Invalid targets')
        return float(-self.logp[x].sum())
