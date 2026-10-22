"""Synthetic source+SQLite+worker lifecycle only, no retained index scan."""
import bz2
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sqlite3
import tempfile
import types
import inventory as runner
import inventory_core as core


def spec(raw, compressed=None, xmlsize=1000):
    compressed=bz2.compress(raw) if compressed is None else compressed
    lines=raw.splitlines(keepends=True)
    offsets=[int(x.split(b':',1)[0]) for x in lines]
    groups=[]
    for line,offset in zip(lines,offsets):
        if not groups or groups[-1][0]!=offset:groups.append([offset,[]])
        groups[-1][1].append(line)
    stats={'compressed_bytes':len(compressed),'decoded_bytes':len(raw),'rows':len(lines),
        'offset_groups':len(groups),'bzip2_members':compressed.count(b'BZh9'),
        'unterminated_final_rows':int(not raw.endswith(b'\n')),'empty_titles':sum(not l.rstrip(b'\n').split(b':',2)[2] for l in lines),
        'maximum_group_rows':max(map(lambda g:len(g[1]),groups)),
        'maximum_group_raw_bytes':max(sum(map(len,g[1])) for g in groups),'maximum_line_bytes':max(map(len,lines))}
    return {'stats':stats,'SHA256':hashlib.sha256(compressed).hexdigest(),'MD5':hashlib.md5(compressed).hexdigest(),
        'SHA1':hashlib.sha1(compressed).hexdigest(),'bytes':len(compressed),'XML_bytes':xmlsize},compressed


