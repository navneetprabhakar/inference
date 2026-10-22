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
from urllib.parse import urlparse, unquote
import unicodedata

from shared_clock import shared_clock

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
    line=0;offset=0
    while not reader.at_eof:
        first=reader.readline(limits['parsed_record_bytes']+1)
        if not first:break
        line+=1;line_offset=offset
        if len(first)<=limits['parsed_record_bytes']:
            offset+=len(first)
            if first.strip():yield {'member':member,'member_ordinal':ordinal,'line':line,'member_uncompressed_byte_offset':line_offset,'record_bytes':len(first),'record_sha256':digest(first),'raw':first}
            continue
        h=hashlib.sha256(first);n=len(first);nonblank=bool(first.strip());complete=first.endswith(b'\n')
        try:
            while not complete:
                b=reader.readline(limits['oversize_chunk_bytes']);h.update(b);n+=len(b);nonblank=nonblank or bool(b.strip())
                complete=not b or b.endswith(b'\n')
        except Exception as exc:
            raise StopInventory('bound_or_failure_mid_oversize_record',{'member':member,'member_ordinal':ordinal,'line':line,'member_uncompressed_byte_offset':line_offset,'record_bytes_returned':n,'sha256_of_returned_prefix':h.hexdigest(),'record_complete':False}) from exc
        offset+=n
        if nonblank:yield {'member':member,'member_ordinal':ordinal,'line':line,'member_uncompressed_byte_offset':line_offset,'record_bytes':n,'record_sha256':h.hexdigest(),'raw':None,'hold':'oversize_record_not_parsed','record_complete':True}

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


def canonical(s):return unicodedata.normalize('NFC',re.sub(r'\s+',' ',s)).strip()

def identity(raw,loc,archive_sha):
    row={'archive_sha256':archive_sha,**{k:v for k,v in loc.items() if k!='raw'},
         'page_id':None,'revision_id':None,'title':None,'url':None,
         'license_original_metadata':None,'html_sha256':None,'html_UTF8_bytes':None,
         'wikitext_sha256':None,'wikitext_UTF8_bytes':None,'identity_holds':[],
         'training_admitted':False}
    if raw is None:
        row['identity_holds']=['oversize_record_not_parsed'];return row
    try:r=json.loads(raw)
    except (ValueError,UnicodeError):
        row['identity_holds']=['invalid_JSON_or_UTF8'];return row
    if not isinstance(r,dict):row['identity_holds']=['record_not_object'];return row
    holds=row['identity_holds']
    for dest,key in [('page_id','identifier'),('title','name'),('url','url')]:row[dest]=r.get(key)
    version=r.get('version');row['revision_original_metadata']=version
    row['revision_id']=version.get('identifier') if isinstance(version,dict) else None
    for key in ['namespace','is_part_of','in_language','date_modified','date_created']:
        row[key]=r.get(key)
    row['license_original_metadata']=r.get('license')
    for key in ['page_id','revision_id']:
        if type(row[key]) is not int or not 0<row[key]<2**63:holds.append('invalid_'+key)
    if not isinstance(row['title'],str) or not row['title'].strip():holds.append('invalid_title')
    try:
        u=urlparse(row['url']) if isinstance(row['url'],str) else None
        if u is None or u.scheme not in ['http','https'] or u.hostname!='en.wikibooks.org' or not u.path.startswith('/wiki/'):holds.append('invalid_project_URL')
        elif isinstance(row['title'],str) and canonical(row['title'].replace('_',' '))!=canonical(unquote(u.path[6:]).replace('_',' ')):holds.append('title_URL_mismatch')
    except ValueError:holds.append('invalid_project_URL')
    lic=row['license_original_metadata']
    if not isinstance(lic,list) or not lic or not all(isinstance(x,dict) and isinstance(x.get('url'),str) for x in lic):holds.append('missing_structured_license_metadata')
    ns=r.get('namespace');project=r.get('is_part_of')
    if ns is not None and (not isinstance(ns,dict) or ns.get('identifier')!=0):holds.append('unexpected_namespace_metadata')
    if project is not None and (not isinstance(project,dict) or project.get('identifier')!='enwikibooks'):holds.append('unexpected_project_metadata')
    body=r.get('article_body')
    for key in ['html','wikitext']:
        value=body.get(key) if isinstance(body,dict) else None
        row[key+'_present']=isinstance(value,str)
        if isinstance(value,str):
            try:encoded=value.encode()
            except UnicodeError:
                holds.append('invalid_Unicode_'+key);continue
            row[key+'_sha256']=digest(encoded);row[key+'_UTF8_bytes']=len(encoded);row[key+'_unicode_characters']=len(value)
        elif key=='html':holds.append('missing_HTML')
    return row

