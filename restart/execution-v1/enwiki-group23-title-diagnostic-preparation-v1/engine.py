import bz2,hashlib,importlib.util,json,os,time
from pathlib import Path

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def decode(raw,feed,remaining,check):
    pending=raw;count=0;n=0;h=hashlib.sha256()
    while pending:
        if not pending.startswith(b'BZh'):raise ValueError('BZ2_member_or_trailing_data')
        d=bz2.BZ2Decompressor();payload=pending
        while True:
            check()
            if n>=remaining:raise ValueError('decoded_cap_no_probe')
            b=d.decompress(payload,max_length=min(65536,remaining-n));payload=b''
            n+=len(b);h.update(b)
            if b:feed(b)
            if d.eof:break
            if d.needs_input:raise ValueError('BZ2_truncated_missing_CRC_EOF')
        pending=d.unused_data;count+=1
    return {'decoded_bytes':n,'decoded_SHA256':h.hexdigest(),'compressed_bytes':len(raw),
            'compressed_SHA256':hashlib.sha256(raw).hexdigest(),'CRC_EOF_members':count,'trailing_absent':True}

def run(profile,selection,rows,read_at,out,check):
 semantic=module('diagnostic_semantic',profile['semantic_module']);observed=[];revisions=[0]
 def rev(r):revisions[0]+=1
 def page(p):
  i=p['page_ordinal']-1
  if not 0<=i<len(rows):raise ValueError('native_page_count_over100')
  r=rows[i]
  if p['page_ID']!=r[2]:raise ValueError('native_index_ID_order_mismatch')
  observed.append({'native_local_ordinal':i+1,'expected_global_ordinal':r[0],'native_page_ID':p['page_ID'],'expected_page_ID':r[2],
    'native_title':p['title'],'raw_index_title_lexeme':r[3],'raw_index_line_SHA256':r[4],
    'titles_literal_equal':p['title']==r[3],'native_raw_XML':p['raw_XML'],'holds':p['holds']})
 parser=semantic.Metadata(page,rev,decoded_cap=profile['limits']['decoded_bytes'],page_cap=100,boundary_flush_cap=1)
 header=decode(read_at(0,570),parser.feed,profile['limits']['decoded_bytes'],lambda:check())
 if parser.pages or parser.current or len(parser.stack)!=1 or not parser.siteinfo_seen:raise ValueError('actual_header_schema_boundary')
 g=profile['target_group'];n=g['compressed_end_exclusive']-g['compressed_start']
 if not 0<n<=2000000 or 570+n>2000000:raise ValueError('compressed_preIO_cap')
 group=decode(read_at(g['compressed_start'],n),parser.feed,profile['limits']['decoded_bytes']-header['decoded_bytes'],lambda:check())
 summary=parser.finish_prefix()
 if len(observed)!=100 or summary['siteinfo_base_status']!='VERIFIED_HTTPS_ENWIKI_BASE' or summary['root_holds']:raise ValueError('exact100_native_header_prefix_boundary')
 result={'status':'COMPLETE_GROUP23_IDENTITY_DIAGNOSTIC_NO_ADMISSION','header':header,'target_group':g,'group':group,'observed_pages':100,'revision_occurrences':revisions[0],
 'raw_index_title_mismatches':sum(not r['titles_literal_equal'] for r in observed),'observed':observed,
 'source_scope':'Actual compressed header plus original group23 only; root remains open, no invented XML bytes.',
 'no_index_decoder_or_normalization_applied':True,'no_wikitext_or_revision_body_output':True,'whole_publisher_archive_verified':False,'new_admitted_documents':0,'new_admitted_tokens':0}
 # Diagnostic identities only; no complete semantic page/revision object output.
 check(len(json.dumps(result,ensure_ascii=False).encode()))
 return result
