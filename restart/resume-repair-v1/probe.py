import json,time
from pathlib import Path
import mlx.core as mx
import numpy as np

@mx.custom_function
def lookup(weight, ids):
    return weight[ids]

@lookup.vjp
def lookup_vjp(primals, cotangent, output):
    weight, ids = primals
    with mx.stream(mx.cpu):
        grad = mx.zeros(weight.shape, dtype=mx.float32).at[ids.reshape(-1)].add(cotangent.reshape(-1,weight.shape[1]).astype(mx.float32))
        grad = grad.astype(weight.dtype)
    return grad, mx.zeros_like(ids)

if __name__=='__main__':
    mx.random.seed(246024)
    w=mx.random.normal((32000,288)).astype(mx.bfloat16)
    ids=mx.array(np.random.default_rng(246024).integers(0,64,(8,256)).astype(np.int32))
    cot=mx.random.normal((8,256,288)).astype(mx.bfloat16)
    mx.eval(w,ids,cot)
    result={}
    for name,fn in [('native',lambda w,ids:w[ids]),('cpu_backward',lookup)]:
        grad=mx.compile(mx.grad(lambda w,ids,c:mx.sum(fn(w,ids).astype(mx.float32)*c.astype(mx.float32))))
        arr=[];t=time.monotonic()
        for i in range(3):
            g=grad(w,ids,cot);mx.eval(g);arr.append(np.array(g.astype(mx.float32)))
        reference=np.zeros((32000,288),np.float32);np.add.at(reference,np.array(ids).reshape(-1),np.array(cot.astype(mx.float32)).reshape(-1,288))
        ref=np.array(mx.array(reference).astype(mx.bfloat16).astype(mx.float32))
        result[name]={'exact_repeats':all(np.array_equal(arr[0],a) for a in arr[1:]),'reference_max_abs':float(np.max(np.abs(arr[0]-ref))),'seconds':time.monotonic()-t}
    Path(__file__).with_name('probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