def run():
    cases=[]
    def bad(name, action):
        try:action()
        except (ValueError,OSError,sqlite3.Error,TimeoutError):cases.append(name)
        else:raise AssertionError(name+' did not fail')
    assessor=runner.load('original_synthetic_index_assessor',runner.ASSESSOR)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp).resolve();counter=0
        def execute(raw, change=lambda s,b:(s,b)):
            nonlocal counter
            counter+=1;s,b=spec(raw);s,b=change(s,b);store=core.Store(root/f'test-{counter}.sqlite',batch=2)
            try:return core.build(io.BytesIO(b),assessor,store,s),store.path
            finally:store.close()
        raw='000:0001:Colon: café 雪\n0:2:Short definition\n20:3:Code instruction'.encode()
        result,path=execute(raw)
        assert result['global_page_ID_uniqueness_proven'] and result['SQLite_rows']==3
        with sqlite3.connect(path) as db:
            rows=db.execute('SELECT row_ordinal,page_id,title,raw_line_sha256,raw_line_bytes,line_ends_LF,noncanonical_offset_ascii,noncanonical_page_ascii FROM rows ORDER BY row_ordinal').fetchall()
            assert rows[0][2]=='Colon: café 雪' and rows[0][6:]==('000','0001')
            assert rows[0][3]==hashlib.sha256(raw.splitlines(keepends=True)[0]).digest()
            assert rows[2][5]==0 and db.execute('select count(*) from groups').fetchone()[0]==2
            assert db.execute('pragma integrity_check').fetchall()==[('ok',)]
        cases+=['exact_SQLite_uniqueID_row_group_and_rawline_provenance','colon_UTF8_and_noncanonical_numeric_lexemes_preserved','unterminated_final_line_retained','SQLite_integrity_complete']
        multi_raw=b'0:1:A\n20:2:B\n'
        multi_bytes=bz2.compress(b'0:1:A\n')+bz2.compress(b'20:2:B\n')
        multi,_=execute(multi_raw,lambda s,b:spec(multi_raw,multi_bytes))
        assert multi['stats']['bzip2_members']==2
        cases.append('all_concatenated_BZ2_members_CRC_EOF')
        bad('duplicate_pageID_same_title',lambda:execute(b'0:1:A\n0:1:A\n'))
        bad('duplicate_pageID_conflicting_title',lambda:execute(b'0:1:A\n20:1:B\n'))
        bad('negative_offset',lambda:execute(b'-1:1:A\n'))
        bad('offset_equal_XMLsize',lambda:execute(b'1000:1:A\n'))
        bad('nonmonotonic_offset',lambda:execute(b'20:1:A\n0:2:B\n'))
        bad('zero_pageID',lambda:execute(b'0:0:A\n'))
        bad('pageID_over_int64',lambda:execute(b'0:9223372036854775808:A\n'))
        bad('invalid_UTF8',lambda:execute(b'0:1:\xff\n'))
        bad('truncated_BZ2',lambda:execute(b'0:1:A\n',lambda s,b:(s,b[:-2])))
        def corrupted(s,b):
            x=bytearray(b);x[-5]^=4;return s,bytes(x)
        bad('BZ2_CRC_failure',lambda:execute(b'0:1:A\n',corrupted))
        bad('trailing_compressed_garbage',lambda:execute(b'0:1:A\n',lambda s,b:(s,b+b'junk')))
        bad('source_checksum_mismatch',lambda:execute(b'0:1:A\n',lambda s,b:({**s,'SHA256':'0'*64},b)))
        bad('decoded_byte_cap',lambda:execute(b'0:1:A\n',lambda s,b:({**s,'stats':{**s['stats'],'decoded_bytes':5}},b)))
        bad('exact_prior_row_count',lambda:execute(b'0:1:A\n',lambda s,b:({**s,'stats':{**s['stats'],'rows':2}},b)))
        # Tiny real page-count cap: on-disk SQLite never crosses it; no disk journal.
        store=core.Store(root/'bounded.sqlite',db_cap=65536)
        try:
            def fill():
                for i in range(2000):
                    raw=f'0:{i+1}:Title {i:010d} with sufficient synthetic payload\n'.encode()
                    store.emit(raw,assessor.parse(raw,i+1,1000))
            bad('SQLite_actual_max_page_count_stops_and_preserves_partial',fill)
        finally:store.close()
        assert (root/'bounded.sqlite').stat().st_size<=65536 and not (root/'bounded.sqlite-journal').exists()
        cases.append('MEMORY_journal_no_disk_journal_overlap')
        # Execute actual production worker against a tiny synthetic source/profile.
        old=(runner.OUT,runner.ROOT,runner.SOURCE,runner.verify)
        job=root/'job';job.mkdir();source=root/'synthetic-index.bz2';s,b=spec(b'0:1:Intro\n20:2:Procedure\n');source.write_bytes(b)
        for name,n in runner.SLOTS.items():(job/name).write_bytes(b' '*n)
        runner.OUT=job;runner.ROOT=root;runner.SOURCE=source;runner.verify=lambda a:{'source':s}
        a=types.SimpleNamespace(start=runner.clock(),supervisor_pid=os.getppid(),code_pins_sha256='fixture',profile_sha256='fixture')
        try:
            runner.worker(a)
            result=json.loads((job/'result.json').read_text())
            assert result['status']=='COMPLETE_INDEX_IDENTITY_FRAME_NO_ADMISSION' and result['source_stats']['rows']==2
            assert result['SQLite_SHA256']==runner.sha(job/'index.sqlite')
            cases.append('actual_production_worker_final_recheck_close_hash_and_COMPLETE_lifecycle')
        finally:runner.OUT,runner.ROOT,runner.SOURCE,runner.verify=old
        # Alarm and SIGTERM must already be armed during supervisor preflight.
        oldverify=runner.verify
        def terminated(a):
            assert signal.getitimer(signal.ITIMER_REAL)[0]>0
            signal.raise_signal(signal.SIGTERM)
        runner.verify=terminated
        try:bad('actual_supervisor_early_TERM_preflight',lambda:runner.supervise(a))
        finally:runner.verify=oldverify
        # Real owned subprocess kill/reap on a synthetic RSS breach; no source scan.
        old=(runner.OUT,runner.ROOT,runner.verify,runner.load,runner.subprocess.Popen)
        runner.OUT=root/'supervised';runner.ROOT=root;runner.verify=lambda a:{}
        original_load=runner.load;original_popen=runner.subprocess.Popen
        runner.load=lambda name,path:types.SimpleNamespace(tree_rss=lambda pid:runner.RSS+1) if path==runner.RSS_HELPER else original_load(name,path)
        runner.subprocess.Popen=lambda args,**kw:original_popen([runner.sys.executable,'-c','import time;time.sleep(30)'],**kw)
        try:
            bad('actual_supervisor_RSS_stop_kills_and_reaps_owned_synthetic_child',lambda:runner.supervise(a))
            owned=json.loads((runner.OUT/'ownership.json').read_text())
            try:os.kill(owned['worker_pid'],0)
            except ProcessLookupError:pass
            else:raise AssertionError('synthetic child not reaped')
            saved=(runner.OUT/'supervisor.json').read_bytes()
            assert json.loads(saved)['worker_reaped']
            bad('actual_existing_partial_output_never_replayed_or_overwritten',lambda:runner.supervise(a))
            assert (runner.OUT/'supervisor.json').read_bytes()==saved
        finally:runner.OUT,runner.ROOT,runner.verify,runner.load,runner.subprocess.Popen=old
        bad('expired_worker_alarm',lambda:runner.arm(-1))
        signal.setitimer(signal.ITIMER_REAL,0)
    if (runner.HERE/'code-pins.json').exists():
        a=types.SimpleNamespace(code_pins_sha256=runner.sha(runner.HERE/'code-pins.json'),profile_sha256=runner.sha(runner.HERE/'profile.json'))
        original_open=Path.open
        def no_source(path,*args,**kwargs):
            if path.resolve()==runner.SOURCE.resolve():raise AssertionError('preflight retained index body open')
            return original_open(path,*args,**kwargs)
        Path.open=no_source
        try:
            runner.verify(a);cases.append('actual_frozen_preflight_retained_index_body_open_prohibited')
            wrong=types.SimpleNamespace(code_pins_sha256='0'*64,profile_sha256=a.profile_sha256)
            bad('actual_external_code_manifest_digest_refused',lambda:runner.verify(wrong))
            original_text=Path.read_text
            def empty(path,*args,**kwargs):
                if path.resolve()==(runner.HERE/'code-pins.json').resolve():return '{"SHA256":{}}'
                return original_text(path,*args,**kwargs)
            Path.read_text=empty
            try:bad('actual_empty_exact_inventory_refused',lambda:runner.verify(a))
            finally:Path.read_text=original_text
        finally:Path.open=original_open
    return {'status':'PASS_SYNTHETIC_ONLY_NO_RETAINED_INDEX_XML_NETWORK_LEDGER','controls':len(cases),'cases':cases}


if __name__=='__main__':print(json.dumps(run(),indent=2))
