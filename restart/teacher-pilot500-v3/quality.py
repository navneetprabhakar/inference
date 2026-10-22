"""Stored-output validation and tokenizer counts; no student backend."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
from slm.common.tokenizer import BPE

ROOT=Path(__file__).resolve().parent
SMALL=['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty']

def contains(text,w):
    if re.search(r'(?<!\w)'+re.escape(str(w))+r'(?!\w)',text,re.I):return True
    return str(w).isdigit() and int(w)<len(SMALL) and re.search(r'\b'+SMALL[int(w)]+r'\b',text,re.I) is not None

def decision(text,wanted):
    first=re.search(r'(?i)\b(yes|no)\b',text)
    return first is not None and first[1].lower()==wanted.lower()

def check(r):
    flags=[];a=[m['content'] for m in r['messages'] if m['role']=='assistant'];f=r['family']
    for k,text in enumerate(a):
        if not text.strip():flags.append(f'empty:{k}')
        limit=r['wordcaps'][k]
        strict=re.search(r'(?i)under (\d+) words',r['users'][k])
        if strict:limit=min(limit,int(strict[1])-1)
        if len(text.split())>limit:flags.append(f'wordcap:{k}')
        for value in r['required'][k]:
            if not contains(text,value):
                inflected=(f=='word_distinctions' and any(contains(text,value+suffix) for suffix in ('d','s','ing')))
                if not inflected:flags.append(f'missing_required:{k}:{value}')
        oracle=r['oracle_notes'][k]
        if f in ('capacity_decisions','budget_revisions') and oracle.startswith(('Yes','No')):
            if not decision(text,oracle.split(';')[0]):flags.append(f'wrong_yes_no:{k}')
        if f in ('capacity_decisions','unit_conversion','stock_accounting','budget_revisions','cart_totals','weekday_offsets','rule_based_labels','sorting_and_selection','sequential_schedules','price_comparisons'):
            if f=='weekday_offsets':need=[oracle]
            elif f=='rule_based_labels':need=[oracle]
            elif f=='sequential_schedules':need=re.findall(r'\d\d:\d\d',oracle)
            else:need=re.findall(r'\b\d+\b',oracle)
            for value in need:
                if not contains(text,value):flags.append(f'oracle_value_missing:{k}:{value}')
        if f=='price_comparisons':
            if oracle.startswith(('A ','B ')) and not contains(text,oracle[0]):flags.append(f'wrong_option:{k}')
            if oracle.startswith('They') and not re.search(r'(?i)\b(same|equal|tie)\b',text):flags.append(f'missing_tie:{k}')
        if f=='json_formatting':
            stripped=re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip())
            try:
                if json.loads(stripped)!=json.loads(oracle):flags.append(f'incorrect_json:{k}')
            except ValueError:flags.append(f'invalid_json:{k}')
        if f=='impossible_constraints' and k==0 and not re.search(r"(?i)\b(no|impossible|cannot|can't|not possible)\b",text):flags.append('missed_infeasibility')
        if f=='capability_honesty' and re.search(r"(?i)\bI (?:have |just )?(?:sent|booked|set|moved|checked|turned|posted|called|uploaded|cancelled)\b",text):flags.append(f'fabricated_action:{k}')
    if f=='format_constraints':
        lines=[l for l in a[0].splitlines() if re.match(r'^\s*[-*•]\s+',l)]
        if len(lines)!=3 or any(len(re.sub(r'^\s*[-*•]\s+','',l).split())>6 for l in lines):flags.append('bullet_constraint')
    return flags

def main():
    bpe=BPE.load(ROOT.parent/'execution-v1/tokenizer-8192')
    rows=[]
    for p in sorted(ROOT.glob('completed-*.json')):rows.extend(json.loads(p.read_text()))
    rows.sort(key=lambda r:r['id']);totals=defaultdict(Counter);flags=Counter();seen=set();clear=[]
    for r in rows:
        issues=check(r)
        x,y,mask=bpe.serialize(r['messages'])
        if len(y)>512:issues.append('exceeds_context512')
        full=json.dumps(r['messages'],sort_keys=True,ensure_ascii=False)
        h=hashlib.sha256(full.encode()).hexdigest()
        if h in seen:issues.append('exact_duplicate')
        seen.add(h)
        r['quality_flags']=issues;r['counts']=dict(content_tokens=sum(len(bpe.encode(m['content'])) for m in r['messages']),
               assistant_supervised_targets=sum(mask),predicted_positions=len(y))
        flags.update(issues)
        if not issues:
            clear.append(r)
            for s in ('all',r['split']):totals[s].update(r['counts']);totals[s].update(documents=1)
    (ROOT/'checked.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    for s in ('train','development','test'):
        (ROOT/(s+'-candidates.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in clear if r['split']==s))
    report=dict(generated=len(rows),automated_clear=len(clear),flags=dict(flags),counts={s:dict(v) for s,v in totals.items()},semantic_acceptance=False)
    if len(rows)==500:
        shingles=[];near=[]
        for r in clear:
            words=re.findall(r'\w+',' '.join(m['content'] for m in r['messages']).lower())
            shingles.append(set(zip(*(words[j:] for j in range(5)))))
        for i,a in enumerate(shingles):
            for j in range(i+1,len(shingles)):
                if clear[i]['split']==clear[j]['split']:continue
                b=shingles[j];overlap=len(a&b);score=overlap/(len(a)+len(b)-overlap)
                if score>=.8:near.append(dict(a=clear[i]['id'],b=clear[j]['id'],score=score))
        report['cross_split_word5gram_jaccard80_pairs']=near
    (ROOT/'automated-review.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
