"""Gradient-suite comparisons; caller supplies budgeted model invocation.

invoke(backend, batch, embedding_implementation=...) returns loss and a numpy
parameter-gradient dictionary. No weights are created by this module.
"""
import copy
import numpy as np
from .numerical_forward import discrepancy


def compare_gradients(left,right,shapes):
    if set(left)!=set(shapes) or set(right)!=set(shapes):raise ValueError('Gradient inventory mismatch')
    differences=[]
    for key,shape in shapes.items():
        if np.asarray(left[key]).shape!=tuple(shape) or np.asarray(right[key]).shape!=tuple(shape):
            raise ValueError('Gradient shape mismatch')
        differences.append(discrepancy(left[key],right[key]))
    if not differences:raise ValueError('Empty parameter inventory')
    return max(differences)


def run(batches,shapes,invoke):
    results={};work=0
    def call(backend,batch,embedding='native-gather-v1'):
        nonlocal work
        work+=np.asarray(batch['inputs']).size
        loss,grad=invoke(backend,batch,embedding_implementation=embedding)
        if not np.isfinite(loss) or loss<0:raise ValueError('Invalid gradient loss')
        compare_gradients(grad,grad,shapes)
        return float(loss),grad
    def record(case,errors,extra=True):
        maximum=max(errors);results['gradients:'+case]={'passed':bool(maximum<=1e-5 and extra),'maximum_absolute_error':maximum,'absolute_tolerance':1e-5,'relative_tolerance':0}
    padded=batches['padded'];base={b:call(b,padded) for b in ('mlx','torch')}
    record('all_parameter_gradients',[abs(base['mlx'][0]-base['torch'][0]),compare_gradients(base['mlx'][1],base['torch'][1],shapes)])
    errors=[]
    # Independent trimmed forwards: weighted aggregate must match padded batch.
    for backend in ('mlx','torch'):
        total=0;loss_sum=0.;sums={k:np.zeros(s,dtype=np.float64) for k,s in shapes.items()}
        for i,mask in enumerate(padded['loss_mask']):
            n=int(sum(mask));trimmed={k:[padded[k][i][:n]] for k in ('inputs','targets','loss_mask','padding_mask')}
            loss,g=call(backend,trimmed);total+=n;loss_sum+=loss*n
            for k in sums:sums[k]+=np.asarray(g[k],dtype=np.float64)*n
        errors.extend([abs(loss_sum/total-base[backend][0]),compare_gradients({k:v/total for k,v in sums.items()},base[backend][1],shapes)])
        # Change masked target IDs only. The loss/gradients must remain identical.
        modified=copy.deepcopy(padded)
        for i,mask in enumerate(modified['loss_mask']):
            for j,m in enumerate(mask):
                if m==0:modified['targets'][i][j]=15
        loss,g=call(backend,modified)
        errors.extend([abs(loss-base[backend][0]),compare_gradients(g,base[backend][1],shapes)])
    record('padding_zero_contribution',errors)
    eos=copy.deepcopy(padded)
    for i,mask in enumerate(eos['loss_mask']):
        n=int(sum(mask));assert eos['targets'][i][n-1]==1
        eos['loss_mask'][i]=[float(j==n-1) for j in range(len(mask))]
    a,b=(call(backend,eos) for backend in ('mlx','torch'))
    norms=[sum(float(np.square(np.asarray(g,dtype=np.float64)).sum()) for g in result[1].values()) for result in (a,b)]
    record('eos_nonzero_contribution',[abs(a[0]-b[0]),compare_gradients(a[1],b[1],shapes)],extra=all(n>0 for n in norms))
    errors=[]
    for backend in ('mlx','torch'):
        loss,g=call(backend,padded,'dense-onehot-v1')
        errors.extend([abs(loss-base[backend][0]),compare_gradients(g,base[backend][1],shapes)])
    record('native_vs_onehot_embedding',errors)
    return {'cases':results,'gradient_input_positions':work,'passed':all(r['passed'] for r in results.values())}
