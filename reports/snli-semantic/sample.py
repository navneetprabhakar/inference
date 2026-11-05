"""Blind hash-sampled train-only label × agreement review."""
from collections import defaultdict
import json
import heapq
from build import DEST,HERE,digest
def sample(n=12,salt='snli-semantic-audit-1',filter_pred=None):
    groups=defaultdict(list)
    for line in (DEST/'train-candidate.jsonl').open():
        r=json.loads(line)
        if filter_pred and not filter_pred(r):continue
        k=r['annotation_tier']+'/'+r['label']
        key=digest(salt+r['pair_id'])
        heap=groups[k];rank=-int(key,16)
        if len(heap)<n:heapq.heappush(heap,(rank,r['pair_id'],r))
        elif rank>heap[0][0]:heapq.heapreplace(heap,(rank,r['pair_id'],r))
    return {k:[r for _,_,r in sorted(v,reverse=True)] for k,v in groups.items()}
if __name__=='__main__':
    for k,rows in sorted(sample().items()):
        print(k)
        for r in rows:print(r['pair_id'],r['premise'],'|',r['hypothesis'])
