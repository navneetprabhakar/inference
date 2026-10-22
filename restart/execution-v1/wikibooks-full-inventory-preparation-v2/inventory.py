"""Offline full-source inventory worker. Parent reviews pins before launch.

Stores compact provenance and text/block hashes only; no corpus admission,
HTML/fulltext duplication, network or model operations. Run via supervisor.py.
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

from shared_clock import shared_clock
import extraction_core as core

CAPS={'decoded_bytes':12_000_000_000,'output_bytes':1_000_000_000,
      'seconds':900,'records':500_000,'parsed_record_bytes':4_194_304,
      'oversize_chunk_bytes':65_536,'rss_target_bytes':512_000_000,
      'rss_hard_bytes':1_000_000_000,'tar_members':64,'member_name_bytes':4096}
FREE_RESERVE=20*1024**3+16_000_000_000
TERMINAL_RESERVE=1_048_576
INTAKE_ROOT=Path(__file__).resolve().parents[1]/'m2-intake'
PROCESSED_CEILING=64_000_000_000
ARCHIVE_SHA256='361fb441fe35d13be56c4eca22a09df6868a663e5d7f3b1ed2a665e332a4d263'
PIN_PATH=Path(__file__).with_name('code-pins.json')

class StopInventory(ValueError):
    def __init__(self,reason,diagnostic=None):
        super().__init__(reason);self.diagnostic=diagnostic

def digest(b):return hashlib.sha256(b).hexdigest()
def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def output_size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def check_processed_reservation(output,additional):
    if not output.resolve().is_relative_to(INTAKE_ROOT.resolve()):raise StopInventory('output_outside_parent_intake_budget_root')
    if output_size(INTAKE_ROOT)+additional>PROCESSED_CEILING:raise StopInventory('combined_intake64GB_processed_ceiling')

def terminal_write(path,result,cap,kind='worker'):
    """Fixed-size preallocated terminal slot; never grows at a hard stop."""
    slot=min(384*1024 if kind=='worker' else 128*1024,cap//8)
    if slot<8192:raise StopInventory('terminal_slot_budget_too_small')
    payload=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    if len(payload)>slot:
        result={'status':'PARTIAL_INVENTORY_NO_ADMISSION','reason':'terminal_metadata_exceeded_fixed_slot',
                'original_status':result.get('status'),'original_reason':result.get('reason'),
                'new_admitted_documents':0,'new_admitted_tokens':0}
        payload=(json.dumps(result,indent=2)+'\n').encode()
    if not path.exists():
        if output_size(path.parent)+slot>cap:raise StopInventory('cannot_allocate_terminal_slot_within_output_cap')
        with path.open('xb') as f:f.write(b' '*slot)
    if path.stat().st_size!=slot:raise StopInventory('terminal_slot_size_mismatch')
    with path.open('r+b') as f:
        f.write(payload+b' '*(slot-len(payload)));f.flush();os.fsync(f.fileno())
    return result
def check_pins():
    pins=json.loads(PIN_PATH.read_text())
    for name,h in pins['sha256'].items():
        if file_sha(PIN_PATH.parent/name)!=h:raise StopInventory('code_pin_mismatch:'+name)
    return pins

class Guards:
    def __init__(self,output,start,limits=CAPS,reserve=FREE_RESERVE):
        self.output=output;self.start=start;self.limits=limits;self.reserve=reserve
    def check(self,additional=0):
        if shared_clock()-self.start>=self.limits['seconds']:raise StopInventory('elapsed_time_cap')
        if output_size(self.output)+additional>self.limits['output_bytes']-TERMINAL_RESERVE:raise StopInventory('aggregate_output_byte_cap')
        if shutil.disk_usage(self.output).free<self.reserve+additional:raise StopInventory('disk_weights_free_floor')

class Decoded:
    """Counts every decoded byte: headers, member data, padding and tail."""
    def __init__(self,f,guards):self.f=f;self.guards=guards;self.n=0
    def read(self,n):
        self.guards.check()
        remaining=self.guards.limits['decoded_bytes']-self.n
        if remaining<=0:raise StopInventory('decoded_byte_cap')
        b=self.f.read(min(n,remaining));self.n+=len(b);return b
    def exact(self,n):
        parts=[];remaining=n
        while remaining:
            b=self.read(min(remaining,65536))
            if not b:raise StopInventory('truncated_tar_container')
            parts.append(b);remaining-=len(b)
        return b''.join(parts)

class MemberReader:
    def __init__(self,decoded,size):self.decoded=decoded;self.remaining=size;self.buffer=b''
    def readline(self,limit):
        parts=[];size=0
        while size<limit:
            if not self.buffer and self.remaining:
                b=self.decoded.read(min(65536,self.remaining))
                if not b:raise StopInventory('truncated_tar_member')
                self.remaining-=len(b);self.buffer=b
            if not self.buffer:break
            take=min(len(self.buffer),limit-size)
            newline=self.buffer.find(b'\n',0,take)
            if newline>=0:take=newline+1
            part=self.buffer[:take];self.buffer=self.buffer[take:];parts.append(part);size+=len(part)
            if part.endswith(b'\n'):break
        return b''.join(parts)
    @property
    def at_eof(self):return not self.buffer and not self.remaining

def records_in_member(reader,member,ordinal,limits=CAPS):
    line=0
    while not reader.at_eof:
        first=reader.readline(limits['parsed_record_bytes']+1)
        if not first:break
        line+=1
        if len(first)<=limits['parsed_record_bytes']:
            if first.strip():yield {'member':member,'member_ordinal':ordinal,'line':line,'record_bytes':len(first),'record_sha256':digest(first),'raw':first}
            continue
        h=hashlib.sha256(first);n=len(first);nonblank=bool(first.strip());complete=first.endswith(b'\n')
        try:
            while not complete:
                b=reader.readline(limits['oversize_chunk_bytes']);h.update(b);n+=len(b);nonblank=nonblank or bool(b.strip())
                complete=not b or b.endswith(b'\n')
        except Exception as exc:
            raise StopInventory('bound_or_failure_mid_oversize_record',{'member':member,'member_ordinal':ordinal,'line':line,'record_bytes_returned':n,'sha256_of_returned_prefix':h.hexdigest(),'record_complete':False}) from exc
        if nonblank:yield {'member':member,'member_ordinal':ordinal,'line':line,'record_bytes':n,'record_sha256':h.hexdigest(),'raw':None,'hold':'oversize_record_not_parsed','record_complete':True}

def tar_records(path,guards,stats):
    with gzip.open(path,'rb') as gz:
        decoded=Decoded(gz,guards)
        try:
            ordinal=0
            while True:
                header=decoded.exact(512)
                if header==b'\0'*512:
                    if decoded.exact(512)!=b'\0'*512:raise StopInventory('missing_second_tar_end_block')
                    # Finish the gzip stream to verify its CRC/trailer; only
                    # zero tar padding is allowed beyond the terminal blocks.
                    while True:
                        b=decoded.read(65536)
                        if not b:break
                        if any(b):raise StopInventory('nonzero_data_after_tar_end')
                    stats['tar_end_blocks_verified']=True;stats['gzip_eof_crc_verified']=True;return
                try:member=tarfile.TarInfo.frombuf(header,'utf-8','strict')
                except Exception as exc:raise StopInventory('invalid_tar_header') from exc
                pathparts=PurePosixPath(member.name)
                if pathparts.is_absolute() or '..' in pathparts.parts:raise StopInventory('unsafe_tar_member_path')
                ordinal+=1
                if ordinal>guards.limits['tar_members']:raise StopInventory('tar_member_count_cap')
                if member.isdir():
                    if member.size:raise StopInventory('nonempty_tar_directory')
                    continue
                if not member.isfile():raise StopInventory('unsupported_tar_member_type')
                if not member.name.endswith(('.ndjson','.json')):raise StopInventory('unknown_tar_member_format')
                if len(member.name.encode())>guards.limits['member_name_bytes']:raise StopInventory('tar_member_name_bound')
                stats['members'].append({'ordinal':ordinal,'name_display':member.name[:256],'name_display_truncated':len(member.name)>256,'full_name_sha256':digest(member.name.encode()),'declared_bytes':member.size,'header_sha256':digest(header)})
                reader=MemberReader(decoded,member.size)
                yield from records_in_member(reader,member.name,ordinal,guards.limits)
                if not reader.at_eof:raise StopInventory('member_not_fully_consumed')
                padding=(-member.size)%512
                if padding and decoded.exact(padding)!=b'\0'*padding:raise StopInventory('nonzero_tar_member_padding')
        finally:stats['actual_decoded_bytes']=decoded.n

def notice_flags(text,source_kind='rendered_text'):
    result=[]
    pattern=r'copyright|all rights reserved|permission is hereby granted|redistribution and use|GNU (?:general public|lesser general|free documentation)|licensed under|licen[cs]e (?:notice|agreement)'
    for m in re.finditer(pattern,text,re.I):
        start=max(0,m.start()-120);end=min(len(text),m.end()+160);span=text[start:end]
        result.append({'source_kind':source_kind,'start':start,'end':end,'exact_span':span,'span_sha256':digest(span.encode()),'reason':'potential_third_party_notice_requires_review_not_blanket_rights_decision'})
        if len(result)==16:break
    return result

def open_db(path,limits):
    os.environ['SQLITE_TMPDIR']=str(path.parent)
    db=sqlite3.connect(path)
    db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL')
    db.execute('pragma cache_size=-4096');db.execute('pragma temp_store=FILE')
    db.execute('pragma max_page_count='+str(limits['output_bytes']//4096))
    db.execute('create table records (ordinal integer primary key,member integer,line integer,source_hash text,record_bytes integer,page_id integer,revision_id integer,title text,depth integer,family text,data text,unique(member,line))')
    db.execute('create unique index page_identity on records(page_id) where page_id is not null')
    db.execute('create index canonical_order on records(depth desc,title collate binary,page_id)')
    db.execute('create table blocks (page_id integer,ordinal integer,hash text,characters integer,primary key(page_id,ordinal))')
    db.execute('create table owners (family text,hash text,page_id integer,primary key(family,hash))')
    db.execute('create table final_holds (page_id integer primary key,holds text,overlap_owners text)')
    db.commit();return db

def compact(r,c,loc,baseline):
    raw_wikitext=r['article_body'].get('wikitext')
    notices=notice_flags(c['text'])
    if isinstance(raw_wikitext,str):notices+=notice_flags(raw_wikitext,'original_wikitext')
    prior=baseline.get((c['page_id'],c['revision_id'],c['html_sha256']),[])
    holds=sorted(set(c['holds']+prior))
    row={
        'archive_sha256':ARCHIVE_SHA256,**{k:v for k,v in loc.items() if k!='raw'},
        **{k:c[k] for k in ['page_id','revision_id','title','url','book_root_title','family_id','html_sha256']},
        'date_modified':r.get('date_modified'),'date_created':r.get('date_created'),
        'page_history_url':c['url']+'?action=history',
        'revision_url':'https://en.wikibooks.org/w/index.php?oldid='+str(c['revision_id']),
        'wikitext_present':isinstance(raw_wikitext,str),'wikitext_sha256':digest(raw_wikitext.encode()) if isinstance(raw_wikitext,str) else None,
        'license_original_metadata':r['license'],'license_exception_flags':['exact_project_snapshot_page_exception_reconciliation_pending'],
        'family_resolution_flags':['slash_root_provisional_alias_and_transclusion_resolution_pending'],
        'templates_original_metadata':r.get('templates',[]),'redirects_original_metadata':r.get('redirects',[]),
        'internal_dependency_links':c['internal_dependency_links'],
        'renderer_sha256':core.RENDERER_SHA256,'extracted_text_sha256':c['text_sha256'],
        'text_unicode_characters':len(c['text']),'text_UTF8_bytes':len(c['text'].encode()),
        'length_basis':'Rendered DOM text; not raw HTML bytes or final-tokenizer token count.',
        'potential_third_party_notice_flags':notices,'structural_holds':holds,'prior_v3_holds':prior,
        'language_metadata':r.get('in_language'),'training_admitted':False,
    }
    return row

def finalize(db,guards,stats):
    for (page,family,data) in db.execute('select page_id,family,data from records where page_id is not null order by depth desc,title collate binary,page_id'):
        guards.check(131072);r=json.loads(data);holds=list(r['structural_holds']);overlaps=[]
        blocks=list(db.execute('select hash,characters from blocks where page_id=? order by ordinal',(page,)))
        if not holds:
            for h,n in blocks:
                if n<80:continue
                owner=db.execute('select page_id from owners where family=? and hash=?',(family,h)).fetchone()
                if owner:overlaps.append({'block_sha256':h,'owner_page_id':owner[0]})
            if overlaps:holds.append('substantive_block_duplicates_canonical_chapter')
            else:
                for h,n in blocks:
                    if n>=80:db.execute('insert or ignore into owners values (?,?,?)',(family,h,page))
        holds=sorted(set(holds))
        db.execute('insert into final_holds values (?,?,?)',(page,json.dumps(holds),json.dumps(overlaps)))
        db.commit();guards.check()
        stats['finalized_pages']+=1
    integrity=db.execute('pragma integrity_check').fetchone()[0]
    if integrity!='ok':raise StopInventory('SQLite_integrity_failure')
    stats['sqlite_integrity']='ok'

def build(archive,output,expected_sha,start,limits=CAPS,reserve=FREE_RESERVE,enforce_pins=True):
    """Core used only by supervisor worker or explicit synthetic fixture tests."""
    stats={'encountered_records':0,'parsed_records':0,'oversize_records':0,'blank_records_excluded':True,
           'record_bytes':0,'actual_decoded_bytes':0,'members':[],'tar_end_blocks_verified':False,'gzip_eof_crc_verified':False,'finalized_pages':0}
    db=None;guards=Guards(output,start,limits,reserve)
    try:
        terminal_write(output/'worker-result.json',{'status':'RUNNING_NOT_COMPLETE','new_admitted_documents':0},limits['output_bytes'])
        if enforce_pins:check_pins()
        if enforce_pins:check_processed_reservation(output,limits['output_bytes'])
        guards.check()
        if shutil.disk_usage(output).free<reserve+limits['output_bytes']:raise StopInventory('preflight_output_plus_weights_and_free_floor')
        if file_sha(archive)!=expected_sha:raise StopInventory('archive_SHA256_mismatch')
        guards.check()
        base_path=Path(__file__).with_name('baseline-v3-holds.json')
        if file_sha(base_path)!=core.BASELINE_HOLDS_SHA256:raise StopInventory('historical_holds_pin_mismatch')
        baseline={(r['page_id'],r['revision_id'],r['html_sha256']):r['holds'] for r in json.loads(base_path.read_text())['records']}
        db=open_db(output/'inventory.sqlite3',limits)
        for loc in tar_records(archive,guards,stats):
            guards.check()
            if stats['encountered_records']>=limits['records']:raise StopInventory('encountered_record_cap')
            stats['encountered_records']+=1;stats['record_bytes']+=loc['record_bytes'];ordinal=stats['encountered_records']
            if loc['raw'] is None:
                row={'archive_sha256':expected_sha,**{k:v for k,v in loc.items() if k!='raw'},'page_id':None,'revision_id':None,'title':None,'family_id':None,'license_original_metadata':None,'training_admitted':False}
                payload=json.dumps(row,sort_keys=True);guards.check(8*len(payload.encode())+65536)
                db.execute('insert into records values (?,?,?,?,?,?,?,?,?,?,?)',(ordinal,loc['member_ordinal'],loc['line'],loc['record_sha256'],loc['record_bytes'],None,None,None,None,None,payload))
                stats['oversize_records']+=1
            else:
                r=json.loads(loc['raw']);c=core.extract_record(r);row=compact(r,c,loc,baseline);row['archive_sha256']=expected_sha
                payload=json.dumps(row,sort_keys=True);guards.check(8*len(payload.encode())+len(c['blocks'])*1024+65536)
                try:db.execute('insert into records values (?,?,?,?,?,?,?,?,?,?,?)',(ordinal,loc['member_ordinal'],loc['line'],loc['record_sha256'],loc['record_bytes'],c['page_id'],c['revision_id'],c['title'],c['title'].count('/'),c['family_id'],payload))
                except sqlite3.IntegrityError as exc:raise StopInventory('duplicate_page_or_line_identity') from exc
                for n,b in enumerate(c['blocks']):db.execute('insert into blocks values (?,?,?,?)',(c['page_id'],n,b['sha256'],len(b['text'])))
                stats['parsed_records']+=1
                del r,c,row
            db.commit();guards.check()
            if stats['encountered_records']==limits['records']:raise StopInventory('encountered_record_cap_no_full_EOF_claim')
        if not stats['tar_end_blocks_verified'] or not stats['gzip_eof_crc_verified']:raise StopInventory('archive_EOF_not_verified')
        finalize(db,guards,stats)
        if stats['finalized_pages']!=stats['parsed_records']:raise StopInventory('incomplete_family_block_finalization')
        if db.execute('select count(*) from records').fetchone()[0]!=stats['encountered_records']:raise StopInventory('record_count_reconciliation_failure')
        db.close();db=None
        guards.check()
        receipt={'status':'COMPLETE_SOURCE_INVENTORY_NO_ADMISSION','archive_sha256':expected_sha,'inventory_sha256':file_sha(output/'inventory.sqlite3'),'stats':stats,'limits':limits,'elapsed_seconds':shared_clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0,
                 'limitations':['Rendered character/byte lengths are not final-tokenizer token weights.','Family roots provisional; external aliases/transclusions unresolved.','License metadata and notice flags are not rights clearance.','All original HTML/wikitext remain in the immutable archive; none is rewritten here.','Full probability samples require parent review of this frozen frame.']}
        return terminal_write(output/'worker-result.json',receipt,limits['output_bytes'])
    except Exception as exc:
        if db is not None:
            try:db.rollback();db.close()
            except Exception:pass
        receipt={'status':'PARTIAL_INVENTORY_NO_ADMISSION','reason':str(exc)[:2000],'exception_type':type(exc).__name__,'incomplete_record_diagnostic':getattr(exc,'diagnostic',None),'archive_sha256':expected_sha,'stats':stats,'limits':limits,'elapsed_seconds':shared_clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0}
        terminal_write(output/'worker-result.json',receipt,limits['output_bytes']);raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--supervisor-pid',type=int,required=True);p.add_argument('--start-monotonic',type=float,required=True)
    a=p.parse_args()
    validate_supervisor_start(a.supervisor_pid,a.start_monotonic)
    build(a.archive,a.output,ARCHIVE_SHA256,a.start_monotonic)

def validate_supervisor_start(supervisor_pid,start):
    if os.getppid()!=supervisor_pid:raise ValueError('Requires live direct supervisor parent')
    if not 0<=shared_clock()-start<CAPS['seconds']:raise ValueError('Invalid supervisor shared CLOCK_MONOTONIC')

if __name__=='__main__':main()
