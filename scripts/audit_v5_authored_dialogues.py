"""Audit literal current-auth teacher batches without exposing sealed evaluation text."""
import hashlib,json,re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/eight-hour-improvement-v5-authored'
EVAL=ROOT/'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2'
OUT=ROOT/'runs/eight-hour-improvement-v5-authored'
def norm(s): return ' '.join(re.findall(r'\w+',s.casefold()))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    rows=[]
    for p in sorted(DATA.glob('batch-*.jsonl')):
        rows += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    errors=[]; ids=set(); turns=[]
    # Hash-only leakage check: comparison consumes sealed text but never emits it.
    eval_openings=set()
    for p in [EVAL/'development.jsonl',EVAL/'confirmation.jsonl']:
        for x in p.read_text().splitlines():
            eval_openings.add(norm(json.loads(x)['turns'][0]['user']))
    opening=set(); full=set()
    for r in rows:
        ident=r.get('id'); msg=r.get('messages',[]); prov=r.get('provenance',{})
        if not ident or ident in ids: errors.append(f'duplicate id:{ident}')
        ids.add(ident)
        if prov.get('source_model')!='gpt-5.6-terra current-auth Codex CLI': errors.append(f'{ident}:source identity')
        if not prov.get('substantive_correctness_review'): errors.append(f'{ident}:missing review')
        users=[m['content'] for m in msg if m.get('role')=='user']
        assistants=[m['content'] for m in msg if m.get('role')=='assistant']
        if not 2<=len(users)<=4 or len(assistants)<len(users): errors.append(f'{ident}:not genuine 2-4 user-turn dialogue')
        key=tuple(norm(x) for x in users)
        if not users or norm(users[0]) in opening or key in full: errors.append(f'{ident}:duplicate dialogue')
        opening.add(norm(users[0])); full.add(key)
        if users and norm(users[0]) in eval_openings: errors.append(f'{ident}:evaluation opening leakage')
        turns.append(len(users))
    report={'kind':'literal_current_auth_teacher_batch_audit','records':len(rows),'batches':len(list(DATA.glob('batch-*.jsonl'))),'families':dict(Counter(r['family'] for r in rows)),'user_turn_distribution':dict(Counter(turns)),'errors':errors,'dataset_sha256':hashlib.sha256(''.join(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n' for r in rows).encode()).hexdigest(),'evaluation_hashes':{p.name:digest(p) for p in [EVAL/'development.jsonl',EVAL/'confirmation.jsonl']},'sealed_evaluation_content_emitted':False,'limitations':['Structural and provenance-label audit only; admission also requires actual per-case semantic review, fixture replay and context checks. Record count alone does not establish quality.']}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    raise SystemExit(bool(errors))
if __name__=='__main__':main()
