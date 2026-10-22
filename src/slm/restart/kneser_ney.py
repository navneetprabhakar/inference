"""Interpolated modified Kneser-Ney with three discounts, orders 1..5.

Chen & Goodman TR-10-98, section 3. Document boundaries use four BOS
markers for each scored sequence. Lower-order effective counts are distinct
left-context counts; highest-order counts are occurrences. No cross-document
windows. Count-derived discounts have a fixed documented sparse-count fallback.
"""
import json
from pathlib import Path
import numpy as np


def dtype(n):return np.dtype([(str(i),'<u2') for i in range(n)])
def records(matrix):
    a=np.ascontiguousarray(matrix,dtype='<u2')
    return a.view(dtype(a.shape[1])).reshape(-1)

def suffix(grams,n):
    result=np.empty(len(grams),dtype=dtype(n));offset=len(grams.dtype.names)-n
    for j in range(n):result[str(j)]=grams[str(j+offset)]
    return result

def discount(counts):
    hist=[int(np.count_nonzero(counts==i)) for i in range(1,5)]
    n1,n2,n3,n4=hist
    fallback=not all((n1,n2,n3))
    if fallback:values=[.5,1.,1.5]
    else:
        y=n1/(n1+2*n2);values=[1-2*y*n2/n1,2-3*y*n3/n2,3-4*y*n4/n3]
    return np.clip(values,1e-8,np.array([1.,2.,3.])-1e-8),hist,fallback


def build(highest,output,notify=lambda _:None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    metadata={'order':5,'boundary':'four BOS=0 per document, EOS=1 already in targets','discount_scale_grid':[.8,1.,1.2],'discounts':{},'method':'interpolated modified Kneser-Ney; distinct-left-context lower counts','reference':'https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-10-98.pdf'}
    previous=None
    for n in range(5,0,-1):
        values=records(highest) if n==5 else suffix(previous,n)
        grams,counts=np.unique(values,return_counts=True)
        np.save(output/f'grams-{n}.npy',grams,allow_pickle=False)
        np.save(output/f'counts-{n}.npy',counts.astype(np.uint64),allow_pickle=False)
        if n>1:
            d,h,f=discount(counts);metadata['discounts'][str(n)]={'base':d.tolist(),'count_of_counts_1_to_4':h,'sparse_fallback_used':f}
        previous=grams;notify({'order':n,'unique_ngrams':len(grams)})
    (output/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def windows(tokens,index):
    tokens=np.asarray(tokens)
    if tokens.ndim!=1 or tokens.dtype.kind not in 'iu' or tokens.size==0 or tokens.max()>=8192:raise ValueError('Invalid token stream')
    result=np.empty((len(tokens),5),dtype='<u2');cursor=0
    for row in index:
        offset,length=row['offset'],row['targets']
        if offset!=cursor or length<=0 or offset+length>len(tokens):raise ValueError('Invalid document boundaries')
        padded=np.concatenate((np.zeros(4,dtype='<u2'),tokens[offset:offset+length]))
        result[offset:offset+length]=np.lib.stride_tricks.sliding_window_view(padded,5)
        cursor+=length
    if cursor!=len(tokens):raise ValueError('Incomplete index')
    return result


def history_keys(grams,n):
    key=np.zeros(len(grams),dtype=np.uint64)
    for j in range(n-1):key=key*8192+grams[str(j)]
    return key


def lookup(keys,query):
    positions=np.searchsorted(keys,query)
    safe=np.minimum(positions,len(keys)-1)
    found=(positions<len(keys)) & (keys[safe]==query)
    return safe,found


class Model:
    def __init__(self,path,scale=1.):
        self.path=Path(path);self.meta=json.loads((self.path/'manifest.json').read_text())
        if scale not in self.meta['discount_scale_grid']:raise ValueError('Scale outside frozen dev grid')
        self.scale=scale

    def probabilities(self,query):
        if query.ndim!=2 or query.shape[1]!=5 or query.dtype.kind not in 'iu' or query.min()<0 or query.max()>=8192:raise ValueError('Invalid query windows')
        q=records(query);prob=np.zeros(len(q),dtype=np.float64)
        for n in range(1,6):
            grams=np.load(self.path/f'grams-{n}.npy',mmap_mode='r',allow_pickle=False)
            counts=np.load(self.path/f'counts-{n}.npy',mmap_mode='r',allow_pickle=False)
            sub=suffix(q,n);pos,found=lookup(grams,sub)
            c=np.where(found,counts[pos],0).astype(np.float64)
            if n==1:prob=c/float(counts.sum());continue
            d=np.clip(np.array(self.meta['discounts'][str(n)]['base'])*self.scale,1e-8,np.array([1.,2.,3.])-1e-8)
            discounts=np.where(counts==1,d[0],np.where(counts==2,d[1],d[2]))
            histories=history_keys(grams,n);unique,starts=np.unique(histories,return_index=True)
            denominators=np.add.reduceat(counts,starts).astype(np.float64)
            removed=np.add.reduceat(discounts,starts)
            h,seen=lookup(unique,history_keys(sub,n));den=denominators[h]
            direct_discount=np.where(c==0,0,np.where(c==1,d[0],np.where(c==2,d[1],d[2])))
            updated=(c-direct_discount)/den+removed[h]/den*prob
            prob=np.where(seen,updated,prob)
        if np.any(~np.isfinite(prob)) or np.any(prob<0) or np.any(prob>1+1e-12):raise ValueError('Invalid baseline probability')
        return prob
