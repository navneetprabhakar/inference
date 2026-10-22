"""Tiny synthetic complete-publication fixtures only; never open real archives."""
import copy
import bz2
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import virtual_reader as v


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(root, mutation=None, blobs=None):
    blobs = blobs if blobs is not None else [b'abc', b'defgh', b'ij']
    components = []
    for i, raw in enumerate(blobs):
        p = root / ('component-%d' % i)
        p.write_bytes(raw)
        components.append({'path': str(p), 'bytes': len(raw), 'SHA256': sha(raw), 'stat': v.identity(p.stat())})
    whole = b''.join(blobs)
    checksums = {'bytes': len(whole), 'MD5': hashlib.md5(whole).hexdigest(), 'SHA1': hashlib.sha1(whole).hexdigest(), 'SHA256': sha(whole)}
    w = {'status': 'COMPLETE_WORKER_VIRTUAL_CHECKSUMS_PENDING_INDEPENDENT_PUBLICATION', 'parts': 2, 'response_bytes': sum(map(len,blobs[1:])), 'body_reserved': sum(map(len,blobs[1:]))+2, 'virtual_bytes': len(whole), **{k: checksums[k] for k in ['MD5', 'SHA1', 'SHA256']}}
    m = {'status': 'COMPLETE_VIRTUAL_ARCHIVE_WORKER_AND_INDEPENDENT_SUPERVISOR_VERIFIED', 'URL': 'https://example.invalid/archive.bz2', 'bytes': len(whole), 'publisher_MD5': checksums['MD5'], 'publisher_SHA1': checksums['SHA1'], 'local_SHA256': checksums['SHA256'], 'ordered_components': components, 'no_concatenated_full_file_created': True, 'no_decompression_or_usable_data_claim': True}
    s = {'status': 'COMPLETE_VIRTUAL_ARCHIVE_NO_ADMISSION', 'coordinator_exit_code': 0, 'coordinator_reaped': True, 'all_charges_preserved': True, 'independent_checksums': checksums}
    expected = {k: m[k] for k in ['URL', 'bytes', 'publisher_MD5', 'publisher_SHA1']}
    expected['components'] = [{k: e[k] for k in ['path', 'bytes']} for e in components]
    if mutation:
        mutation(m, s, w, expected)
    pins = {}
    def save(name, obj):
        raw = (json.dumps(obj) + '\n').encode()
        (root / name).write_bytes(raw)
        pins[name] = sha(raw)
    save('worker-result.json', w)
    m['worker_receipt_SHA256'] = pins['worker-result.json']
    save('virtual-archive-manifest.json', m)
    s['virtual_manifest_SHA256'] = pins['virtual-archive-manifest.json']
    save('supervisor-result.json', s)
    return pins, expected, whole


