"""Integrated finite calibration engine; supplied reader only, no source opener."""
import bz2,hashlib,importlib.util,json,os,sqlite3,time
from pathlib import Path
from codec import Codec

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def transcript(row):return (json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode()

class Evidence:
    def __init__(self,out,check,metadata_cap=8000000):
        self.out=Path(out);self.check=check;self.cap=metadata_cap;self.bytes=0;self.exception_bytes=0;self.events=0;self.digest=hashlib.sha256()
        self.f=(self.out/'exceptions.jsonl').open('xb')
    def exception(self,obj):
        b=transcript(obj);self.check(len(b))
        if self.bytes+len(b)>self.cap:raise ValueError('metadata_exception_cap')
        self.f.write(b);self.bytes+=len(b);self.exception_bytes+=len(b);self.events+=1;self.digest.update(b)
    def write(self,name,obj):
        b=obj if type(obj) is bytes else transcript(obj)
        self.check(len(b))
        if self.bytes+len(b)>self.cap:raise ValueError('metadata_allfiles_cap')
        with (self.out/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        self.bytes+=len(b)
    def close(self):
        self.f.flush();os.fsync(self.f.fileno());self.f.close()

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

def run(profile,selection,rows,read_at,out,check,*,fault=lambda stage:None):
    """No retained source access here until caller supplies reviewed read_at."""
    out=Path(out);limits=profile['limits'];started=clk()
    semantic=module('calibration_semantic',profile['semantic_module']);sql=module('calibration_sink',profile['sink_module'])
    sink=None;evidence=None;parser=None;receipts=[];state={'group':None,'identity':None,'pages':0}
    try:
        evidence=Evidence(out,check,limits['metadata_bytes'])
        sink=sql.Sink(out/'frame.sqlite',DB_cap=limits['DB_bytes'],max_group_pages=100,revision_cap=limits['revision_occurrences'])
        codec=Codec(sink,evidence.exception,lambda:check())
        def on_page(p):
            if state['group'] is None:raise ValueError('page_outside_indexed_group')
            state['identity'].update(transcript([p['page_ordinal'],p['page_ID'],p['title']]))
            codec.page(p);state['pages']+=1
        parser=semantic.Metadata(on_page,codec.revision,decoded_cap=limits['decoded_bytes'],
             page_cap=selection['rows'],boundary_flush_cap=len(selection['groups']))
        header=bytearray()
        def header_feed(b):
            if len(header)+len(b)>65536:raise ValueError('actual_header_decoded_cap')
            header.extend(b);parser.feed(b)
        n=selection['header_bytes'];check(n)
        if n<=0 or n>limits['max_group_compressed_bytes']:raise ValueError('header_compressed_cap')
        header_raw=read_at(0,n);hr=decode(header_raw,header_feed,limits['decoded_bytes'],lambda:check())
        if parser.pages or parser.current or len(parser.stack)!=1 or not parser.siteinfo_seen:raise ValueError('actual_header_schema_or_boundary')
        decoded=hr['decoded_bytes'];compressed=n
        evidence.write('original-header.xml',bytes(header));fault('after_header')
        for group in selection['groups']:
            check();g=group['group_ordinal'];begin=group['compressed_start'];end=group['compressed_end_exclusive'];n=end-begin
            if n<=0 or n>limits['max_group_compressed_bytes'] or begin!=compressed or end>limits['compressed_bytes']:raise ValueError('compressed_group_budget_before_IO')
            expected=rows[group['first_row_ordinal']-1:group['last_row_ordinal']]
            tuples=[(r[0],r[2],r[3]) for r in expected]
            if len(expected)!=group['index_rows']:raise ValueError('frozen_group_row_count')
            sink.begin_group(g,begin,end,tuples);state['group']=g;state['identity']=hashlib.sha256();state['pages']=0;codec.group_base=decoded
            fault('after_group_begin');read_start=clk();raw=read_at(begin,n);read_seconds=clk()-read_start;compressed+=len(raw)
            phase=clk();dr=decode(raw,parser.feed,limits['decoded_bytes']-decoded,lambda:check());fault('after_CRC')
            boundary=parser.flush_boundary();fault('after_boundary_flush')
            parse_seconds=clk()-phase
            expected_digest=hashlib.sha256(b''.join(transcript(list(x)) for x in tuples)).hexdigest()
            if state['pages']!=len(tuples) or state['identity'].hexdigest()!=expected_digest:raise ValueError('actual_native_identity_transcript_mismatch')
            if boundary['siteinfo_base_status']!='VERIFIED_HTTPS_ENWIKI_BASE' or boundary['root_holds']:raise ValueError('global_header_source_schema_hold')
            # Atomic sink commit occurs only after decodeCRC + real SAX group
            # boundary + exact every-ID/title/order + rawpage span reconciliation.
            fault('before_group_commit');commit_start=clk();durable=sink.end_group(dr['decoded_bytes'],bytes.fromhex(dr['decoded_SHA256']));commit_seconds=clk()-commit_start;fault('after_group_commit')
            receipts.append({'group_ordinal':g,'compressed_start':begin,'compressed_end_exclusive':end,
                'decoded_global_start':decoded,**dr,'native_pages':state['pages'],
                'actual_native_identity_SHA256':state['identity'].hexdigest(),
                'frozen_index_identity_SHA256':expected_digest,'durable':durable,
                'compressed_read_seconds':read_seconds,'decode_parse_SQL_callbacks_seconds':parse_seconds,
                'atomic_group_commit_seconds':commit_seconds,'group_processing_seconds':clk()-phase})
            decoded+=dr['decoded_bytes'];state['group']=None
        final=parser.finish_prefix();check();fault('before_final_integrity')
        if compressed!=selection['compressed_prefix_end_exclusive'] or sink.pages!=selection['rows'] or sink.groups!=len(selection['groups']):raise ValueError('exact_calibration_coverage')
        if sink.db.execute('PRAGMA integrity_check').fetchone()!=('ok',) or sink.db.execute('PRAGMA foreign_key_check').fetchone() is not None:raise ValueError('SQLite_integrity_or_FK')
        counts={'pages':sink.pages,'revision_occurrences':sink.revisions,'groups':sink.groups,
          'ns0_nonredirect':sink.db.execute('SELECT count(*) FROM pages WHERE namespace=0 AND (flags & 1)=0').fetchone()[0],
          'namespace_counts':sink.db.execute('SELECT namespace,count(*) FROM pages GROUP BY namespace').fetchall(),
          'flag_counts':sink.db.execute('SELECT flags,count(*) FROM pages GROUP BY flags').fetchall()}
        sink.close();sink=None
        evidence.write('codec.json',codec.summary());evidence.write('header-summary.json',final)
        evidence.write('group-receipts.json',{'header':hr,'groups':receipts})
        exception_summary={'events':evidence.events,'bytes':evidence.exception_bytes,'metadata_total_bytes':evidence.bytes,'ordered_exception_SHA256':evidence.digest.hexdigest(),'normal_perrevision_JSON_spool':False}
        evidence.close();evidence=None
        return {'status':'COMPLETE_FIRST128_TERMINAL_PREFIX_CALIBRATION_NO_ADMISSION','counts':counts,
            'compressed_prefix_bytes_read':compressed,'decoded_prefix_bytes':decoded,
            'scope':'PREFIX_ONLY_BIASED_ENGINEERING_NOT_SAMPLE_OR_FULL_ARCHIVE',
            'actual_root_closed':False,'no_invented_XML_bytes':True,
            'all_selected_BZ2_CRC_EOF_index_ID_title_order':True,
            'exceptions':exception_summary,'elapsed_engine_seconds':clk()-started,
            'new_admitted_documents':0,'new_admitted_tokens':0}
    finally:
        if evidence is not None:evidence.close()
        if sink is not None:sink.close()
