"""Eight required forward checks. Caller supplies a budgeted, scoped invocation.

invoke(backend, tokens, padding_mask=None, cache=None) returns numpy logits,
backend-native cache, and numpy layer traces. This module never creates weights.
"""
import numpy as np


def discrepancy(left,right):
    a,b=np.asarray(left),np.asarray(right)
    if a.shape!=b.shape or not a.size or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Invalid numerical comparison shape/value')
    return float(np.max(np.abs(a.astype(np.float64)-b.astype(np.float64))))


def run(config,batches,invoke):
    results={};base={};work=0
    def call(backend,tokens,padding=None,cache=None):
        nonlocal work
        x=np.asarray(tokens,dtype=np.int32)
        # Actual runner must reserve before invoke; this count is a reconciliation.
        work+=x.size
        logits,cached,traces=invoke(backend,x,padding_mask=padding,cache=cache)
        if np.asarray(logits).shape!=(*x.shape,config.vocab_size) or not np.isfinite(logits).all():raise ValueError('Invalid forward logits')
        if len(traces)!=config.num_layers:raise ValueError('Invalid trace inventory')
        for trace in traces:
            if np.asarray(trace).shape!=(*x.shape,config.hidden_size) or not np.isfinite(trace).all():raise ValueError('Invalid layer trace')
        return logits,cached,traces
    def record(case,errors):
        maximum=max(errors)
        results['forward:'+case]={'passed':maximum<=1e-5,'maximum_absolute_error':maximum,'absolute_tolerance':1e-5,'relative_tolerance':0}
    for name,case in [('single','single_token_logits'),('unpadded','un-padded_batch_logits'),('padded','right_padded_valid_logits')]:
        row=batches[name];mask=np.asarray(row['padding_mask'],dtype=bool)
        # The single fixture includes BOS+content; first-position comparison is the single-token check.
        x=np.asarray(row['inputs'],dtype=np.int32)
        if name=='single':x=x[:,:1];mask=mask[:,:1]
        for backend in ('mlx','torch'):base[backend,name]=call(backend,x,mask if name=='padded' else None)
        a,b=(base[backend,name][0] for backend in ('mlx','torch'))
        errors=[discrepancy(np.asarray(a)[mask],np.asarray(b)[mask])]
        if name=='padded':
            for backend in ('mlx','torch'):
                for i in range(len(x)):
                    n=int(mask[i].sum());trimmed=call(backend,x[i:i+1,:n])[0]
                    errors.append(discrepancy(np.asarray(base[backend,name][0])[i:i+1,:n],trimmed))
        record(case,errors)
    record('layer_residual_traces',[discrepancy(a,b) for a,b in zip(base['mlx','unpadded'][2],base['torch','unpadded'][2])])
    original=np.asarray(batches['unpadded']['inputs'],dtype=np.int32)
    perturbed=np.asarray(batches['causal_perturbation']['inputs'],dtype=np.int32)
    positions=batches['causal_perturbation']['unchanged_logit_positions']
    if not positions or not np.array_equal(original[:,positions],perturbed[:,positions]):raise ValueError('Bad causal fixture')
    errors=[]
    for backend in ('mlx','torch'):
        changed=call(backend,perturbed)[0]
        errors.append(discrepancy(np.asarray(base[backend,'unpadded'][0])[:,positions],np.asarray(changed)[:,positions]))
    record('causal_future_perturbation',errors)
    isolated=original.copy();isolated[1,:]=15;errors=[]
    for backend in ('mlx','torch'):
        changed=call(backend,isolated)[0]
        errors.append(discrepancy(np.asarray(base[backend,'unpadded'][0])[0],np.asarray(changed)[0]))
    record('separate_document_perturbation',errors)
    errors=[]
    for backend in ('mlx','torch'):
        cache=None;chunks=[]
        for i in range(original.shape[1]):
            out,cache,_=call(backend,original[:,i:i+1],cache=cache);chunks.append(out)
        errors.append(discrepancy(base[backend,'unpadded'][0],np.concatenate(chunks,axis=1)))
    record('cached_vs_full_decode',errors)
    errors=[];offset=4
    for backend in ('mlx','torch'):
        _,cache,_=call(backend,original[:,:offset])
        out,_,_=call(backend,original[:,offset:],cache=cache)
        errors.append(discrepancy(np.asarray(base[backend,'unpadded'][0])[:,offset:],out))
    record('rope_offset_decode',errors)
    return {'cases':results,'forward_input_positions':work,'passed':all(r['passed'] for r in results.values())}
