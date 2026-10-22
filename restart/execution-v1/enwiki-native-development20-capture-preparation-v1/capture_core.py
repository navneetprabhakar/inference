"""Exact bounded raw XML capture from preselected verified group/page locators."""
import bz2,hashlib,json,os
from pathlib import Path

def decode(raw,receipt,remaining,check):
    if len(raw)!=receipt['compressed_bytes'] or hashlib.sha256(raw).hexdigest()!=receipt['compressed_SHA256']:raise ValueError('compressed_group_identity')
    expected=receipt['decoded_bytes']
    if not 0<expected<=remaining:raise ValueError('decoded_expected_global_cap')
    pending=raw;out=bytearray();members=0;digest=hashlib.sha256()
    while pending:
        if not pending.startswith(b'BZh'):raise ValueError('BZ2_trailing_or_member_header')
        d=bz2.BZ2Decompressor();payload=pending
        while True:
            check()
            # One explicit extra probe, never retained, diagnoses excess output;
            # exact declared expected still bounds retained decoded memory.
            chunk=d.decompress(payload,max_length=min(65536,expected-len(out)+1));payload=b''
            if len(out)+len(chunk)>expected:raise ValueError('decoded_group_excess')
            out.extend(chunk);digest.update(chunk)
            if d.eof:break
            if d.needs_input:raise ValueError('BZ2_truncated_CRC_EOF')
        pending=d.unused_data;members+=1
    if len(out)!=expected or digest.hexdigest()!=receipt['decoded_SHA256'] or members!=receipt['CRC_EOF_members']:raise ValueError('decoded_group_hash_length_member_count')
    return out

def run(profile,selection,read_group,read_header,write,check):
    limits=profile['limits'];groups=selection['groups'];selected=selection['selected'];compressed=decoded=0;records=[];seen=set()
    if len(selected)!=20 or len({r['row_ordinal'] for r in selected})!=20 or len(groups)>20:raise ValueError('exact_fixed20_unique_selection')
    if sum(g['compressed_bytes'] for g in groups)>limits['compressed_bytes'] or sum(g['decoded_bytes'] for g in groups)>limits['decoded_bytes']:raise ValueError('fixed_group_total_caps')
    header=read_header();write('original-header.xml',header)
    for group in groups:
        check();g=group['group_ordinal']
        if g in seen:raise ValueError('duplicate_group_read_forbidden')
        seen.add(g);raw=read_group(group);compressed+=len(raw)
        if compressed>limits['compressed_bytes']:raise ValueError('compressed_total_cap')
        native=decode(raw,group,limits['decoded_bytes']-decoded,check);decoded+=len(native)
        for p in [r for r in selected if r['group_ordinal']==g]:
            offset=p['group_decoded_start'];n=p['raw_XML_bytes']
            if type(offset) is not int or offset<0 or type(n) is not int or not 0<n<=limits['page_bytes'] or offset+n>len(native):raise ValueError('raw_page_locator_bounds_or_page_cap')
            body=native[offset:offset+n]
            if hashlib.sha256(body).hexdigest()!=p['raw_SHA256']:raise ValueError('raw_page_exact_XML_SHA256')
            name=f'page-{p["row_ordinal"]:08d}-{p["page_id"]}.xml';write(name,body)
            records.append({'selection':p,'raw_XML_file':name,'raw_XML_bytes':n,'raw_XML_SHA256':p['raw_SHA256'],
                'group_compressed_start':group['compressed_start'],'group_compressed_end_exclusive':group['compressed_end_exclusive'],
                'group_compressed_SHA256':group['compressed_SHA256'],'group_decoded_SHA256':group['decoded_SHA256'],'CRC_EOF_verified':True,
                'outcome':'EXACT_RAW_NATIVE_XML_CAPTURE_NO_RENDER_OR_ELIGIBILITY_DECISION'})
        del native,raw
    if len(records)!=20 or seen!={g['group_ordinal'] for g in groups}:raise ValueError('all20outcomes_and_groups')
    byid={r['selection']['row_ordinal']:r for r in records};records=[byid[p['row_ordinal']] for p in selected]
    check()
    return {'status':'COMPLETE_RAW_DEVELOPMENT20_CAPTURE_NO_ADMISSION','scope':'BIASED_FIRST128_DEVELOPMENT_NOT_ACCEPTANCE_OR_WHOLE_ARCHIVE',
        'records':records,'compressed_group_bytes_read':compressed,'decoded_group_bytes':decoded,'groups_read_once':sorted(seen),
        'source_text_changed':False,'XML_namespace_or_root_invented':False,'new_admitted_documents':0,'new_admitted_tokens':0}
