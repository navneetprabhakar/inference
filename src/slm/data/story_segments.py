"""Byte-exact delimited story records from complete files or sparse ranges."""
# Creator: Navneet Prabhakar
import hashlib

DELIMITER = b'<|endoftext|>'


def segments(raw, start, total, *, max_records=200000, max_story_bytes=1048576):
    if not isinstance(raw, bytes) or type(start) is not int or type(total) is not int or start < 0 or start + len(raw) > total:
        raise ValueError('Valid original byte interval required')
    if DELIMITER not in raw:
        raise ValueError('Expected story delimiter absent')
    boundaries=[];cursor=0
    while True:
        found=raw.find(DELIMITER,cursor)
        if found < 0:break
        boundaries.append((cursor,found,'delimiter'));cursor=found+len(DELIMITER)
        if len(boundaries)>max_records+1:raise ValueError('Story count cap exceeded')
    if start+len(raw)==total:boundaries.append((cursor,len(raw),'file_eof'))
    records=[]
    for i,(left,right,end_kind) in enumerate(boundaries):
        if i==0 and start>0:continue  # Left edge may be a partial UTF-8/story fragment.
        body=raw[left:right]
        if len(body)>max_story_bytes:raise ValueError('Complete story exceeds byte cap')
        text=body.decode('utf-8',errors='strict')
        if not text.strip():continue
        records.append(dict(start=start+left,end=start+right,text=text,end_kind=end_kind,
                            raw_text_sha256=hashlib.sha256(body).hexdigest()))
        if len(records)>max_records:raise ValueError('Story count cap exceeded')
    return records
