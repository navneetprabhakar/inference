"""Independent mathematical oracles for four gradient-suite case IDs.

Callbacks must be scoped and budgeted by the numerical runner. No parameters
are initialized here. Finite differences use an independent FP64 loss oracle.
"""
import numpy as np
from .numerical_forward import discrepancy


def ce_reference(logits,target):
    x=np.asarray(logits,dtype=np.float64)
    if x.ndim!=1 or len(x)<2 or not np.isfinite(x).all() or type(target) is not int or not 0<=target<len(x):
        raise ValueError('Invalid analytic CE fixture')
    other=np.delete(x,target);center=other.max();weights=np.exp(other-center);weights/=weights.sum()
    margin=center+np.log(np.exp(other-center).sum())-x[target]
    loss=float(np.logaddexp(0.,margin));mass=float(np.exp(-np.logaddexp(0.,-margin)))
    gradient=np.empty_like(x);gradient[target]=-mass;gradient[np.arange(len(x))!=target]=weights*mass
    return loss,gradient


def record(errors,extra=True):
    maximum=max(errors)
    if not np.isfinite(maximum):raise ValueError('Nonfinite oracle comparison')
    return {'passed':bool(maximum<=1e-5 and extra),'maximum_absolute_error':maximum,'absolute_tolerance':1e-5,'relative_tolerance':0}


def cross_entropy_cases(invoke):
    """invoke(backend, FP32 logits[1,4], targets[1]) -> mean loss, numpy gradient."""
    tail=[];offset=[];signs=True;positions=0
    for margin in (-60.,-20.,0.,20.,60.):
        x=np.array([[margin,0.,0.,0.]],np.float32);expected,g=ce_reference(x[0],0)
        for backend in ('mlx','torch'):
            loss,gradient=invoke(backend,x,np.array([0],np.int32));positions+=1
            loss2,gradient2=invoke(backend,x+100.,np.array([0],np.int32));positions+=1
            tail.extend([discrepancy([loss],[expected]),discrepancy(gradient,g[None,:])])
            offset.extend([discrepancy([loss],[loss2]),discrepancy(gradient,gradient2)])
            # Absolute tolerance alone would incorrectly accept collapsed tiny gradients.
            signs=signs and bool(np.all(np.sign(gradient)==np.sign(g[None,:])))
            signs=signs and bool(np.all(np.sign(gradient2)==np.sign(g[None,:])))
    return {'cases':{'gradients:stable_ce_confident_tail':record(tail,signs),
                     'gradients:stable_ce_common_offset':record(offset,signs)},'logit_target_positions':positions}


def tied_embedding_case(invoke):
    """invoke(backend) -> (full gradient, input-only gradient, output-only gradient).

    Adapter must detach output embedding for input-only, and detach hidden state
    for output-only; all three use the same parameters, batch and mean loss.
    """
    errors=[];nonzero=True
    for backend in ('mlx','torch'):
        full,input_only,output_only=map(np.asarray,invoke(backend))
        discrepancy(full,input_only);discrepancy(full,output_only) # validate without accepting these differences
        errors.append(discrepancy(full,input_only+output_only))
        nonzero=nonzero and bool(np.any(input_only!=0) and np.any(output_only!=0))
    return {'gradients:tied_embedding_both_paths':record(errors,nonzero)}


def finite_difference_case(parameters,analytic_gradients,loss64):
    """Central differences at predeclared first/last coordinates in four tensors.

    loss64(name, index, replacement) performs a fresh FP64 reference forward
    with that single parameter replaced; it must not mutate shared parameters.
    """
    names=('embedding','layers.0.q','layers.0.down','final_norm');errors=[];points=[]
    if set(analytic_gradients)!= {'mlx','torch'}:raise ValueError('Both analytic backends required')
    for name in names:
        p=np.asarray(parameters[name]);assert p.size>1
        for index in (tuple(0 for _ in p.shape),tuple(n-1 for n in p.shape)):
            value=float(p[index]);epsilon=1e-4
            plus=float(loss64(name,index,value+epsilon));minus=float(loss64(name,index,value-epsilon))
            estimate=(plus-minus)/(2*epsilon)
            for backend in ('mlx','torch'):
                g=np.asarray(analytic_gradients[backend][name])
                if g.shape!=p.shape:raise ValueError('Finite-difference gradient shape mismatch')
                errors.append(discrepancy([float(g[index])],[estimate]))
            points.append({'parameter':name,'index':list(index),'epsilon':epsilon,'reference_derivative':estimate})
    return {'cases':{'gradients:finite_difference_selected_parameters':record(errors)},'points':points,'fp64_forward_calls':2*len(points)}
