"""Frozen metadata-only development selection; no acceptance/probability claim."""
import hashlib
SEED='enwiki-first128-development20-v1-20261021'
BUCKETS=[(512,1024),(1024,2048),(2048,4096),(4096,8192),(8192,16384),(16384,32768),(32768,65536),(65536,1000001)]

def priority(role,bucket,row):
    preimage=f'{SEED}\n{role}\n{bucket}\n{row["row_ordinal"]}'
    return hashlib.sha256(preimage.encode('utf8')).hexdigest()

def select(rows):
    selected=[];used=set();groups=set();namespaces=set()
    def choose(role,bucket,candidates,quota,namespace_diverse=False):
        candidates=sorted(candidates,key=lambda r:(priority(role,bucket,r),r['row_ordinal']))
        for _ in range(quota):
            available=[r for r in candidates if r['row_ordinal'] not in used]
            if not available:raise ValueError('metadata_selection_quota_unavailable')
            # Stable greedy group diversity, then nonzero namespace diversity;
            # reuse only when remaining exact role/bucket lacks alternatives.
            pool=[r for r in available if r['group_ordinal'] not in groups] or available
            if namespace_diverse:pool=[r for r in pool if r['namespace'] not in namespaces] or pool
            row=pool[0];selected.append({**row,'selection_role':role,'raw_size_bucket':bucket,'priority_SHA256':priority(role,bucket,row),'group_was_new':row['group_ordinal'] not in groups})
            used.add(row['row_ordinal']);groups.add(row['group_ordinal']);namespaces.add(row['namespace'])
    for low,high in BUCKETS:
        choose('ns0_nonredirect',f'[{low},{high})',[r for r in rows if r['namespace']==0 and not(r['flags']&1) and low<=r['raw_XML_bytes']<high],2)
    choose('ns0_redirect','raw<=1000000',[r for r in rows if r['namespace']==0 and r['flags']&1 and 0<r['raw_XML_bytes']<=1000000],2)
    choose('nonzero_namespace','raw<=1000000',[r for r in rows if r['namespace']!=0 and 0<r['raw_XML_bytes']<=1000000],2,True)
    if len(selected)!=20 or len(used)!=20:raise ValueError('exact20selection')
    return selected
