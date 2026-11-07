"""Independent graph/disposition/byte replay; shared frozen framing only.

No packer/grouping imports, private cases, model, GPU, or admission.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,hashlib,importlib.metadata,json,pathlib,re,resource,shutil,signal,sqlite3,struct,sys,time,unicodedata
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(R))
S=R/'data/everyday-source-review-v1';D=R/'data/everyday-packed-v1'
DECISION_SHA='7bb6fb06e0b6cc1a745fda34713f3e0bcf45d8a295187c783e75e683fd9b0d62'
PACKER_SHA='17278635fa8b9beaa54818a3ed30606bce660a27376b38551fe81959b7f717fc'
OUTPUTS={'rows.jsonl','train.inputs.u16','train.labels.u16','components.json','history-decisions.json','freeze.json','histories.jsonl'}

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(p):
    with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def canon(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def value_sha(value):return hashlib.sha256(canon(value).encode()).hexdigest()
def normalized(text):return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())

def independent_graph(histories,check=lambda:None):
    """All-pairs graph, then graph traversal (no packer's union/inverted index)."""
    ids=sorted(histories);text={};features={};adj={i:set() for i in ids};edges=[];first={}
    for i in ids:
        check();text[i]='\n'.join(m['role']+': '+normalized(m['content']) for m in histories[i])
        words=re.findall(r'\w+',normalized(text[i]));features[i]={tuple(words[k:k+5]) for k in range(len(words)-4)}
    for index,i in enumerate(ids):
        check()
        if text[i] in first:
            j=first[text[i]];edges.append(dict(left=j,right=i,kind='exact'));adj[i].add(j);adj[j].add(i)
        else:first[text[i]]=i
        for j in ids[:index]:
            f,g=features[i],features[j];shared=len(f.intersection(g))
            if shared<8:continue
            union=len(f)+len(g)-shared;minimum=min(len(f),len(g))
            if shared/union>=.65 or shared/minimum>=.8:
                edges.append(dict(left=j,right=i,kind='strong_lexical',shared=shared,union=union,minimum=minimum));adj[i].add(j);adj[j].add(i)
    groups={}
    for i in ids:
        if i in groups:continue
        pending=[i];component=set()
        while pending:
            at=pending.pop()
            if at in component:continue
            component.add(at);pending.extend(adj[at]-component)
        smallest=min(component)
        groups.update((at,smallest) for at in component)
    return groups,text,edges

def u16(values,labels=False):
    need(all(type(v)is int and (0<=v<=50256 or labels and v==-100) for v in values),'valid token/label vocabulary')
    return struct.pack('<'+'H'*len(values),*(65535 if v==-100 else v for v in values))

def run():
    start=time.monotonic();os.nice(10)
    def timeout(*args):raise TimeoutError('packed replay deadline')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(600)
    def check():
        if any(p.exists() for p in (R/'runs/STOP',H/'STOP',S/'STOP',D/'STOP')):raise RuntimeError('STOP')
        if time.monotonic()-start>=600:raise RuntimeError('wall limit')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)>=2*1024**3:raise RuntimeError('RSS limit')
        if shutil.disk_usage(R).free<20*1024**3:raise RuntimeError('disk floor')
    target=D/'independent-verification.json';pending=D/'independent-verification.pending.json'
    need(not target.exists() and not pending.exists(),'preserve prior verification')
    report=dict(state='FAIL_independent_everyday_packing_not_admitted',training_admitted=False,failures=[])
    try:
        check()
        from own_base_chat_rows import build_chat_rows
        from tokenizer import ASSETS,load
        manifest=read(D/'manifest.json');freeze=read(D/'freeze.json');decision_path=H/'packing-decision-v1.json';decision=read(decision_path)
        need(sha(decision_path)==DECISION_SHA==manifest['decision_sha256']==freeze['decision_sha256'],'root decision binding')
        need(sha(H/'pack_train_v1.py')==PACKER_SHA,'reviewed packer version')
        need(manifest['state']=='prepared_train_only_pending_independent_verification' and manifest['training_admitted'] is False,'complete train-only packing')
        need(freeze['state']=='frozen_before_packing' and freeze['training_admitted'] is False and sha(D/'freeze.json')==manifest['freeze_sha256'],'freeze binding')
        need(set(manifest['outputs'])==OUTPUTS,'exact output inventory')
        need({p.name for p in D.iterdir()}==OUTPUTS|{'manifest.json'},'no extra packed output or DEV')
        pinned={str(D/'manifest.json'):sha(D/'manifest.json'),str(pathlib.Path(__file__)):sha(pathlib.Path(__file__))}
        required=[S/n for n in ('review.sqlite','review-queue.jsonl','receipt.json','independent-extraction-verification.json','custody.json')]+[H/n for n in ('quality-review-summary.json','full-fit-profile.json','intake-policy.json','packing-decision-v1.json','pack_train_v1.py','check_pack_train_v1.py','grouping_draft.py')]+[R/n for n in ('own_base_chat_rows.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tokenizer.py','tools/__init__.py')]+[R/'data/tokenizer'/n for n in ASSETS]
        need(set(freeze['pins'])=={str(p.relative_to(R)) for p in required},'exact complete frozen input inventory')
        for name,expected in freeze['pins'].items():
            check();p=R/name;need(not p.is_symlink() and sha(p)==expected,'input pin '+name);pinned[str(p)]=expected
        for name,entry in manifest['outputs'].items():
            check();p=D/name;need(p.is_file() and not p.is_symlink() and p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'],'output pin '+name);pinned[str(p)]=entry['sha256']
        need(freeze['limits']==dict(seconds=600,rss_bytes=2*1024**3,output_bytes=256*1024**2,free_bytes=20*1024**3),'packing limits')
        layout=dict(context=1024,reply_budget=256,permit_calls=True,allowed_names=None,all_or_none=True)
        need(freeze['layout']==layout and freeze['tokenizer_assets']==ASSETS,'framing freeze')
        receipt=read(S/'receipt.json');proof=read(S/'independent-extraction-verification.json');custody=read(S/'custody.json');quality=read(H/'quality-review-summary.json');profile=read(H/'full-fit-profile.json')
        need(receipt['state']=='full_history_review_queue_not_admitted' and receipt['failure'] is None and receipt['training_admitted'] is False,'complete source')
        need(proof['state']=='PASS_extract_not_admitted' and proof['failures']==[] and proof['verified_rows']==1130 and proof['training_admitted'] is False,'independent extraction')
        need(proof['database_sha256']==receipt['database_sha256']==custody['database_sha256']==sha(S/'review.sqlite'),'source DB bindings')
        need(proof['receipt_sha256']==sha(S/'receipt.json') and proof['queue_sha256']==receipt['queue_sha256']==sha(S/'review-queue.jsonl') and proof['policy_sha256']==receipt['policy_sha256']==sha(H/'intake-policy.json'),'full source proof binding')
        need(custody['state']=='screened_not_admitted' and custody['training_admitted'] is False and custody['reviewed']==1130,'complete custody')
        need(set(custody['pins'])=={'review.sqlite','review-queue.jsonl','receipt.json','independent-extraction-verification.json'},'custody proof inventory')
        for name,expected in custody['pins'].items():need(sha(S/name)==expected,'custody artifact binding')
        need(decision['state']=='root_reviewed_train_only_packing_not_admitted' and decision['training_admitted'] is False and decision['eligible_status']=='old_train' and set(decision['quarantined_statuses'])=={'unknown','excluded'},'root train-only policy')
        need(quality['state']=='complete_fixed_sample_review_not_admitted' and quality['training_admitted'] is False and decision['quality_review_sha256']==sha(H/'quality-review-summary.json'),'quality binding')
        sample_bad={r['doc_id'] for r in quality['records'] if r['decision']!='retain'}
        need(len(sample_bad)==27 and sample_bad==set(decision['excluded_sample_doc_ids']),'27 exact exclusions')
        need(profile['state']=='completed_mechanical_full_history_fit_not_admitted' and profile['training_admitted'] is False and profile['layout']==layout,'fit provenance')
        need(profile['runtime']['python']==sys.version and profile['runtime']['tokenizers']==importlib.metadata.version('tokenizers'),'same framing runtime')
        for name,expected in profile['input_pins'].items():check();need(sha(R/name)==expected,'fit input pin');pinned[str(R/name)]=expected
        with sqlite3.connect('file:'+str(S/'review.sqlite')+'?mode=ro',uri=True) as db:
            need(db.execute('pragma quick_check').fetchone()==('ok',),'source SQLite');db.row_factory=sqlite3.Row
            source={r['doc_id']:dict(r) for r in db.execute('select * from histories order by doc_id')}
        need(len(source)==1130 and dict(collections.Counter(r['status'] for r in source.values()))==dict(old_train=770,excluded=41,unknown=319),'full original inventory')
        histories={i:json.loads(r['messages_json']) for i,r in source.items()}
        for i,messages in histories.items():check();need(value_sha(messages)==source[i]['history_sha256'],'full original history SHA')
        need(sample_bad<=source.keys() and all(source[i]['status']=='old_train' for i in sample_bad),'sample exclusions original status')
        for r in quality['records']:need(source[r['doc_id']]['history_sha256']==r['history_sha256'],'sample original history')
        denied=set(custody['excluded_doc_ids']);need(len(denied)==len(custody['excluded_doc_ids']) and denied<=source.keys(),'complete custody IDs')
        groups,texts,edges=independent_graph(histories,check)
        bad={i for i,r in source.items() if r['status']!='old_train'}|denied|sample_bad;bad_groups={groups[i] for i in bad}
        need(read(D/'components.json')==dict(groups=groups,edges=edges,initial_quarantine_ids=sorted(bad),quarantined_components=sorted(bad_groups)),'independent complete component/edge replay')
        duplicate={};keepers={};selected=[]
        for i in sorted(source):
            if groups[i] in bad_groups:continue
            need(source[i]['status']=='old_train','train-only surviving component')
            if texts[i] in keepers:duplicate[i]=keepers[texts[i]]
            else:keepers[texts[i]]=i;selected.append(i)
        dispositions={i:dict(doc_id=i,component=groups[i],status=source[i]['status'],decision='quarantine_component' if groups[i] in bad_groups else 'duplicate' if i in duplicate else 'pending_frame',duplicate_of=duplicate.get(i)) for i in sorted(source)}
        counts=dict(histories=0,rows=0,targets=0,refused_histories=0);exposure=collections.Counter();offset=0;tokenizer=load();profiles={r['doc_id']:r for r in profile['documents']}
        need(len(profiles)==profile['profiled_histories'],'unique fit profiles')
        with (D/'train.inputs.u16').open('rb') as inputs,(D/'train.labels.u16').open('rb') as labels,(D/'rows.jsonl').open() as rows,(D/'histories.jsonl').open() as provenance:
            for i in selected:
                check();r=source[i];messages=histories[i]
                try:
                    need(all(type(m)is dict and set(m)=={'role','content'} for m in messages),'exact message fields')
                    history=[dict(role=m['role'],text=m['content']) for m in messages]
                    built=build_chat_rows(tokenizer,history,provenance=dict(doc_id=i,raw_history_sha256=r['history_sha256']))
                except ValueError as error:
                    dispositions[i].update(decision='refused_full_history',reason=str(error));counts['refused_histories']+=1;continue
                need(built['metadata']['original_history']==history,'full mapped original preservation')
                prior=profiles[i];need(prior['fit'] is True and prior['history_sha256']==r['history_sha256'] and prior['rows']==len(built['rows']) and prior['supervised_targets']==built['counters']['supervised_targets'] and prior['row_input_tokens']==[len(x.inputs) for x in built['rows']] and prior['row_targets']==[x.target_count for x in built['rows']],'profile match')
                begin=offset
                for turn,row in enumerate(built['rows']):
                    check();need(len(row.inputs)==len(row.labels),'aligned lengths');target_count=sum(v!=-100 for v in row.labels);need(target_count==row.target_count,'target recount')
                    pos={key:0 for key in ('0..255','256..511','512..767','768..1023')}
                    for index,value in enumerate(row.labels):
                        if value!=-100:
                            position=index+1;need(position<1024,'target context position');low=position//256*256;pos[f'{low}..{low+255}']+=1
                    need(pos==built['per_row_position_exposure'][turn],'position recount')
                    expected=dict(source='everyday-conversations',doc_id=i,turn=turn,family=groups[i],split='train',offset=offset,length=len(row.inputs),target_count=target_count,original_history_sha256=built['metadata']['original_history_sha256'],raw_history_sha256=r['history_sha256'],position_exposure=pos)
                    need(json.loads(rows.readline())==expected,'exact every-row index')
                    need(inputs.read(2*len(row.inputs))==u16(row.inputs),'exact input bytes')
                    need(labels.read(2*len(row.labels))==u16(row.labels,labels=True),'exact label bytes')
                    offset+=len(row.inputs);counts['rows']+=1;counts['targets']+=target_count;exposure.update(pos)
                expected=dict(source_provenance={k:v for k,v in r.items() if k!='messages_json'},messages=messages,mapped_metadata=built['metadata'],component=groups[i],split='train',offset=begin,length=offset-begin,rows=len(built['rows']),target_count=built['counters']['supervised_targets'])
                need(json.loads(provenance.readline())==expected,'complete raw/mapped provenance')
                dispositions[i]['decision']='retained';counts['histories']+=1
            need(inputs.read(1)==labels.read(1)==b'' and rows.readline()==provenance.readline()=='','no extra bytes/rows/histories')
        counts.update(candidate_histories=1130,old_train_histories=770,initial_quarantined_histories=len(bad),component_quarantined_histories=sum(groups[i] in bad_groups for i in source),duplicate_histories=len(duplicate),validation_histories=0)
        need(read(D/'history-decisions.json')==list(dispositions.values()),'all1130 exact dispositions')
        need(counts==manifest['counts'] and offset==manifest['stream_tokens'] and dict(exposure)==manifest['position_exposure'],'all aggregates')
        need(counts['histories']+counts['refused_histories']+counts['duplicate_histories']+counts['component_quarantined_histories']==1130,'complete disposition partition')
        need({p.name for p in D.iterdir()}==OUTPUTS|{'manifest.json'},'no extra output before proof')
        for path,expected in pinned.items():check();need(sha(path)==expected,'changed verification input')
        report.update(state='PASS_independent_everyday_packing_not_admitted',manifest_sha256=pinned[str(D/'manifest.json')],freeze_sha256=manifest['freeze_sha256'],decision_sha256=DECISION_SHA,database_sha256=sha(S/'review.sqlite'),verified_histories=counts['histories'],verified_rows=counts['rows'],counts=counts,stream_tokens=offset,position_exposure=dict(exposure),input_pins=pinned,scope='Independent all-pairs whole-history graph plus connected traversal, quarantine closure and exact dedup. Reuses approved frozen build_chat_rows only for exact framing; all indices, target counts, positions, binary bytes, original provenance and no-DEV disposition independently compared. No private access or semantic/quality certification.')
    except BaseException as error:
        report['state']='FAIL_independent_everyday_packing_not_admitted';report['failures']=[dict(type=type(error).__name__,reason=str(error))]
    report['seconds']=time.monotonic()-start
    if report['failures']:signal.alarm(0)
    else:check()
    with pending.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    if not report['failures']:check()
    os.rename(pending,target);signal.alarm(0)
    print(json.dumps(dict(state=report['state'],failures=report['failures'],seconds=report['seconds'])),flush=True)
    if report['failures']:raise RuntimeError(report['failures'])
if __name__=='__main__':run()
