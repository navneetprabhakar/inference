"""Build 800 curated + 200 authored conversation candidates. Never trains a model.

Frozen old sets are read-only. Source records are hash-ranked before selection;
no first-N source ordering, template expansion, response truncation or rewriting.
"""
import collections, hashlib, html, json, re, statistics, sys
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer
from prepare_continuation import Near, fingerprint
from sft_common import ROOT, encode_episode, render
OUT=ROOT/'data/conversations-v1'
REPORT=ROOT/'reports/conversations-v1'
SEED='conversation-pilot-20261031-v1'
SOURCES=[ROOT/'data/sft-v2/raw/smol-smoltalk.parquet',ROOT/'data/sft-v3/raw/smol-smoltalk-1.parquet']

def norm(s):return ' '.join(s.casefold().split())
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def substantive(messages):
    return [m['content'] for m in messages if m['role']=='user' and len(re.findall(r'\w+',m['content']))>=4]
def family_text(messages):return '\n'.join(norm(s) for s in substantive(messages))
def read_jsonl(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def write_jsonl(p,rows):p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))

def clean_episode(ms):
    """Drop greeting pair and unanswered final user only; never cut an answer."""
    ms=[{'role':m['role'],'content':m['content']} for m in ms];edits=[]
    if any(m['role'] not in ('user','assistant') or not isinstance(m['content'],str) or not m['content'].strip() for m in ms):return None,['unsupported_role_or_empty']
    if ms and ms[-1]['role']=='user':ms=ms[:-1];edits.append('removed_unanswered_trailing_user')
    greeting=r'(hi|hello|hey|hi there|hey there|hello there|good morning|good afternoon|good evening)[!., ]*'
    if len(ms)>=4 and re.fullmatch(greeting,ms[0]['content'].strip(),re.I) and ms[1]['role']=='assistant':ms=ms[2:];edits.append('removed_opening_greeting_pair')
    if len(ms)<4 or len(ms)%2 or any(m['role']!=('user' if i%2==0 else 'assistant') for i,m in enumerate(ms)):return None,['not_complete_multiturn']
    return ms,edits

def quality_reason(ms):
    text='\n'.join(m['content'] for m in ms);letters=[x for x in text if x.isalpha()]
    if not letters or sum(c.isascii() for c in letters)/len(letters)<.98:return 'non_ascii_language_screen'
    if not re.search(r'\b(the|is|are|can|what|how|you|would|do|to|a|i)\b',text,re.I):return 'english_function_word_screen'
    if re.search(r'<\||```|https?://|\ufffd',text):return 'markup_code_url'
    if re.search(r'\b(role.?play|pretend|act as|in character|sexual|suicide|self.harm|diagnos\w*|medication|prescri\w*|invest\w*|stocks?|tax\w*|lawsuit|illegal|weapon|explosive|password)\b',text,re.I):return 'scope_excluded'
    if re.search(r'\b(exactly \d+|at least \d+|forbidden.words|placeholders?|entire response|highlight at least)\b',text,re.I):return 'artificial_constraint'
    for m in ms:
        if m['role']!='assistant':continue
        s=m['content']
        if len(s.split())>110:return 'long_assistant_turn'
        if re.search(r"\b(I(?:'ve| have) (?:visited|traveled|travelled|lived|owned)|my (?:dog|cat|wife|husband|children|child|home|favorite|favourite)|I (?:love|enjoy|remember when|went to)|as (?:a|an) (?:human|doctor|lawyer))\b",s,re.I):return 'possible_invented_persona'
        words=re.findall(r'\w+',s.lower());grams=[tuple(words[i:i+6]) for i in range(len(words)-5)]
        if len(grams)!=len(set(grams)):return 'repeated_sixword_phrase'
        if len(words)<2:return 'emptyish_answer'
    return None

def category(ms):
    """Routing labels for review only, not validated semantic annotations."""
    s=norm(' '.join(m['content'] for m in ms if m['role']=='user'))
    if re.search(r'\b(write|rewrite|edit|email|message|paragraph|sentence|grammar|letter|wording)\b',s):return 'writing'
    if re.search(r'\b(explain|why|how does|difference between|what is|what are|mean|learn|study|understand)\b',s):return 'explanations_learning'
    if re.search(r'\b(actually|instead|sorry|i meant|change my|correction)\b',s):return 'followup_correction'
    if re.search(r'\b(plan|organize|organise|trip|weekend|hobby|hobbies|garden|room|walk|book|travel|friend|relax|routine)\b',s):return 'everyday_planning'
    return 'other_conversation_review'

