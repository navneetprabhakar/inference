"""Select bounded row groups without reading payloads or changing their limits."""
# Creator: Navneet Prabhakar
from slm.data.schema import digest


def compatible_group(reader,index):
    g=reader.metadata.row_group(index);cs=[g.column(i) for i in range(g.num_columns)]
    if not cs:return None
    spans=[(c.dictionary_page_offset if c.has_dictionary_page else c.data_page_offset,c.total_compressed_size) for c in cs]
    start=min(s for s,n in spans);stop=max(s+n for s,n in spans);declared=sum(c.total_uncompressed_size for c in cs)
    lim=reader.transport.limits
    if (g.num_rows>lim.group_rows or declared<0 or declared>lim.group_declared_uncompressed_bytes
        or stop-start>lim.group_compressed_bytes or start<4 or stop>reader.footer_start
        or any(c.file_path or c.total_uncompressed_size<0 or n<=0 for c,(s,n) in zip(cs,spans))):return None
    return dict(index=index,rows=g.num_rows,declared_bytes=declared,compressed_interval_bytes=stop-start)


def select(censuses,seed,total,per_file,excluded):
    if type(total) is not int or type(per_file) is not int or min(total,per_file)<1:raise ValueError('Positive selection caps required')
    candidates=[]
    for name,groups in censuses.items():
        eligible=[g for g in groups if (name,g['index']) not in excluded]
        ranked=sorted(eligible,key=lambda g:digest([seed,name,g['index']]))[:per_file]
        candidates.extend(dict(file=name,group=g) for g in ranked)
    return sorted(candidates,key=lambda r:digest([seed,r['file'],r['group']['index']]))[:total]
