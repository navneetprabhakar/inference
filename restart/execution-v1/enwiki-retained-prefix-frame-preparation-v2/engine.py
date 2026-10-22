"""Integrated finite calibration engine; supplied reader only, no source opener."""
import bz2,hashlib,importlib.util,json,os,sqlite3,time
from pathlib import Path
from codec import Codec

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def transcript(row):return (json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode()

class Evidence:
    def __init__(self,out,check,metadata_cap):
        self.out=Path(out);self.check=check;self.cap=metadata_cap;self.bytes=0;self.exception_bytes=0;self.events=0;self.digest=hashlib.sha256();self.group_count=0;self.group_bytes=0;self.group_digest=hashlib.sha256()
        self.f=(self.out/'exceptions.jsonl').open('xb');self.groups=(self.out/'group-receipts.jsonl').open('xb')
    def append(self,obj,group=False):
        b=transcript(obj);self.check(len(b))
        if self.bytes+len(b)>self.cap:raise ValueError('combined_metadata_prewrite_cap')
        stream=self.groups if group else self.f;stream.write(b);self.bytes+=len(b)
        if group:self.group_count+=1;self.group_bytes+=len(b);self.group_digest.update(b);stream.flush();os.fsync(stream.fileno())
        else:self.exception_bytes+=len(b);self.events+=1;self.digest.update(b)
    def exception(self,obj):self.append(obj)
    def write(self,name,obj):
        b=obj if type(obj) is bytes else transcript(obj);self.check(len(b))
        if self.bytes+len(b)>self.cap:raise ValueError('combined_metadata_prewrite_cap')
        with (self.out/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        self.bytes+=len(b)
    def close(self):
        for f in (self.f,self.groups):
            if not f.closed:f.flush();os.fsync(f.fileno());f.close()


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

def run(profile,group_stream,read_at,out,check,*,fault=lambda stage:None):
    """No retained source access here until caller supplies reviewed read_at."""
    out=Path(out);limits=profile['limits'];selection=profile['selection'];started=clk()
    semantic=module('calibration_semantic',profile['semantic_module']);sql=module('calibration_sink',profile['sink_module']);titles=module('calibration_titles',profile['title_decoder'])
    sink=None;evidence=None;parser=None;state={'group':None,'identity':None,'pages':0,'expected':None}
    try:
        evidence=Evidence(out,check,limits['metadata_bytes'])
        sink=sql.Sink(out/'frame.sqlite',DB_cap=limits['DB_bytes'],max_group_pages=100,revision_cap=limits['revision_occurrences'])
        codec=Codec(sink,evidence.exception,lambda:check())
        def on_page(p):
            if state['group'] is None:raise ValueError('page_outside_indexed_group')
            i=state['pages'];expected=state['expected']
            if i>=len(expected):raise ValueError('ordered_native_index_identity_extra_page')
            e=expected[i]
            if (p['page_ordinal'],p['page_ID'],p['title'])!=e:
                detail={'group':state['group'],'expected_ordinal':e[0],'actual_ordinal':p['page_ordinal'],'expected_page_ID':e[1],'actual_page_ID':p['page_ID'],
                    'expected_semantic_title_SHA256':hashlib.sha256(e[2].encode()).hexdigest(),'actual_native_title_SHA256':hashlib.sha256(p['title'].encode()).hexdigest()}
                raise ValueError('ordered_native_index_identity_mismatch:'+json.dumps(detail,sort_keys=True,separators=(',',':')))
            state['identity'].update(transcript([p['page_ordinal'],p['page_ID'],p['title']]))
            codec.page(p);state['pages']+=1
        parser=semantic.Metadata(on_page,codec.revision,decoded_cap=limits['decoded_bytes'],
             page_cap=selection['rows'],boundary_flush_cap=selection['groups'])
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
        decoder_hash=hashlib.sha256(Path(profile['title_decoder']).read_bytes()).hexdigest()
        evidence.write('header-receipt.json',hr)
        for group,expected in group_stream():
            check();g=group['group_ordinal'];begin=group['compressed_start'];end=group['compressed_end_exclusive'];n=end-begin
            if n<=0 or n>limits['max_group_compressed_bytes'] or begin!=compressed or end>limits['compressed_bytes']:raise ValueError('compressed_group_budget_before_IO')
            projected=[titles.decode_once(r[3]) for r in expected]
            tuples=[(r[0],r[2],t['semantic_expected_title']) for r,t in zip(expected,projected)]
            raw_identity=hashlib.sha256(b''.join(transcript([r[0],r[2],r[3]]) for r in expected)).hexdigest()
            reference_count=sum(t['references_decoded_once'] for t in projected)
            if len(expected)!=group['index_rows']:raise ValueError('frozen_group_row_count')
            sink.begin_group(g,begin,end,tuples);state['group']=g;state['identity']=hashlib.sha256();state['pages']=0;state['expected']=tuples;codec.group_base=decoded
            fault('after_group_begin');read_start=clk();raw=read_at(begin,n);read_seconds=clk()-read_start;compressed+=len(raw)
            phase=clk();dr=decode(raw,parser.feed,limits['decoded_bytes']-decoded,lambda:check());fault('after_CRC')
            boundary=parser.flush_boundary();fault('after_boundary_flush')
            parse_seconds=clk()-phase
            expected_digest=hashlib.sha256(b''.join(transcript(list(x)) for x in tuples)).hexdigest()
            if state['pages']!=len(tuples) or state['identity'].hexdigest()!=expected_digest:raise ValueError('actual_native_identity_transcript_mismatch')
            if boundary['siteinfo_base_status']!='VERIFIED_HTTPS_ENWIKI_BASE' or boundary['root_holds']:raise ValueError('global_header_source_schema_hold')
            # Atomic sink commit occurs only after decodeCRC + real SAX group
            # boundary + exact every-ID/title/order + rawpage span reconciliation.
            check(force=True);fault('before_group_commit');commit_start=clk();durable=sink.end_group(dr['decoded_bytes'],bytes.fromhex(dr['decoded_SHA256']));commit_seconds=clk()-commit_start;fault('after_group_commit')
            evidence.append({'group_ordinal':g,'compressed_start':begin,'compressed_end_exclusive':end,
                'decoded_global_start':decoded,**dr,'native_pages':state['pages'],
                'actual_native_identity_SHA256':state['identity'].hexdigest(),
                'frozen_index_identity_SHA256':expected_digest,'raw_index_identity_SHA256':raw_identity,'expected_title_representation':'XML10_TEXT_ENTITIES_AND_NUMERIC_ONCE','references_decoded_once':reference_count,'title_decoder_SHA256':decoder_hash,'raw_index_lines_SHA256':group['raw_index_lines_SHA256'],'durable':durable,
                'compressed_read_seconds':read_seconds,'decode_parse_SQL_callbacks_seconds':parse_seconds,
                'atomic_group_commit_seconds':commit_seconds,'group_processing_seconds':clk()-phase},group=True)
            check(force=True)
            decoded+=dr['decoded_bytes'];state['group']=None
        final=parser.finish_prefix();check();fault('before_final_integrity')
        if compressed!=selection['compressed_prefix_end_exclusive'] or sink.pages!=selection['rows'] or sink.groups!=selection['groups']:raise ValueError('exact_calibration_coverage')
        if sink.db.execute('PRAGMA integrity_check').fetchone()!=('ok',) or sink.db.execute('PRAGMA foreign_key_check').fetchone() is not None:raise ValueError('SQLite_integrity_or_FK')
        counts={'pages':sink.pages,'revision_occurrences':sink.revisions,'groups':sink.groups,
          'ns0_nonredirect':codec.ns0_nonredirect,
          'namespace_counts':sorted(codec.namespace_counts.items()),
          'flag_counts':sorted(codec.page_flag_counts.items())}
        if evidence.group_count!=sink.groups:raise ValueError('streamed_group_receipt_coverage')
        if sum(codec.namespace_counts.values())!=sink.pages or sum(codec.page_flag_counts.values())!=sink.pages:raise ValueError('bounded_summary_counter_coverage')
        sink.close();sink=None
        evidence.write('codec.json',codec.summary());evidence.write('header-summary.json',final)
        exception_summary={'events':evidence.events,'bytes':evidence.exception_bytes,'metadata_total_bytes':evidence.bytes,'ordered_exception_SHA256':evidence.digest.hexdigest(),'normal_perrevision_JSON_spool':False,'group_receipt_count':evidence.group_count,'group_receipt_bytes':evidence.group_bytes,'ordered_group_receipts_SHA256':evidence.group_digest.hexdigest()}
        evidence.close()
        if (out/'exceptions.jsonl').stat().st_size!=evidence.exception_bytes or (out/'group-receipts.jsonl').stat().st_size!=evidence.group_bytes:raise ValueError('streamed_metadata_actual_byte_reconciliation')
        evidence=None
        return {'status':'COMPLETE_RETAINED_PREFIX_FRAGMENT_FRAME_NO_ADMISSION','counts':counts,
            'compressed_prefix_bytes_read':compressed,'decoded_prefix_bytes':decoded,
            'scope':'RETAINED_PREFIX_FRAGMENT_NOT_FULL_ARCHIVE_OR_QUALITY_FRAME',
            'actual_root_closed':False,'no_invented_XML_bytes':True,
            'native_page_ID_uniqueness_scope':'EXACT_ORDERED_MATCH_TO_VERIFIED_GLOBAL_UNIQUE_INDEX_SUBSET_NOT_FULL_NATIVE_ARCHIVE',
            'all_selected_BZ2_CRC_EOF_index_ID_title_order':True,
            'exceptions':exception_summary,'elapsed_engine_seconds':clk()-started,
            'new_admitted_documents':0,'new_admitted_tokens':0}
    finally:
        if evidence is not None:evidence.close()
        if sink is not None:sink.close()
