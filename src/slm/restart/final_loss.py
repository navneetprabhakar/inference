"""Final-only loss inputs and paired family-bootstrap research gate.

No model loading, launch authority or training imports. The final evaluator must
bind the one development-selected checkpoint and enforce supervised custody.
"""
import json,math
from collections import defaultdict
import numpy as np
from .development_loss import _LossTokens,summarize
from .token_store import _read


class FinalTokens(_LossTokens):
    def __init__(self,root,*,manifest_sha256,vocab_size=8192):
        super().__init__(root,manifest_sha256=manifest_sha256,split='test',vocab_size=vocab_size)
        manifest=self.manifest
        if (manifest.get('selection')!='all documents' or any(row['partial'] for row in self.rows)
                or self.targets<500000 or len({row['family_id'] for row in self.rows})<500):
            raise ValueError('Final loss requires all whole test documents, 500k targets and 500 families')


def family_totals(store,payload):
    metrics=summarize(store,payload)
    if payload.get('metrics')!=metrics:raise ValueError('Reported final loss differs from raw evidence')
    documents={row['audit_id']:row['family_id'] for row in store.rows}
    totals=defaultdict(lambda:[0,[]])
    for row in payload['records']:
        family=documents[row['document']]
        totals[family][0]+=len(row['nll']);totals[family][1].extend(row['nll'])
    return metrics,{key:(value[0],math.fsum(value[1])) for key,value in totals.items()}


def paired_bootstrap(neural,baseline):
    """Sample whole families with replacement; retain token weighting in each draw."""
    if not neural or set(neural)!=set(baseline):raise ValueError('Paired family inventory required')
    families=sorted(neural);counts=[];differences=[]
    for family in families:
        n,a=neural[family];m,b=baseline[family]
        if (type(n) is not int or n<=0 or n!=m or any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in (a,b))):
            raise ValueError('Invalid paired family totals')
        counts.append(n);differences.append(b-a)
    counts=np.asarray(counts,dtype=np.float64);differences=np.asarray(differences,dtype=np.float64)
    rng=np.random.Generator(np.random.PCG64(42));values=[]
    for first in range(0,10000,64):
        indices=rng.integers(0,len(families),size=(min(64,10000-first),len(families)))
        values.extend((differences[indices].sum(axis=1)/counts[indices].sum(axis=1)).tolist())
    low,high=np.quantile(values,[.025,.975],method='linear')
    return {'resamples':10000,'seed':42,'rng':'PCG64','unit':'family','statistic':'baseline-minus-neural token-weighted NLL',
            'interval_95':[float(low),float(high)],'positive_improvement':bool(low>0),
            'observed_improvement':float(differences.sum()/counts.sum()),'families':len(families)}


def assess(store,neural,baselines):
    if set(baselines)!={'unigram','modified_kneser_ney'}:raise ValueError('Both frozen baselines required')
    if store.targets<500000 or len({row['family_id'] for row in store.rows})<500:
        raise ValueError('Insufficient final research denominator')
    metrics,families=family_totals(store,neural)
    references={name:family_totals(store,payload) for name,payload in baselines.items()}
    better=min(sorted(references),key=lambda name:references[name][0]['nll'])
    baseline,paired=references[better];interval=paired_bootstrap(families,paired)
    passed=metrics['nll']<=.9*baseline['nll'] and interval['positive_improvement']
    return {'passed':passed,'neural':metrics,'baselines':{k:v[0] for k,v in references.items()},
            'better_frozen_baseline':better,'maximum_nll_ratio':.9,'bootstrap':interval,
            'scope':'Loss gate only; checkpoint provenance and all other research gates remain mandatory'}
