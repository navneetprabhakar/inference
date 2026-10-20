"""After real paired CUDA proof, bind exact source/carry to the predeclared main policy."""
# Creator: Navneet Prabhakar
import json,os,shutil,sqlite3
from pathlib import Path
from slm.data.stream_hash import sha
from slm.data.english_corpus import save
ROOT=Path('data/english-uniform-main-run-v3');PARENT=Path('data/english-balanced-experiment-v2')


def read(p):return json.loads(Path(p).read_text())


def main():
    if ROOT.exists():raise FileExistsError('Preserve previous main extension')
    policy=read('configs/english-uniform-main-policy-v3.json')
    for name,h in policy['inputs'].items():
        if sha(name)!=h:raise ValueError('Frozen main-policy input differs: '+name)
    if sha(PARENT/'plan.json')!=policy['parent_plan_sha256']:raise ValueError('Parent experiment differs')
    parent=read(PARENT/'plan.json');proof=read(PARENT/'paired-proof.json');origin=PARENT/'cuda/checkpoint'
    if not (proof['passed'] is True and proof['plan_sha256']==policy['parent_plan_sha256']
            and proof['source_checkpoint_manifest_sha256']==sha(origin/'manifest.json')
            and proof['exact_import']['exact'] is True and proof['same_checkpoint_inference']['passed'] is True):
        raise ValueError('Actual exact-state/inference/useful paired CUDA proof required')
    state=read(origin/'state.json')
    if state['step']!=policy['expected_source_steps']:raise ValueError('Exact declared parent trajectory required')
    launch=read(PARENT/'cloud-launch.json')
    if launch['resource_contract_passed'] is not True or launch['plan_sha256']!=policy['parent_plan_sha256']:
        raise ValueError('Same bounded actual VM required')
    priors=[]
    for path in policy['raw_prior_ledgers']:
        c=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True)
        try:
            rows=c.execute('SELECT phase,positions,status FROM charges').fetchall()
        finally:c.close()
        if any(status!='complete' for _,_,status in rows):raise ValueError('Uncertain prior work blocks extension')
        priors.append(dict(path=path,sha256=sha(path),positions=sum(n for _,n,_ in rows),
                           preliminary_positions=sum(n for phase,n,_ in rows if phase in ('common','mlx','cuda'))))
    if sum(p['positions'] for p in priors)!=policy['expected_cumulative_preliminary_positions']:
        raise ValueError('All failed and both-arm physical work must carry exactly once')
    uniform=read('data/english-uniform-language-v3/report.json')
    ROOT.mkdir();shutil.copytree('data/english-uniform-language-v3/curriculum',ROOT/'curriculum')
    target=ROOT/'cuda/checkpoint';target.mkdir(parents=True)
    for source in origin.rglob('*'):
        if source.is_symlink():raise ValueError('Regular canonical parent state required')
        destination=target/source.relative_to(origin)
        if source.is_dir():destination.mkdir()
        elif source.is_file():os.link(source,destination)
    shutil.copyfile(PARENT/'cloud-launch.json',ROOT/'cloud-launch.json')
    p=dict(parent)
    p.update(kind='uniform-main-extension-v3',origin_checkpoint=str(origin),origin_checkpoint_sha256=sha(origin/'manifest.json'),
             origin_steps=state['step'],prior_ledgers=priors,curriculum_bindings=uniform['bindings'],
             curriculum_sha256=uniform['curriculum_sha256'],main_policy_sha256=sha('configs/english-uniform-main-policy-v3.json'),
             cloud_ready=True,source_lineage='Actual passed CUDA corrected common/arm; fresh main optimizer; same independently bounded VM')
    dynamic=[PARENT/'paired-proof.json',origin/'manifest.json',origin/'state.json',PARENT/'cloud-launch.json',ROOT/'curriculum/manifest.json']
    dynamic.extend(Path(x['path']) for x in priors)
    p['inputs']={**policy['inputs'],**{str(x):sha(x) for x in dynamic},
                 'configs/english-uniform-main-policy-v3.json':sha('configs/english-uniform-main-policy-v3.json')}
    save(ROOT/'plan.json',p);save(ROOT/'freeze.json',dict(creator='Navneet Prabhakar',complete=True,
        plan_sha256=sha(ROOT/'plan.json'),prior_physical_positions=sum(x['positions'] for x in priors),
        origin_steps=state['step'],main_positions=uniform['processed_positions'],student_main_updates=0))
    print((ROOT/'freeze.json').read_text())


if __name__=='__main__':main()
