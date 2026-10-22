"""Pure bytes helper. Returns one corrected chapter in memory; never writes corpus."""
import hashlib

def sha(x): return hashlib.sha256(x).hexdigest()
def apply(data, patches, expected_sha256):
    if sha(data)!=expected_sha256: raise ValueError('chapter_hash_mismatch')
    ordered=sorted(patches,key=lambda p:p['derivative_start_byte'])
    previous_end=-1
    for p in ordered:
        a,b=p['derivative_start_byte'],p['derivative_end_byte']
        if type(a) is not int or type(b) is not int or not 0<=a<b<=len(data): raise ValueError('offset_bounds')
        if a<previous_end: raise ValueError('overlapping_or_duplicate_join')
        old=data[a:b]
        if old.decode('ascii')!=p['exact_old_whitespace'] or sha(old)!=p['old_whitespace_sha256']: raise ValueError('whitespace_binding')
        if any(x not in b' \t\r\n' for x in old) or b'\n' not in old: raise ValueError('non_whitespace_or_not_linebreak')
        if p['replacement_ascii']!=' ': raise ValueError('nonapproved_replacement')
        if a==0 or b==len(data) or data[a-1] in b' \t\r\n' or data[b] in b' \t\r\n':raise ValueError('not_internal_maximal_whitespace')
        previous_end=b
    out=data
    for p in reversed(ordered):out=out[:p['derivative_start_byte']]+b' '+out[p['derivative_end_byte']:]
    if b''.join(out.split())!=b''.join(data.split()):raise ValueError('nonwhitespace_changed')
    return out
