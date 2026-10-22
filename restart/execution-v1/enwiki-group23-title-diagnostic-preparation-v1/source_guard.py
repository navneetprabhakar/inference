"""Separately versioned terminal-prefix custody; never wholepublisher verification."""
import contextlib,hashlib,json,os,stat
from pathlib import Path
FIELDS=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
PREFIX_BYTES=17988844772
PREFIX_SHA='28c687b269c4e46e28c1068d7cd7c9579fbb3f03a73c3924bb014f081e58c00b'
ETAG='"6a738a16-63590c983"'
URL='https://dumps.wikimedia.org/enwiki/20260801/enwiki-20260801-pages-articles-multistream.xml.bz2'

def ident(s):return [getattr(s,k) for k in FIELDS]
def small(path,cap=8000000):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>cap:raise ValueError('metadata_regular_bound')
    with p.open('rb') as f:b=f.read(cap+1)
    if len(b)>cap:raise ValueError('metadata_read_bound')
    return b
def load(p):return json.loads(small(p))
def absent(pid):
    if type(pid) is not int or pid<=1:raise ValueError('old_owner_PID')
    try:os.kill(pid,0)
    except ProcessLookupError:return
    except PermissionError:raise ValueError('old_PID_absence_unproven')
    raise ValueError('old_source_writer_PID_present')
def verify(profile):
    b=profile['source'];base=Path(b['base'])
    names={
      'v2_worker':base/'m2-intake/enwiki-native-full-XML-20260801-v2/worker-result.json',
      'v2_supervisor':base/'m2-intake/enwiki-native-full-XML-20260801-v2/supervisor-result.json',
      'v2_headers':base/'m2-intake/enwiki-native-full-XML-20260801-v2/response-headers.json',
      'v2_preflight':base/'m2-intake/enwiki-native-full-XML-20260801-v2/preflight.json',
      'v2_owner':base/'m2-intake/enwiki-native-full-XML-20260801-v2/ownership.json',
      'v3_worker':base/'m2-intake/enwiki-native-full-XML-20260801-v3/worker-result.json',
      'v3_supervisor':base/'m2-intake/enwiki-native-full-XML-20260801-v3/supervisor-result.json',
      'v3_headers':base/'m2-intake/enwiki-native-full-XML-20260801-v3/response-headers.json',
      'v3_preflight':base/'m2-intake/enwiki-native-full-XML-20260801-v3/preflight.json',
      'v3_owner':base/'m2-intake/enwiki-native-full-XML-20260801-v3/ownership.json',
      'v3_copy':base/'m2-intake/enwiki-native-full-XML-20260801-v3/prefix-copy.json',
      'fresh_prefix':base/'m2-intake/enwiki-native-segmented-tail-20260801-v1/prefix-verification.json',
      'seg_owner':base/'m2-intake/enwiki-native-segmented-tail-20260801-v1/ownership.json',
      'seg_profile':base/'enwiki-native-segmented-tail-preparation-v1/profile.json',
      'seg_codepins':base/'enwiki-native-segmented-tail-preparation-v1/code-pins.json',
      'seg_code':base/'enwiki-native-segmented-tail-preparation-v1/segmented.py',
    }
    for v in [2,3]:
        for n in ['archive.py','profile.json','code-pins.json']:
            names['prep%d_%s'%(v,n)]=base/('enwiki-native-full-acquisition-preparation-v%d'%v)/n
    if set(b['chain'])!=set(names):raise ValueError('exact_source_chain_inventory')
    for k,p in names.items():
        if b['chain'][k]['path']!=str(p) or hashlib.sha256(small(p)).hexdigest()!=b['chain'][k]['SHA256']:raise ValueError('source_chain_pin')
    d={k:load(p) for k,p in names.items() if p.suffix=='.json'}
    for v in [2,3]:
        w=d[f'v{v}_worker'];sup=d[f'v{v}_supervisor'];owner=d[f'v{v}_owner']
        if w['status']!='TERMINAL_PARTIAL_XML_NO_RETRY' or not w['prefix_hash_covers_entire_partial'] or w['published_final_exists'] is not False:raise ValueError('source_terminal_partial_only')
        if sup['worker_exit_code']!=1 or sup['worker_receipt_SHA256']!=b['chain'][f'v{v}_worker']['SHA256'] or sup['independent_final_file_verification'] is not None:raise ValueError('source_supervisor_terminal')
        if owner['code_pins_sha256']!=b['chain'][f'prep{v}_code-pins.json']['SHA256'] or owner['profile_sha256']!=b['chain'][f'prep{v}_profile.json']['SHA256']:raise ValueError('source_owned_code_profile')
        registry=d[f'prep{v}_code-pins.json']['sha256']
        if registry.get(str(names[f'prep{v}_archive.py']))!=b['chain'][f'prep{v}_archive.py']['SHA256']:raise ValueError('source_worker_code_inventory')
        absent(owner['supervisor_pid']);absent(owner['worker_pid'])
    if d['v3_worker']['partial_bytes']!=PREFIX_BYTES or d['v3_worker']['complete_recorded_prefix']['SHA256']!=PREFIX_SHA:raise ValueError('terminal_v3_prefix_identity')
    old=d['v2_worker']['complete_recorded_prefix'];cp=d['v3_copy']
    if old['bytes']!=16927669898 or old['SHA256']!='1fe6566d328a9c8b790df414dc89a4922a8fa6f209b5f7e0120ad7ce6951400e' or cp['new_copy_bytes']!=old['bytes'] or cp['new_copy_prefix_SHA256']!=old['SHA256'] or cp['no_HTTP_before_verified_copy'] is not True:raise ValueError('original_prefix_copy_ancestry')
    for v,status,start,length in [(2,200,0,26668484995),(3,206,16927669898,9740815097)]:
        h=d[f'v{v}_headers'];raw=bytes.fromhex(h['prefix_hex'])
        if len(raw)>65536 or len(raw)!=h['parsed_header_bytes'] or hashlib.sha256(raw).hexdigest()!=h['headers_SHA256'] or h['effective_URL']!=URL or h['status']!=status:raise ValueError('official_header_evidence')
        headers={}
        for line in raw.decode('latin1').splitlines():
            k,val=line.split(':',1);headers.setdefault(k.lower(),[]).append(val.strip())
        if headers.get('etag')!=[ETAG] or headers.get('content-length')!=[str(length)] or headers.get('content-encoding',[]) not in [[],['identity']] or headers.get('transfer-encoding'):raise ValueError('header_ETag_identity_length')
        if v==3 and headers.get('content-range')!=['bytes 16927669898-26668484994/26668484995']:raise ValueError('range_ancestry')
    for v in [2,3]:
        pre=d[f'v{v}_preflight'];reg=d[f'prep{v}_code-pins.json']['sha256']
        if pre['URL']!=URL or pre['CERT_REQUIRED_hostname'] is not True or pre['CA_SHA256'] not in reg.values():raise ValueError('original_TLS_required')
    fresh=d['fresh_prefix'];seg=d['seg_profile'];owner=d['seg_owner']
    if fresh['bytes']!=PREFIX_BYTES or fresh['SHA256']!=PREFIX_SHA or len(fresh['components'])!=1:raise ValueError('fresh_wholeprefix_hash_receipt')
    cp=fresh['components'][0]
    if cp['path']!=b['path'] or cp['bytes']!=PREFIX_BYTES or cp['SHA256']!=PREFIX_SHA or cp['stat']!=b['stat']:raise ValueError('fresh_prefix_stat_hash_chain')
    if seg['prefix']['path']!=b['path'] or seg['prefix']['bytes']!=PREFIX_BYTES or seg['prefix']['SHA256']!=PREFIX_SHA or seg['prefix']['stat']!=b['stat']:raise ValueError('actual_reader_prefix_profile')
    if owner['profile_SHA256']!=b['chain']['seg_profile']['SHA256'] or owner['code_pins_SHA256']!=b['chain']['seg_codepins']['SHA256']:raise ValueError('actual_reader_ownership_profile')
    reg=d['seg_codepins']
    mapping=reg.get('SHA256',reg.get('sha256',reg.get('files',{})))
    if isinstance(mapping,list):mapping={x['path']:x.get('SHA256',x.get('sha256')) for x in mapping}
    if mapping.get(str(names['seg_code']))!=b['chain']['seg_code']['SHA256']:raise ValueError('actual_reader_code_registry')
    return b

