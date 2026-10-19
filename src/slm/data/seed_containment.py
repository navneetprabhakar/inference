"""Exact normalized byte containment with a vectorized candidate index."""
# Creator: Navneet Prabhakar
import unicodedata
import numpy as np


def normalized_bytes(text):
    if not isinstance(text,str):raise ValueError('Original text required')
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split()).encode('utf-8')


class PrefixIndex:
    """Hash collisions only add candidates; every full seed is byte-verified.

    Polynomial hashes enumerate every possible byte offset. No sampling, token
    boundaries, probabilistic acceptance or semantic/source-ID inference.
    """
    def __init__(self,patterns,*,width=64,base=257,max_bytes=4*1024**2):
        if type(width) is not int or width<1 or type(base) is not int or base<1 or base%2!=1 or max_bytes<width:raise ValueError('Positive width and invertible odd base required')
        self.width=width;self.max_bytes=max_bytes;self.patterns={};self.powers=np.empty(0,dtype=np.uint64);self.inverse=np.empty(0,dtype=np.uint64);self.base=base
        self._grow(width)
        if not patterns:raise ValueError('Nonempty complete seed patterns required')
        for key,raw in patterns.items():
            if not isinstance(raw,bytes) or not width<=len(raw)<=max_bytes:raise ValueError('Bounded seed bytes required')
            value=int(np.sum(np.frombuffer(raw[:width],dtype=np.uint8).astype(np.uint64)*self.powers[:width],dtype=np.uint64))
            self.patterns.setdefault(value,[]).append((key,raw))
        self.keys=np.array(sorted(self.patterns),dtype=np.uint64)

    def _grow(self,n):
        if n>self.max_bytes:raise ValueError('Normalized target exceeds byte cap')
        if len(self.powers)>=n:return
        self.powers=np.full(n,self.base,dtype=np.uint64);self.powers[0]=1;np.multiply.accumulate(self.powers,out=self.powers)
        self.inverse=np.full(n,pow(self.base,-1,1<<64),dtype=np.uint64);self.inverse[0]=1;np.multiply.accumulate(self.inverse,out=self.inverse)

    def candidates(self,raw):
        if not isinstance(raw,bytes):raise ValueError('Normalized target bytes required')
        if len(raw)>self.max_bytes:raise ValueError('Normalized target exceeds byte cap')
        if len(raw)<self.width:return
        n=len(raw);self._grow(n)
        prefix=np.empty(n+1,dtype=np.uint64);prefix[0]=0
        np.cumsum(np.frombuffer(raw,dtype=np.uint8).astype(np.uint64)*self.powers[:n],out=prefix[1:])
        values=(prefix[self.width:]-prefix[:-self.width])*self.inverse[:n-self.width+1]
        locations=np.searchsorted(self.keys,values);safe=np.minimum(locations,len(self.keys)-1)
        for offset in np.flatnonzero((locations<len(self.keys)) & (self.keys[safe]==values)):
            offset=int(offset)
            for key,pattern in self.patterns[int(values[offset])]:
                yield key,offset,raw.startswith(pattern,offset)

    def matches(self,raw):
        for key,start,full in self.candidates(raw):
            if full:yield key,start
