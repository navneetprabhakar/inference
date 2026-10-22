"""Re-derive labels from rendered text, then screen full task contexts."""
import collections,csv,hashlib,json,re,sqlite3
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.restart.edu_filter import normalized
O=Path(__file__).resolve().parent;R=O.parents[2];TOK=BPE.load(O.parent/'tokenizer-8192')

def answer_from_text(row,passage):
    kind=row['detail_subtype'];question=row['question']
    if kind=='explicit_fact':
        target=re.fullmatch(r'What color was the (scarf|glove)\?',question).group(1)
        colors='red|blue|green|white'
        matches=re.findall(r'\b('+colors+r') '+target+r'\b',passage)
        matches+=re.findall(r'\b'+target+r' (?:was|looked|colored|that was) ('+colors+r')\b',passage)
        assert len(matches)==1
        return matches[0]
    if kind=='temporal':
        states=re.findall(r'beside the (box|bed|bag|cup)\b',passage)
        assert len(states)==4 and len(set(states))==4
        if 'after the first' in question or 'before its second' in question:index=1
        elif 'after the second' in question or 'before its third' in question:index=2
        elif 'after the final' in question or 'all moves were finished' in question:index=3
        else:raise AssertionError('Unknown temporal question')
        return states[index]
    names=[re.fullmatch(r' It was ([A-Za-z]+)\.',x).group(1) for x in row['alternatives']]
    pattern='|'.join(map(re.escape,names))
    matches=re.findall(r'\bto ('+pattern+r')\b',passage)
    matches+=re.findall(r'\b('+pattern+r') (?:accepted a small bell|was given a candle)\b',passage)
    assert len(matches)==1
    return matches[0]

def main():
    allrows=[];hashes={};patterns=[];inverted=collections.defaultdict(set);seen=set();stats={}
    for split in ['development','final']:
        p=O/(split+'-grounded-v2-candidates.jsonl');hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        rows=[json.loads(x) for x in p.read_text().splitlines()];lookup={r['id']:r for r in rows}
        assert len(lookup)==100 and collections.Counter(r['subtype'] for r in rows)=={'explicit_fact':50,'temporal_reference':50}
        assert collections.Counter(r['correct_index'] for r in rows)==dict.fromkeys(range(4),25)
        for row in rows:
            norm=normalized(row['prompt']);assert norm not in seen;seen.add(norm)
            lengths=[len(TOK.encode(x)) for x in row['alternatives']]
            assert lengths==row['continuation_token_lengths'] and len(set(lengths))==1
            answer=answer_from_text(row,row['passage'])
            assert answer==row['oracle']['answer']
            assert row['alternatives'][row['correct_index']].endswith(' '+answer+'.')
            source=lookup[row['controls']['shuffled_source_id']]
            assert source['id']!=row['id'] and source['question']==row['question']
            assert row['controls']['shuffled_prompt']==source['passage']+'\nQuestion: '+row['question']+'\nAnswer:'
            assert row['controls']['empty_prompt']=='Question: '+row['question']+'\nAnswer:'
            assert answer_from_text(row,source['passage'])!=answer
            for label,text in [('passage',row['passage']),('full_task',row['prompt']+row['alternatives'][row['correct_index']])]:
                norm=normalized(text);words=norm.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)}
                idx=len(patterns);patterns.append((row['id'],label,norm,grams))
                for gram in grams:inverted[gram].add(idx)
        stats[split]={'items':100,'template_families':len({r['template_family'] for r in rows})}
        allrows.extend(rows)
    manifest=R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
    with manifest.open() as f:train={int(r['audit_id']) for r in csv.DictReader(f) if r['split']=='train'}
    db=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True);hits=[];counts=collections.Counter()
    def scan(key,origin,text):
        words=text.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)};candidates=collections.Counter()
        for gram in grams:
            for idx in inverted.get(gram,()):candidates[idx]+=1
        for idx,n in candidates.items():
            item,label,norm,need=patterns[idx];exact=(' '+norm+' ') in (' '+text+' ')
            if exact or n/len(need)>=.8:hits.append(dict(item=item,part=label,document=key,origin=origin,exact=exact,fivegram_fraction=n/len(need)))
        counts[origin]+=1
    for key,text in db.execute('SELECT id,normalized FROM docs'):
        if key in train:scan(key,'training',text)
    for key,text in db.execute('SELECT id,normalized FROM protections'):scan(key,'existing_protection',text)
    result={'status':'DRAFT_VALIDATED_LEXICAL_SCREEN_PASS' if not hits else 'OVERLAP_REVIEW_REQUIRED','inputs_sha256':hashes,'split_counts':stats,'text_derived_oracles_verified':len(allrows),'empty_controls_verified':len(allrows),'shuffled_controls_verified':len(allrows),'screened_documents':dict(counts),'hits':hits,'limitations':['Same assistant authored templates and reviewed rendered examples; not independent human certification.','Only 11 template families per split, including one temporal story frame. No broad comprehension claim.','Shuffled controls are compatible-question derangements constrained to a different supported answer; they are counterfactual controls, not unrestricted random passage shuffles. Original answer key is retained for comparison.','Passage and complete task screened for exact containment and >=80% distinct fivegram overlap. Generic answer sentences alone are not leakage evidence.','Full ancestry audit, combined suite freeze, final custody binding and neural scoring remain outstanding.']}
    (O/'grounded-v2-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='hits'}|{'hit_count':len(hits)},indent=2))
if __name__=='__main__':main()