def run():
    names = []
    def bad(name, action):
        try:
            action()
        except (ValueError, OSError, TypeError, KeyError):
            names.append(name)
        else:
            raise AssertionError('not refused: ' + name)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        pins, expected, whole = build(root)
        with v.VirtualArchive(root, pins, expected, max_read=8) as f:
            assert f.read(0) == b'' and f.tell() == 0
            names.append('zero_read_position_stable')
            assert f.read(4) == b'abcd' and f.tell() == 4
            assert f.read(6) == b'efghij' and f.read(1) == b''
            names.append('cross_prefix_part_and_part_part_boundaries_exact_EOF')
            assert f.seek(-3, os.SEEK_END) == 7 and f.read(8) == b'hij'
            assert f.seek(1) == 1 and f.seek(1, os.SEEK_CUR) == 2 and f.read(2) == b'cd'
            names.append('seek_set_current_end')
            f.seek(0)
            b = bytearray(7)
            assert f.readinto(b) == 7 and b == b'abcdefg'
            names.append('bounded_readinto_across_components')
            for name, action in [('negative_read', lambda: f.read(-1)), ('implicit_readall', lambda: f.read()), ('oversize_read', lambda: f.read(9)), ('noninteger_read', lambda: f.read(1.0)), ('negative_seek', lambda: f.seek(-1)), ('past_EOF_seek', lambda: f.seek(11)), ('invalid_whence', lambda: f.seek(0, 9)), ('immutable_readinto', lambda: f.readinto(b'x'))]:
                bad(name, action)
            assert f.readable() and f.seekable() and not f.writable() and f.component_hashes_not_recomputed_by_reader
        bad('closed_read', lambda: f.read(0))
        f.close()
        names.append('idempotent_close')
        # Standard binary-buffer consumer, with bounded underlying readinto.
        with io.BufferedReader(v.VirtualArchive(root, pins, expected), buffer_size=4) as buffered:
            assert buffered.read(9) == whole[:9] and buffered.seek(2) == 2 and buffered.read(5) == whole[2:7]
        names.append('standard_buffered_binary_file_interface')
        for name, mutation in [
            ('candidate_manifest', lambda m,s,w,e:m.update(status='WORKER_VERIFIED_NOT_PUBLISHED_UNTIL_INDEPENDENT_SUPERVISOR')),
            ('partial_supervisor', lambda m,s,w,e:s.update(status='TERMINAL_PARTIAL_NO_RETRY_NO_COMPLETE_ARCHIVE')),
            ('partial_worker', lambda m,s,w,e:w.update(status='TERMINAL_PARTIAL_NO_RETRY_NO_PUBLICATION')),
            ('unreaped_worker', lambda m,s,w,e:s.update(coordinator_reaped=False)),
            ('wrong_independent_checksum', lambda m,s,w,e:s['independent_checksums'].update(SHA1='0'*40)),
            ('wrong_worker_checksum', lambda m,s,w,e:w.update(SHA256='0'*64)),
            ('wrong_publisher_identity', lambda m,s,w,e:e.update(publisher_MD5='0'*32)),
            ('wrong_component_order', lambda m,s,w,e:m['ordered_components'].reverse()),
            ('component_total_wrong', lambda m,s,w,e:m.update(bytes=11)),
            ('wrong_tail_charge', lambda m,s,w,e:w.update(body_reserved=8)),
            ('bad_component_hash_schema', lambda m,s,w,e:m['ordered_components'][0].update(SHA256='bad')),
            ('bad_component_stat', lambda m,s,w,e:m['ordered_components'][0]['stat'].__setitem__(2,99)),
        ]:
            pins2, e2, _ = build(root, mutation)
            bad(name, lambda: v.VirtualArchive(root, pins2, e2))
        pins, expected, _ = build(root)
        bad('missing_external_metadata_pin', lambda: v.VirtualArchive(root, {k:h for k,h in pins.items() if k!='worker-result.json'}, expected))
        tamper = dict(pins);tamper['supervisor-result.json']='0'*64
        bad('wrong_external_metadata_hash', lambda: v.VirtualArchive(root, tamper, expected))
        bad('invalid_readcap', lambda: v.VirtualArchive(root, pins, expected, max_read=v.MAX_READ+1))
        f = v.VirtualArchive(root, pins, expected)
        fds = list(f._fds)
        target = Path(expected['components'][1]['path'])
        target.write_bytes(b'DEFGH')
        bad('mutated_component_detected_on_seek', lambda: f.seek(0))
        bad('mutated_component_close_still_releases_all_descriptors', f.close)
        for fd in fds:
            bad('closed_descriptor_%d' % fd, lambda fd=fd: os.fstat(fd))
        pins, expected, _ = build(root)
        f = v.VirtualArchive(root, pins, expected)
        Path(expected['components'][0]['path']).write_bytes(b'ABC')
        bad('same_length_component_change_detected_on_read', lambda: f.read(1))
        bad('mutation_close_audit', f.close)
        pins, expected, _ = build(root)
        p = Path(expected['components'][0]['path']);p.rename(root/'saved');p.symlink_to(root/'saved')
        bad('component_symlink_refused', lambda: v.VirtualArchive(root, pins, expected))
        p.unlink();(root/'saved').rename(p)
        pins, expected, _ = build(root)
        f = v.VirtualArchive(root, pins, expected)
        p = root/'supervisor-result.json';p.write_bytes(p.read_bytes()+b' ')
        bad('publication_metadata_mutation', lambda:f.read(1))
        bad('metadata_mutation_close_still_closes', f.close)
        pins, expected, _ = build(root)
        p=root/'worker-result.json';p.write_bytes(b'{"status":1,"status":2}')
        pins[p.name]=sha(p.read_bytes())
        bad('duplicate_JSON_metadata_key', lambda:v.VirtualArchive(root,pins,expected))
        p.write_bytes(b' '* (v.MAX_METADATA+1));pins[p.name]=sha(p.read_bytes())
        bad('metadata_hard_byte_cap', lambda:v.VirtualArchive(root,pins,expected))
        # Reader must never hash a component body on open or seek.
        pins, expected, _ = build(root)
        old_pread = os.pread
        def no_body(*args, **kwargs):
            raise AssertionError('implicit component body read')
        os.pread = no_body
        try:
            with v.VirtualArchive(root,pins,expected) as f:
                assert f.seek(2)==2 and f.tell()==2 and f.read(0)==b''
        finally:
            os.pread = old_pread
        names.append('open_seek_zero_close_do_not_implicitly_read_or_rehash_bodies')
        compressed = bz2.compress(b'<page>synthetic only</page>' * 30)
        cut = len(compressed)//3
        pins, expected, _ = build(root, blobs=[compressed[:cut],compressed[cut:2*cut],compressed[2*cut:]])
        with v.VirtualArchive(root,pins,expected) as f:
            with bz2.BZ2File(f, 'rb') as stream:
                assert stream.read(1000)==b'<page>synthetic only</page>'*30
        names.append('synthetic_bz2_consumer_crosses_components_not_publisher_validation')
    return {'status':'PASS_SYNTHETIC_ONLY_NO_PUBLISHER_BODY_NETWORK_LEDGER', 'controls':len(names), 'cases':names}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