@contextlib.contextmanager
def opened(binding,check):
    p=Path(binding['path']);expected=binding['stat']
    if p.is_symlink() or str(p.resolve())!=str(p) or ident(p.stat())!=expected or not stat.S_ISREG(p.stat().st_mode):raise ValueError('source_before_stat')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        if ident(os.fstat(fd))!=expected:raise ValueError('source_FD_stat')
        consumed=0;position=0
        def read_at(offset,n):
            nonlocal consumed,position
            check()
            if type(offset) is not int or type(n) is not int or n<=0 or n>2000000 or (offset,n) not in [(0,570),(24391408,1375788)] or ((position==0 and offset!=0) or (position==570 and offset!=24391408)) or consumed+n>1376358:raise ValueError('bounded_sequential_prefix_read')
            raw=os.pread(fd,n,offset);consumed+=len(raw);position+=len(raw)
            if len(raw)!=n:raise ValueError('source_short_read')
            return raw
        def assert_custody():
            if ident(os.fstat(fd))!=expected or ident(p.stat())!=expected or p.is_symlink():raise ValueError('source_guard_stat_changed')
        read_at.assert_custody=assert_custody
        yield read_at
        check()
        if consumed!=1376358:raise ValueError('exact_selected_prefix_consumption')
        if ident(os.fstat(fd))!=expected or ident(p.stat())!=expected:raise ValueError('source_after_stat')
    finally:os.close(fd)
