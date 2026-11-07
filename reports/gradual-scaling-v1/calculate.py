"""Exact integer parameter accounting; no framework imports/model allocation."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
V,C,T=50257,1024,512

def count(d,l):
    # Tied token/output embedding; learned positions; two affine LN per block;
    # qkv/out/4xMLP weights and biases; final affine LN.
    return (V+C)*d+l*(12*d*d+13*d)+2*d

def compute(d,l):
    # Approx forward FLOPs/token: dense blocks + causal attention upperbound
    # (unmasked square work) + full vocabulary projection. Excludes pointwise,
    # normalization, embedding gathers and kernel/backend overhead.
    return 24*l*d*d+4*l*T*d+2*V*d

base=compute(768,12)
rows=[]
for name,d,l,h in [('current',768,12,12),('modest_depth',768,16,12),('depth_250m',768,30,12),('width_depth_342m',1024,23,16),('approximately_500m',1280,22,20),('below_1b_ceiling',1536,32,24)]:
    n=count(d,l);assert d%h==0 and n<=1000000000
    rows.append(dict(name=name,width=d,depth=l,heads=h,head_dimension=d//h,total_parameters=n,
        token_embedding_parameters=V*d,position_embedding_parameters=C*d,block_parameters=l*(12*d*d+13*d),final_norm_parameters=2*d,
        fp32_weights_bytes=4*n,fp32_adam_moments_bytes=8*n,fp32_gradients_bytes=4*n,
        parameter_gradient_optimizer_floor_bytes=16*n,checkpoint_weights_moments_floor_bytes=12*n,
        forward_flops_per_token_proxy=compute(d,l),relative_compute_proxy=compute(d,l)/base,
        relative_layer_width_activation_proxy=l*d/(12*768)))
assert rows[0]['total_parameters']==124439808
out=dict(state='prospective_not_authorized_for_launch',vocabulary=V,context=C,compute_sequence_length=T,
    parameter_formula='(vocabulary+context)*width + depth*(12*width^2+13*width) + 2*width',
    compute_formula='24*depth*width^2 + 4*depth*sequence_length*width + 2*vocabulary*width',
    current_code_sha256=hashlib.sha256((ROOT/'gpt2.py').read_bytes()).hexdigest(),architectures=rows,
    assumptions=['Exactly current GPT2 implementation: tied output weights, full multihead attention, affine LayerNorm, 4x GELU MLP, all linear biases, learned position embeddings.',
    'FP32 parameters, gradients and two Adam moments:16 bytes/parameter. Autocast BF16 does not remove FP32 master/state. No extra master copy assumed.',
    'Memory floors exclude activations, logits, gradient temporaries, optimizer foreach temporaries, allocator/cache, data, Python and checkpoint copies.',
    'Compute proxy is not measured latency or training throughput; sequence512, unchanged tokenizer. Backward proportionality is approximate.',
    'Layer-width activation proxy is illustrative only; full attention/logits terms and recomputation alter actual peaks.',
    'No checkpoint conversion, growth transformation, pretrained substitution, GPU execution or automatic next-size activation.'])
path=Path(__file__).with_name('options.json');path.write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['name'],r['total_parameters'],round(r['parameter_gradient_optimizer_floor_bytes']/2**30,3),round(r['checkpoint_weights_moments_floor_bytes']/2**30,3),round(r['relative_compute_proxy'],3))
