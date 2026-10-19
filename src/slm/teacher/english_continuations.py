"""Versioned style-controlled candidate composition; never grants training admission."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.teacher.english_batch import EnglishRecipe, continuations
from slm.teacher.sol import parse_sol_events


def checked_capture(record,journal,capture_base):
    raw=journal.cached(record['request_key'])
    if raw is None or digest(raw)!=record['raw_response_sha256']:raise ValueError('Completed original response required')
    capture=raw['capture'];root=Path(capture['root'])
    if root.is_symlink() or root.resolve().parent!=Path(capture_base).resolve():raise ValueError('Original private capture location required')
    limits={'prompt.txt':65536,'schema.json':65536,'events.jsonl':512*1024,
            'stderr.txt':128*1024,'last.json':16384,'process-terminal.json':1024}
    if set(capture['files'])!=set(limits) or {p.name for p in root.iterdir()}!=set(limits):raise ValueError('Exact bounded capture files required')
    for name,bound in limits.items():
        p=root/name
        if p.is_symlink() or not p.is_file() or p.stat().st_size>bound or sha(p)!=capture['files'][name]:
            raise ValueError('Original capture changed: '+name)
    if json.loads((root/'process-terminal.json').read_text())!=dict(process_terminal=True,returncode=0):raise ValueError('Actual successful terminal CLI required')
    request=record['request']
    prompt=request['instructions']+'\nSCENARIOS:\n'+json.dumps(request['batch'],sort_keys=True,ensure_ascii=False)
    if (root/'prompt.txt').read_text()!=prompt or json.loads((root/'schema.json').read_text())!=request['schema']:
        raise ValueError('Captured prompt/schema differs from hashed request')
    replay=parse_sol_events((root/'events.jsonl').read_text(),(root/'last.json').read_text(),EnglishRecipe(**request['recipe']))
    if replay!={k:v for k,v in raw.items() if k!='capture'}:raise ValueError('Captured events/final/usage differ from cache')
    return capture


def compose(record,journal,exclusions,tokenizer,*,tokenizer_sha256,capture_base,max_length=1024):
    capture=checked_capture(record,journal,capture_base)
    base=continuations(record,journal,exclusions);out=[]
    for row,scenario in zip(base,record['request']['batch'],strict=True):
        expected='user'
        for message in scenario['context']:
            if message['role']!=expected or not message['content'].strip():raise ValueError('Complete alternating history required')
            expected='assistant' if expected=='user' else 'user'
        control=f"Response style: {scenario['style']}. Content setting: {scenario['content_category']}."
        messages=[dict(role='system',content=control),*deepcopy(row['messages'])]
        if exclusions.matches('\n'.join(m['content'] for m in messages)):raise ValueError('Protected text in composed candidate')
        x,y,mask=tokenizer.serialize(messages,supervision='last-user-turn-v1',max_length=max_length)
        content_targets=len(tokenizer.encode(messages[-1]['content']))
        if sum(mask)!=content_targets+2:raise ValueError('Only final assistant content/end markers may be supervised')
        out.append(dict(**{k:v for k,v in row.items() if k!='messages'},version=2,
            kind='style-controlled-sol-english-candidate-v2',messages=messages,style=scenario['style'],content_category='sfw',
            physical_positions=len(x),assistant_targets=sum(mask),assistant_content_targets=content_targets,
            tokenizer_manifest_sha256=tokenizer_sha256,host_style_control_sha256=digest(control),
            captured_files_sha256=digest(capture['files']),uncontrolled_v1_candidate_sha256=digest(row),
            source_evidence_complete=False,training_release_approved=False))
    return out