def build(archive,output,expected_sha,start,limits=CAPS,reserve=FREE_RESERVE,enforce_pins=True):
    guards=Guards(output,start,limits,reserve);db=None
    stats={'encountered_records':0,'identity_held_records':0,'oversize_records':0,'record_bytes':0,'actual_decoded_bytes':0,'members':[],
           'tar_end_blocks_verified':False,'gzip_eof_crc_verified':False,'blank_lines_excluded':True}
    try:
        terminal_write(output/'worker-result.json',{'status':'RUNNING_NOT_COMPLETE'},limits['output_bytes'])
        if enforce_pins:check_pins();check_processed_reservation(output,limits['output_bytes'])
        guards.check()
        if shutil.disk_usage(output).free<reserve+limits['output_bytes']:raise StopInventory('preflight_output_plus_weights_and_free_floor')
        h=hashlib.sha256()
        with archive.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):guards.check();h.update(b)
        if h.hexdigest()!=expected_sha:raise StopInventory('archive_SHA256_mismatch')
        os.environ['SQLITE_TMPDIR']=str(output)
        guards.check(131072)
        db=sqlite3.connect(output/'inventory.sqlite3')
        db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL');db.execute('pragma cache_size=-4096');db.execute('pragma temp_store=FILE')
        db.execute('pragma max_page_count='+str((limits['output_bytes']-TERMINAL_RESERVE)//4096))
        db.execute('create table records (ordinal integer primary key, member integer, line integer, page_id integer, revision_id integer, data text, unique(member,line))')
        db.execute('create index page_lookup on records(page_id,revision_id)');db.commit()
        for loc in tar_records(archive,guards,stats):
            guards.check()
            if stats['encountered_records']>=limits['records']:raise StopInventory('encountered_record_cap')
            row=identity(loc['raw'],loc,expected_sha);payload=json.dumps(row,ensure_ascii=True,separators=(',',':'))
            # Conservative prewrite allowance includes SQLite pages and rollback journal.
            guards.check(8*len(payload.encode())+131072)
            ordinal=stats['encountered_records']+1
            page=row['page_id'] if type(row['page_id']) is int and 0<row['page_id']<2**63 else None
            rev=row['revision_id'] if type(row['revision_id']) is int and 0<row['revision_id']<2**63 else None
            db.execute('insert into records values (?,?,?,?,?,?)',(ordinal,loc['member_ordinal'],loc['line'],page,rev,payload))
            stats['encountered_records']=ordinal;stats['record_bytes']+=loc['record_bytes']
            stats['identity_held_records']+=bool(row['identity_holds']);stats['oversize_records']+=loc['raw'] is None
            # Full identity duplicates remain visible: this frame is not deduplicated.
            if ordinal%100==0:db.commit()
            del row,payload
            if ordinal==limits['records']:raise StopInventory('encountered_record_cap_no_full_EOF_claim')
        if not stats['tar_end_blocks_verified'] or not stats['gzip_eof_crc_verified']:raise StopInventory('archive_EOF_not_verified')
        db.commit();guards.check()
        n,total=db.execute("select count(*),sum(json_extract(data,'$.record_bytes')) from records").fetchone()
        if n!=stats['encountered_records'] or (total or 0)!=stats['record_bytes']:raise StopInventory('record_count_or_bytes_reconciliation_failure')
        db.set_progress_handler(lambda:1 if shared_clock()-start>=limits['seconds'] else 0,10000)
        if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise StopInventory('SQLite_integrity_failure')
        stats['sqlite_integrity']='ok';stats['reconciled_stored_records']=n
        db.close();db=None;guards.check()
        result={'status':'COMPLETE_IDENTITY_FRAME_NO_ADMISSION','archive_sha256':expected_sha,'inventory_sha256':file_sha(output/'inventory.sqlite3'),
                'stats':stats,'limits':limits,'elapsed_seconds':shared_clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0,
                'limitations':['Identity frame only; no eligibility, token weights, quality, family resolution or rights clearance.','Oversize rows have whole-line identity hashes only; fields were not parsed.','Invalid and duplicate identities retained; original archive remains authoritative.','Blank lines excluded; full gzip CRC and tar EOF mandatory.']}
        guards.check();return terminal_write(output/'worker-result.json',result,limits['output_bytes'])
    except BaseException as exc:
        if db is not None:
            try:db.commit();db.close()
            except Exception:pass
        terminal_write(output/'worker-result.json',{'status':'PARTIAL_IDENTITY_FRAME_NO_ADMISSION','reason':str(exc)[:2000],
            'incomplete_record_diagnostic':getattr(exc,'diagnostic',None),'stats':stats,'archive_sha256':expected_sha,
            'elapsed_seconds':shared_clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0},limits['output_bytes']);raise

def validate_supervisor_start(pid,start):
    if os.getppid()!=pid:raise ValueError('Requires live direct supervisor parent')
    if not 0<=shared_clock()-start<CAPS['seconds']:raise ValueError('Invalid supervisor shared CLOCK_MONOTONIC')

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--supervisor-pid',type=int,required=True);p.add_argument('--start-monotonic',type=float,required=True)
    a=p.parse_args();validate_supervisor_start(a.supervisor_pid,a.start_monotonic);build(a.archive,a.output,ARCHIVE_SHA256,a.start_monotonic)
if __name__=='__main__':main()
