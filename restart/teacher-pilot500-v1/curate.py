"""Conservative post-pilot salvage, with raw records retained unchanged."""
# Creator: Navneet Prabhakar
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from slm.common.tokenizer import BPE

ROOT=Path(__file__).resolve().parent.parent/'teacher-pilot500-v2'
TOKENIZER=ROOT.parent/'execution-v1/tokenizer-8192'
MASS_PLURAL=['clay','gloves','binoculars','yarn','paper','fabric','thread','notes',
             'safety goggles','scissors','walking shoes','wool','string']

def sha(x):return hashlib.sha256(x.encode()).hexdigest()
def write(name,data):(ROOT/name).write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n')

def grammar(text):
    for noun in MASS_PLURAL:text=re.sub(r'\ba '+re.escape(noun)+r'\b',noun,text,flags=re.I)
    for noun in ['apron','instrument','ID card']:
        text=re.sub(r'\ba '+re.escape(noun)+r'\b','an '+noun,text,flags=re.I)
    return text

def issues(row):
    result=[];answers=[m['content'] for m in row['messages'] if m['role']=='assistant']
    for reason in row['automated_issues']:
        if reason.startswith('missing_required_'):
            turn=int(reason.split('turn')[1][0]);required=reason.split(':',1)[1]
            if required=='1' and re.search(r'\bone\b',answers[turn-1],re.I):continue
        result.append(reason)
    category=row['category']
    if category=='reasoning':
        if not re.match(r'(?i)^yes\b',answers[0]):result.append('fit_first_answer_requires_review')
        if re.match(r'(?i)^yes\b',answers[1]):result.append('contradictory_yes_when_over_capacity')
        elif not re.match(r'(?i)^no\b',answers[1]):result.append('fit_second_answer_requires_review')
    if category=='clarification':
        if re.search(r'(?i)\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',answers[0]):
            result.append('assumed_weekday_absent_from_own_context')
        if answers[0].count('?')!=1:result.append('not_exactly_one_clarification_question')
    if category=='rewrite' and re.search(r'(?i)\b(borrow|bring|lend)\b',' '.join(answers)):
        result.append('rewrite_changes_give_request_intent')
    if category=='summary':
        words=[w for w in row['users'][0].split('Fictional event note: ')[1].split(';')[0].split()
               if w.lower() not in {'class','session','meetup','lesson','circle','group','workshop','event','practice','community'}]
        if not any(re.search(r'(?i)\b'+re.escape(w)+r'\b',answers[1]) for w in words):
            result.append('low_information_second_summary_no_event_topic')
    return result

def main():
    bpe=BPE.load(TOKENIZER);rows=[json.loads(l) for l in (ROOT/'candidates.jsonl').read_text().splitlines()]
    if len(rows)!=500:raise ValueError('Complete 500 required before final curation')
    kept=[];held=[];reasons=Counter();repairs=Counter();counts=defaultdict(Counter);duplicate=set()
    for r in rows:
        r['quality_holds']=issues(r);reasons.update(r['quality_holds'])
        if r['quality_holds']:held.append(r);continue
        original=json.dumps(r['messages'],ensure_ascii=False,sort_keys=True)
        edits=[]
        for index,m in enumerate(r['messages']):
            fixed=grammar(m['content'])
            if fixed!=m['content']:
                edits.append(dict(message=index,before=m['content'],after=fixed));m['content']=fixed
                repairs[m['role']+'_messages']+=1
        r['grammar_edits']=edits;r['raw_messages_sha256']=sha(original)
        r['raw_teacher_batch']=f"batch-{int(r['id'][1:3]):02d}/last.json"
        if edits:repairs['conversations']+=1
        serial=json.dumps(r['messages'],sort_keys=True,ensure_ascii=False)
        if sha(serial) in duplicate:raise ValueError('Duplicate survived')
        duplicate.add(sha(serial));x,y,mask=bpe.serialize(r['messages'])
        r['counts']=dict(content_tokens=sum(len(bpe.encode(m['content'])) for m in r['messages']),
            serialized_predicted_positions=len(y),assistant_supervised_targets=sum(mask),
            utf8_bytes=sum(len(m['content'].encode()) for m in r['messages']))
        if len(y)>512:raise ValueError('Context changed beyond limit')
        for key in ('all',r['split']):counts[key].update(r['counts']);counts[key].update(documents=1)
        r['eligibility']='curated diagnostic candidate; release and training readiness assessed separately'
        kept.append(r)
    for name,values in [('curated.jsonl',kept),('held.jsonl',held)]:
        (ROOT/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in values))
    shared={}
    for category in sorted({r['category'] for r in rows}):
        chosen=[r for r in rows if r['category']==category];pairs=Counter()
        first=Counter();second=Counter()
        for r in chosen:
            a=[m['content'] for m in r['messages'] if m['role']=='assistant']
            pairs[tuple(a)]+=1;first[a[0]]+=1;second[a[1]]+=1
        shared[category]=dict(conversations=len(chosen),distinct_assistant_pairs=len(pairs),
                             most_common_first=first.most_common(1),most_common_second=second.most_common(1))
    utterances=defaultdict(set)
    for r in kept:
        for m in r['messages']:
            if m['role']=='assistant':utterances[m['content']].add(r['split'])
    overlaps=[dict(text=t,splits=sorted(s)) for t,s in utterances.items() if len(s)>1]
    write('curation-counts.json',dict(generated=500,kept_candidates=len(kept),held=len(held),
        hold_reason_events=dict(reasons),grammar_repair_counts=dict(repairs),
        counts={k:dict(v) for k,v in counts.items()},
        exact_full_conversation_duplicates=len(kept)-len(duplicate),
        category_repetition=shared,exact_assistant_utterances_shared_across_splits=overlaps,
        independent_generalization_evaluation_ready=False,
        scope='Actual M1-tokenizer counts of curated candidates, not new admissions to the original frozen corpus. Reused templates and answer strings invalidate any claim of independent broad-English evaluation.'))

if __name__=='__main__':main()
