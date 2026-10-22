"""Verify completed fixed398 captured original JSON/text artifacts; no admission."""
import collections, datetime, hashlib, json, os
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()

def run():
    assert not (HERE / 'verification.json').exists()
    prep = BASE / 'pressbooks-fresh400-capture-preparation-v2'
    profile = json.loads((prep / 'profile.json').read_text())
    folder = Path(profile['output'])
    s = json.loads((folder / 'supervisor.json').read_text())
    r = json.loads((folder / 'result.json').read_text())
    o = json.loads((folder / 'ownership.json').read_text())
    assert s['status'] == 'COMPLETE_FRESH400_WHOLE_CAPTURE_NO_ADMISSION' and s['worker_exit_code'] == 0
    assert r['status'] == 'COMPLETE_FRESH400_DRAW_WHOLE_ORIGINAL_PRESSBOOKS_CAPTURE_NO_ADMISSION'
    assert r['profile_SHA256'] == sha(prep / 'profile.json') and r['codepins_SHA256'] == sha(prep / 'code-pins.json')
    for key in ['worker_PID', 'supervisor_PID']:
        try: os.kill(o[key], 0)
        except ProcessLookupError: pass
        else: raise AssertionError('owner still live')
    assert sha(folder / 'result.json') == s['result_SHA256']
    assert s['elapsed_seconds'] <= 300 and s['peak_observed_RSS_bytes'] <= 1000000000
    files = {p.name: p for p in folder.iterdir()}
    assert set(files) == set(r['artifacts']) | {'result.json', 'supervisor.json'}
    assert all(p.is_file() and not p.is_symlink() for p in files.values())
    assert sum(p.stat().st_size for p in files.values()) == s['all_output_bytes'] <= 64000000
    for name, expected in r['artifacts'].items():
        assert files[name].stat().st_size == expected['bytes'] and sha(files[name]) == expected['SHA256']
    assert sha(folder / 'records.json') == r['records_SHA256']
    records = json.loads((folder / 'records.json').read_text())
    selection = json.loads((prep / 'selection.json').read_text())
    assert records['draws'] == selection['draws'] and len(records['draws']) == 400
    wanted = {x['text_SHA256']: x for x in selection['selected_capture_occurrences']}
    captures = [x for source in records['sources'] for x in source['captures']]
    assert len(captures) == len(wanted) == 398 and len({x['text_SHA256'] for x in captures}) == 398
    textbytes = rawbytes = 0
    allroles = collections.Counter()
    for x in captures:
        t = wanted[x['text_SHA256']]
        assert (x['source_id'], x['ordinal']) == (t['source_id'], t['ordinal'])
        raw = (folder / x['raw_line_file']).read_bytes()
        text = (folder / x['text_file']).read_bytes()
        obj = json.loads(raw.decode('utf8'))
        assert obj['text'].encode('utf8') == text
        assert hashlib.sha256(raw).hexdigest() == x['raw_line_SHA256'] == t['line_SHA256']
        assert hashlib.sha256(text).hexdigest() == x['text_SHA256'] == t['text_SHA256']
        assert len(raw) == x['raw_line_bytes'] == t['line_bytes']
        assert len(text) == x['text_UTF8_bytes'] == t['text_UTF8_bytes']
        assert x['line_offset'] == t['line_offset'] and x['ends_LF'] == bool(t['ends_LF'])
        assert x['draw_roles'] == t['draw_roles'] and x['existing_M1_content_tokens'] == t['M1_content_tokens']
        allroles.update((a['mode'], a['draw'], a['text_SHA256']) for a in x['draw_roles'])
        textbytes += len(text); rawbytes += len(raw)
    assert allroles == collections.Counter((a['mode'], a['draw'], a['text_SHA256']) for a in records['draws'])
    assert textbytes == 10563953 and rawbytes == 11013981
    proof = dict(status='PASS_ALL398_CAPTURED_ORIGINAL_JSON_TEXT_AND400_DRAWROLES_INDEPENDENTLY_VERIFIED_NO_ADMISSION',
                 UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), exec_session=53140, exec_exit_code=0,
                 all_owner_PIDs_absent=True, output=str(folder), records_SHA256=sha(folder / 'records.json'),
                 result_SHA256=sha(folder / 'result.json'), supervisor_SHA256=sha(folder / 'supervisor.json'),
                 verifier_SHA256=sha(Path(__file__).resolve()), unique_captures=398, draws=400,
                 text_UTF8_bytes=textbytes, original_JSON_bytes=rawbytes,
                 elapsed_seconds=s['elapsed_seconds'], peak_RSS_bytes=s['peak_observed_RSS_bytes'],
                 original_all_row_CRC_SHA_frame_checks='Inherited reviewed capture producer; root independently checks all saved originalJSON/text/selection inverses and exact artifact hashes.',
                 semantic_quality_reviewed=False, rights_family_near_protected_cleared=False,
                 new_admitted_documents=0, new_admitted_tokens=0)
    with (HERE / 'verification.json').open('x') as f:
        json.dump(proof, f, indent=2); f.write('\n')
    print(json.dumps(proof))

if __name__ == '__main__': run()
