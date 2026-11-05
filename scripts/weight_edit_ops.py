"""Pure NumPy checkpoint algebra; no optimizer or training operations."""
import numpy as np

def bf16_codes(x):
    bits=np.ascontiguousarray(x,dtype=np.float32).view(np.uint32)
    return ((bits + np.uint32(0x7fff) + ((bits>>16)&1))>>16).astype(np.uint16)

def top_fraction(delta,fraction):
    if not 0<fraction<=1:raise ValueError('Invalid fraction')
    flat=delta.reshape(-1);k=max(1,int(np.ceil(flat.size*fraction)))
    # Stable tie break by original index; exact k selected, even at threshold ties.
    magnitude=np.abs(flat);threshold=np.partition(magnitude,flat.size-k)[flat.size-k]
    selected=magnitude>threshold;needed=k-int(selected.sum())
    ties=np.flatnonzero(magnitude==threshold);selected[ties[:needed]]=True
    return np.where(selected,flat,0).reshape(delta.shape)

def edited_tensor(name,v11,p100,v15,p200,v18,method,scale):
    if method=='global_rollback':return v11+np.float32(scale)*(p100-v11)
    if method=='embedding_norm_rollback':
        return v11+np.float32(scale)*(p100-v11) if name=='embed.weight' or name=='norm.weight' or '.n1.' in name or '.n2.' in name else v11.copy()
    if method=='sparse_v15_delta':return v11+np.float32(scale)*top_fraction(v15-v11,.2)
    if method=='clean_matrix_transfer':
        is_matrix=name.startswith('layers.') and name.split('.')[2] in ['q','k','v','o','gate','up','down']
        return v11+np.float32(scale)*(v18-p200) if is_matrix else v11.copy()
    raise ValueError('Unrecognized edit')
