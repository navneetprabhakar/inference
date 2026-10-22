"""Read-only constant-memory ordered subset of independently verified index."""
import contextlib,hashlib,os,sqlite3,stat
from pathlib import Path

def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

@contextlib.contextmanager
def opened(profile,check):
    binding=profile['index'];selection=profile['selection'];p=Path(binding['path']);expected=binding['stat']
    def custody():
        if p.is_symlink() or str(p.resolve())!=str(p) or identity(p.stat())!=expected:raise ValueError('index_path_stat_custody')
    custody();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);db=None
    try:
        if identity(os.fstat(fd))!=expected or not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('index_FD_stat_regular')
        db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
        for pragma in ['query_only=ON','cache_size=-8192','temp_store=MEMORY','mmap_size=0']:db.execute('PRAGMA '+pragma)
        db.set_progress_handler(lambda:(check() or 0),10000);custody()
        def groups():
            previous_end=selection['header_bytes'];previous_row=0;count=0
            cursor=db.execute('SELECT group_ordinal,block_start,block_end_exclusive,first_row,last_row,row_count FROM groups WHERE group_ordinal<=? ORDER BY group_ordinal',(selection['groups'],))
            for g,start,end,first,last,n in cursor:
                check();custody()
                if g!=count+1 or start!=previous_end or first!=previous_row+1 or type(n) is not int or not 1<=n<=100 or last-first+1!=n or not 0<end-start<=profile['limits']['max_group_compressed_bytes'] or end>selection['compressed_prefix_end_exclusive']:raise ValueError('index_group_exact_partition')
                rows=db.execute('SELECT row_ordinal,page_id,title,raw_line_sha256,raw_line_bytes,line_ends_LF,noncanonical_offset_ascii,noncanonical_page_ascii,group_ordinal FROM rows WHERE row_ordinal BETWEEN ? AND ? ORDER BY row_ordinal',(first,last)).fetchall()
                if len(rows)!=n:raise ValueError('index_exact_group_row_count')
                projected=[];linehash=hashlib.sha256()
                for offset,(ordinal,pid,title,rawSHA,nbytes,lf,offsetlex,idlex,rowgroup) in enumerate(rows):
                    if ordinal!=first+offset or rowgroup!=g or type(pid) is not int or pid<=0 or type(title) is not str or type(lf) is not int or lf not in [0,1]:raise ValueError('index_row_identity_fields')
                    off=str(start) if offsetlex is None else offsetlex;ident=str(pid) if idlex is None else idlex
                    if type(off) is not str or type(ident) is not str or not off.isascii() or not ident.isascii() or not off.isdigit() or not ident.isdigit() or int(off)!=start or int(ident)!=pid:raise ValueError('index_numeric_lexemes')
                    raw=(off+':'+ident+':'+title).encode('utf8')+(b'\n' if lf else b'')
                    if len(raw)>131072 or len(raw)!=nbytes or hashlib.sha256(raw).digest()!=rawSHA:raise ValueError('index_lossless_rawline_hash_length')
                    linehash.update(raw);projected.append([ordinal,g,pid,title])
                yield {'group_ordinal':g,'compressed_start':start,'compressed_end_exclusive':end,'compressed_bytes':end-start,'first_row_ordinal':first,'last_row_ordinal':last,'index_rows':n,'raw_index_lines_SHA256':linehash.hexdigest()},projected
                previous_end=end;previous_row=last;count+=1
            if count!=selection['groups'] or previous_row!=selection['rows'] or previous_end!=selection['compressed_prefix_end_exclusive']:raise ValueError('index_subset_exact_terminal_coverage')
            if selection.get('require_next_group_outside_prefix',True):
                nextrow=db.execute('SELECT block_start,block_end_exclusive,first_row FROM groups WHERE group_ordinal=?',(count+1,)).fetchone()
                if nextrow is None or nextrow[0]!=previous_end or nextrow[1]<=profile['source']['bytes'] or nextrow[2]!=previous_row+1:raise ValueError('next_group_not_closed_in_retained_prefix')
        groups.assert_custody=custody
        yield groups
        custody()
        if identity(os.fstat(fd))!=expected:raise ValueError('index_FD_changed')
    finally:
        if db is not None:db.close()
        os.close(fd)