def main():
    if (OUT/'pilot-1000.jsonl').exists():raise RuntimeError('Pilot already exists; version rather than overwrite')
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
    protected_turns=set();protected_full=set();near=Near();protection={};oldtrain=set()
    for version in ['sft-v1','sft-v2','sft-v3']:
        for split in ['dev','test']:
            p=ROOT/'data'/version/(split+'.jsonl')
            if not p.exists():continue
            rr=read_jsonl(p);protection[str(p.relative_to(ROOT))]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'records':len(rr)}
            for r in rr:
                ms=r.get('episode',r.get('messages',[]));protected_full.add(digest(render(ms)))
                for s in substantive(ms):
                    protected_turns.add(norm(s));near.add(fingerprint(norm(s)))
        p=ROOT/'data'/version/'train.jsonl'
        if p.exists():
            for r in read_jsonl(p):
                for s in substantive(r.get('episode',r.get('messages',[]))):oldtrain.add(norm(s))
    authored=read_jsonl(OUT/'authored-batch-0001.jsonl')
    for p in sorted(OUT.glob('*.source.txt')):
        batch=[]
        for block in p.read_text().strip().split('\n\n'):
            lines=block.splitlines();assert len(lines)==5,(p,lines[0]);cat,scenario=lines[0].split('|')
            ms=[{'role':'user' if i%2==0 else 'assistant','content':s.replace('\\n','\n')} for i,s in enumerate(lines[1:])]
            batch.append({'id':'authored-v1-'+scenario,'family':scenario,'category':cat,'messages':ms,'provenance':{'method':'newly authored by assistant in this chat','synthetic':True,'template_expansion':False,'paid_generation_api':False,'source_file':p.name},'status':'candidate_pending_independent_review','split':'candidate_train'})
        write_jsonl(p.with_suffix('').with_suffix('.jsonl'),batch);authored+=batch
    assert len(authored)==200,len(authored)
    accepted_near=Near();seen_full=set();seen_first=set()
    def validate_overlap(ms,include_old=False):
        text=render(ms);ss=substantive(ms)
        if not ss:return 'no_substantive_user_turn'
        if digest(text) in protected_full or any(norm(s) in protected_turns for s in ss):return 'heldout_exact'
        if any(near.contains(fingerprint(norm(s))) for s in ss):return 'heldout_approximate'
        if include_old and any(norm(s) in oldtrain for s in ss):return 'old_training_user_overlap'
        if digest(text) in seen_full or norm(ss[0]) in seen_first:return 'pilot_exact_duplicate'
        if accepted_near.contains(fingerprint(norm(ss[0]))):return 'pilot_approximate_duplicate'
        return None
    def register(ms):
        seen_full.add(digest(render(ms)));ss=substantive(ms);seen_first.add(norm(ss[0]));accepted_near.add(fingerprint(norm(ss[0])))
    for r in authored:
        enc=encode_episode(tok,r['messages']);assert enc is not None,r['id']
        reason=validate_overlap(r['messages']);assert reason is None,(r['id'],reason)
        r.update(tokens=enc[2],assistant_target_tokens=int(enc[1].sum()),review_status='pending_independent_review');register(r['messages'])
    pools=collections.defaultdict(list);rejections=collections.Counter();readcounts=collections.Counter();receipts=[]
    for path in SOURCES:
        receipt=json.loads(path.with_name('receipt.json').read_text());actual=hashlib.sha256(path.read_bytes()).hexdigest();assert actual==receipt['sha256'],path
        receipts.append({'path':str(path.relative_to(ROOT)),'sha256':actual,'upstream':receipt})
        index=0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1024):
            for row in batch.to_pylist():
                row_index=index;index+=1;src=row['source'];readcounts[src]+=1
                if src not in ('everyday-conversations','smol-magpie-ultra-short'):continue
                ms,edits=clean_episode(row['messages'])
                if ms is None:rejections[src+':'+edits[0]]+=1;continue
                reason=quality_reason(ms)
                if reason:rejections[src+':'+reason]+=1;continue
                enc=encode_episode(tok,ms)
                if enc is None:rejections[src+':context_too_long']+=1;continue
                rawhash=digest(json.dumps(row['messages'],sort_keys=True,ensure_ascii=False));rank=digest(SEED+rawhash)
                pools[src].append((rank,{'id':'curated-'+rawhash,'family':digest(family_text(ms)),'category':category(ms),'category_method':'heuristic_pending_review','messages':ms,'tokens':enc[2],'assistant_target_tokens':int(enc[1].sum()),'provenance':{'method':'curated_local_unrewritten','upstream_source':src,'dataset':'HuggingFaceTB/smol-smoltalk','revision':receipt['revision'],'file':str(path.relative_to(ROOT)),'row_index':row_index,'original_messages_sha256':rawhash,'transformations':edits,'synthetic':'upstream_generated_conversations','license':'Apache-2.0 upstream receipt; no redistribution audit'},'review_status':'pending_independent_review','split':'candidate_train'}))
    print('Eligible pools', {k:len(v) for k,v in pools.items()},flush=True)
    # Balanced source selection; fallback explicitly recorded if everyday supply is insufficient.
    curated=[];selection=collections.Counter()
    for src,target in [('everyday-conversations',400),('smol-magpie-ultra-short',800),('everyday-conversations',800)]:
        for rank,r in sorted(pools[src],key=lambda x:x[0]):
            if len(curated)>=800 or (src=='everyday-conversations' and selection[src]>=target):break
            reason=validate_overlap(r['messages'],True)
            if reason:rejections[src+':'+reason]+=1;continue
            register(r['messages']);curated.append(r);selection[src]+=1
    assert len(curated)==800,('Insufficient eligible conversations',len(curated),selection)
    records=authored+curated;records.sort(key=lambda r:digest(SEED+r['id']))
    assert len({r['id'] for r in records})==1000
    ids=[];masks=[];lengths=[]
    for r in records:
        a,b,n=encode_episode(tok,r['messages']);assert a[n-1]==1 and b[n-2]==1
        ids.append(a);masks.append(b);lengths.append(n)
    write_jsonl(OUT/'authored-200.jsonl',authored);write_jsonl(OUT/'curated-800.jsonl',curated);write_jsonl(OUT/'pilot-1000.jsonl',records)
    np.savez_compressed(OUT/'pilot-episodes.npz',ids=np.stack(ids),mask=np.stack(masks),length=np.array(lengths,dtype=np.int32))
    manifest={'version':'conversation-pilot-v1','status':'prepared_candidates_pending_review_not_training_authorized','target_full_corpus':10000,'pilot_total':1000,'authored':200,'curated':800,'source_counts':dict(selection),'category_counts':dict(collections.Counter(r['category'] for r in records)),'category_labels':'authored labels explicit; curated heuristics pending review','turn_counts':dict(collections.Counter(len(r['messages']) for r in records)),'tokens':{'total_nonpadding':sum(lengths),'min':min(lengths),'median':statistics.median(lengths),'max':max(lengths),'assistant_targets':sum(r['assistant_target_tokens'] for r in records)},'protected_sets':protection,'sources':receipts,'raw_source_counts':dict(readcounts),'eligible_pool_counts':{k:len(v) for k,v in pools.items()},'rejections_encountered':dict(rejections),'selection_policy':'Hash-ranked whole source conversations. Target 400 everyday, fill from ultra-short, then use additional eligible everyday records if ultra-short is insufficient. Exclude exact old training user turns. Protect substantive old heldout user turns using exact normalization and 64-bit SimHash distance <=3. Reject first-substantive-user approximate matches within pilot. No semantic guarantee.','files':{},'training_started':False,'cloud_spend_usd':0,'limitations':['Candidates, not independently quality-approved training data.','English, topic and persona checks are heuristics; false positives/negatives remain.','Near-duplicate checks do not establish semantic or benchmark independence.','No new 200+200 dev/confirmation sets have been created; original heldouts are preserved.','No automatic scaling to 10000 or training.','Full source conversations are kept after optional greeting removal and unanswered final-user removal; no assistant response is truncated.']}
    for name in ['authored-200.jsonl','curated-800.jsonl','pilot-1000.jsonl','pilot-episodes.npz']:manifest['files'][name]=hashlib.sha256((OUT/name).read_bytes()).hexdigest()
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');REPORT.mkdir(exist_ok=True)
    (REPORT/'pilot-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Fixed hash-ranked source-stratified review sample, chosen without outcome ratings.
    sample=[]
    for origin,rr in [('authored',authored),('everyday', [r for r in curated if r['provenance']['upstream_source']=='everyday-conversations']),('ultra-short',[r for r in curated if r['provenance']['upstream_source']=='smol-magpie-ultra-short'])]:
        for r in sorted(rr,key=lambda r:digest('review'+r['id']))[:40]:sample.append({'origin':origin,**r})
    write_jsonl(REPORT/'review-sample.jsonl',sample)
    review=[{'id':r['id'],'origin':r['origin'],'naturalness':None,'correctness':None,'context_continuity':None,'unnecessary_verbosity':None,'accept':None,'notes':''} for r in sample]
    (REPORT/'review-ratings.json').write_text(json.dumps(review,indent=2)+'\n')
    body='<h1>Conversation pilot: 1,000 candidates</h1><p>200 newly authored + 800 curated locally. No training. Independent review pending. The 10,000-conversation target has not been reached.</p><h2>Audit</h2><pre>'+html.escape(json.dumps(manifest,indent=2))+'</pre><h2>Fixed review sample: 40 per origin</h2>'
    for r in sample:
        body+='<h3>'+html.escape(r['origin']+' / '+r['id'])+'</h3>'
        for m in r['messages']:body+='<p><b>'+m['role']+':</b> '+html.escape(m['content']).replace('\n','<br>')+'</p>'
    (REPORT/'PILOT_REPORT.html').write_text('<!doctype html><meta charset="utf-8"><title>Conversation pilot</title><style>body{font:16px/1.6 system-ui;max-width:1000px;margin:40px auto;padding:0 20px}pre{white-space:pre-wrap;background:#eee;padding:12px}h3{margin-top:40px;overflow-wrap:anywhere}</style>'+body)
    print(json.dumps({'total':len(records),'source_counts':selection,'tokens':manifest['tokens'],'review_cases':len(sample)},indent=2))
if __name__=='__main__':main()
