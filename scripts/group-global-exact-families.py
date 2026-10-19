"""Consolidate raw source and witness texts; exact grouping only, before splits."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from slm.data.cosmopedia_seed import extract
from slm.data.exact_families import ExactFamilies
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/global-exact-families-v1');PLAN=Path('configs/global-exact-families-v1.json')

def read(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(line) for line in Path(p).read_bytes().splitlines()]
def cached(root,key):return Path(root)/'cache'/(digest(key)+'.bin')
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')

def worker():
    plan=read(PLAN)
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Global exact input changed')
    store=ExactFamilies(ROOT/'families.sqlite',max_records=plan['max_records'],max_bytes=plan['max_db_bytes'])
    ingredients=Counter();ancestral=0;known=Counter()
    try:
        def add(identity,texts,families,ingredient,candidate=False,fixed=None,blocked=False,reference=None,tokens=None,metadata=None):
            store.add(dict(id=identity,texts=texts,families=sorted(set(families)),ingredient=ingredient,
                candidate=candidate,fixed_partition=fixed,blocked=blocked,reference=reference,tokens=tokens,metadata=metadata or {},training_approved=False))
            ingredients[ingredient]+=1
            if len(store.parent)%5000==0:
                if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Free disk reserve reached')
                print(json.dumps(dict(records=len(store.parent),ingredient=ingredient)),flush=True)
        parent=Path(plan['ancestral_dataset']);manifest=read(parent/'manifest.json');frozen=read(parent/'heldout-groups.json');seenfamilies=set()
        for name,h in manifest['files'].items():
            if not name.startswith(('validation-','test-')) or not name.endswith('.jsonl'):continue
            path=parent/name
            if sha(path)!=h:raise ValueError('Ancestral shard changed')
            for r in lines(path):
                if frozen[r['parent_group_id']]!=r['split']:raise ValueError('Ancestral partition mismatch')
                add('ancestral:'+r['example_id'],{str(i):m['content'] for i,m in enumerate(r['messages'])},[r['parent_group_id']],
                    'ancestral',fixed=r['split'],reference=dict(path=str(path),example_id=r['example_id'],original=r))
                ancestral+=1;seenfamilies.add(r['parent_group_id'])
        if seenfamilies!=set(frozen):raise ValueError('Missing full ancestral family texts')
        fineplan=read('configs/fineweb-candidate-intake-execution-v2.json');judgments=fineplan['known_judgments']
        old={}
        for path in plan['old_fineweb_rows']:
            for r in lines(path):old[r['source_group']]=r
        for family,r in sorted(old.items()):
            bad=judgments.get(family) in ('exclude','defer');known['fineweb_nonapproval']+=bad
            add('fineweb-old:'+family,dict(content=r['row']['text']),[family],'fineweb-old',blocked=bad,
                reference=dict(paths=plan['old_fineweb_rows'],source_group=family,raw_record_sha256=r['raw_record_sha256']))
        if known['fineweb_nonapproval']!=29:raise ValueError('All29known FineWeb nonapprovals required')
        root='data/fineweb-candidate-intake-v1';report=read(Path(root)/'report.json')
        for item in report['groups']:
            path=cached(root,'rows/'+item['file']+'/'+str(item['group']['index']))
            if sha(path)!=item['rows_sha256']:raise ValueError('FineWeb acquired payload changed')
            for r in lines(path):
                add('fineweb:'+r['file']+':'+str(r['row_group'])+':'+str(r['row_in_group']),dict(content=r['row']['text']),[r['source_group']],
                    'general',candidate=r['provisional_quality_pass'],fixed=frozen.get(r['source_group']),blocked=judgments.get(r['source_group']) in ('exclude','defer'),
                    reference=dict(path=str(path),raw_record_sha256=r['raw_record_sha256']),tokens=r['actual_student_bpe_text_tokens'],metadata=dict(url=r['row']['url'],crawl=r['row']['dump']))
        cosmoplan=read('configs/cosmopedia-candidate-intake-execution-v2.json');badfamilies=set(cosmoplan['nonapproval_prompt_families'])|set(cosmoplan['nonapproval_seed_families'])
        for family in sorted(badfamilies):add('blocked-family:'+family,{},[family],'blocked-family',blocked=True,reference=dict(path='configs/cosmopedia-candidate-intake-execution-v2.json'))
        def cosmo(r,identity,path,candidate=False):
            raw=r['row'];families=['HuggingFaceTB/smollm-corpus:cosmopedia-v2:prompt:'+digest(raw['prompt'])];texts=dict(content=raw['text'],prompt=raw['prompt'])
            if raw['seed_data']=='fineweb':
                seed=extract(raw);families.append(seed['proposed_exact_seed_family']);texts['seed']=seed['seed_excerpt']
            bad=bool(set(families)&badfamilies);known['cosmo_nonapproval_records']+=bad
            genre=raw['format'];ingredient='explanatory' if genre in ('textbook','textbook_unconditionned_topic') else 'cosmopedia-other'
            add(identity,texts,families,ingredient,candidate=candidate,blocked=bad,
                reference=dict(path=str(path),raw_record_sha256=r['raw_record_sha256']),tokens=r.get('actual_student_bpe_text_tokens'),metadata=dict(format=genre,audience=raw['audience'],seed_data=raw['seed_data']))
        root='data/cosmopedia-candidate-intake-v1';report=read(Path(root)/'report.json')
        for item in report['files']:
            path=cached(root,item['rows_cache_key'])
            if sha(path)!=item['rows_sha256']:raise ValueError('Cosmopedia acquired payload changed')
            for r in lines(path):cosmo(r,'cosmopedia:'+r['file']+':'+str(r['row_group'])+':'+str(r['row_in_group']),path,r['provisional_quality_pass'])
        for path in plan['old_cosmopedia_rows']:
            for i,r in enumerate(lines(path)):cosmo(r,'cosmopedia-old:'+str(path)+':'+str(i),path)
        root='data/tinystories-range-intake-v1';narrative=read(Path(root)/'report.json');quality=read('data/tinystories-quality-v1/report.json')
        for item in narrative['requests']:
            req=item['request'];kind=req['kind']
            if kind=='evaluation_prompts':continue
            path=cached(root,'records/'+req['key'])
            if sha(path)!=item['records_sha256']:raise ValueError('Narrative acquired payload changed')
            decisions={}
            if kind=='train_range':
                for chunk in quality['chunks']:
                    if chunk['key'].startswith(req['key']+'/'):
                        for r in lines(cached('data/tinystories-quality-v1','decisions/'+chunk['key'])):decisions[(r['file'],r['start'])]=r
            for r in lines(path):
                key=(r['file'],r['row']['start']);q=decisions.get(key);bad=q is not None and q['decision']['prior_direct_judgment'] in ('exclude','defer')
                known['narrative_nonapproval']+=bad
                add('tinystories:'+r['file']+':'+str(r['row']['start']),dict(content=r['row']['text']),['roneneldan/TinyStories:'+r['source_group']],
                    'narrative' if kind=='train_range' else 'official-validation',candidate=q['decision']['candidate'] if q else False,
                    fixed='validation' if kind=='official_validation' else None,blocked=bad,
                    reference=dict(path=str(path),start=r['row']['start'],raw_text_sha256=r['row']['raw_text_sha256']),tokens=q['content_tokens'] if q else None)
        if known['narrative_nonapproval']!=3:raise ValueError('All3narrative nonapprovals required')
        prior=read('data/evaluation-exclusions-v2/inventory.json')
        for i,r in enumerate(prior['entries']):add('protected-prior:'+str(i),dict(content=r['text']),[],'protection',fixed='test',reference=dict(origins=r['origins']))
        upstream=read('data/tinystories-characterization-v1/upstream-protection.json')
        for i,r in enumerate(upstream['prompts']):add('protected-upstream:'+str(i),dict(content=r['text']),[],'protection',fixed='test',reference=dict(origin=r['origin']))
        result=store.finish();result.update(creator='Navneet Prabhakar',kind='actual-global-exact-families-v1',complete=True,
            plan_sha256=sha(PLAN),ingredient_records=dict(ingredients),ancestral_rows=ancestral,ancestral_families=len(seenfamilies),known_witness_counts=dict(known),
            training_approved=False,near_grouping_complete=False,substring_seed_linking_complete=False,split_assignment_performed=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='All acquired source rows and full witness texts consolidated without rewriting. Normalized whole-text and explicit parent/prompt/exact-seed-family components only. Existing witness partitions immutable; component priority prevents future train membership. Near similarity and excerpt containment/source-identity reconciliation remain required before new splits or admission.')
        for p,h in plan['input_bindings'].items():
            if sha(p)!=h:raise ValueError('Global exact input changed during grouping')
        store.close();result['database_sha256']=sha(ROOT/'families.sqlite');save(ROOT/'report.json',result);save('reports/global-exact-families.json',result)
        print(json.dumps(result,indent=2),flush=True)
    except BaseException as error:
        store.close();save(ROOT/'failure.json',dict(complete=False,error_type=type(error).__name__,records=len(store.parent)))
        raise SystemExit('Global exact grouping stopped; preserve incomplete output, no admission') from None

def main():
    if '--worker' in sys.argv:worker();return
    if ROOT.exists():raise FileExistsError('Global exact grouping already attempted')
    ROOT.mkdir();save(ROOT/'plan.json',read(PLAN))
    child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
    try:
        code=child.wait(timeout=1800)
        if code:raise SystemExit(code)
    except BaseException:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise

if __name__=='__main__':main()
