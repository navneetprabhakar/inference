"""Freeze grounded and boundary curriculum; keep old and new source labels intact."""
import hashlib,json,random,re
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT,encode_episode
from audit_teacher_fixture_trajectories import audit

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=ROOT/'data/eight-hour-improvement-v7';out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():raise RuntimeError('Already frozen')
    oldpath=ROOT/'data/eight-hour-improvement-v6/records.jsonl';newpath=ROOT/'data/eight-hour-grounded-v1/batch-001.jsonl'
    for path in [oldpath,newpath]:
        if audit([path])['errors']:raise RuntimeError('Fixture/context gate failed')
    old=[json.loads(l) for l in oldpath.read_text().splitlines()];new=[json.loads(l) for l in newpath.read_text().splitlines()]
    boundary={'no_tool_arithmetic','missing_tool_argument','unavailable_calendar','division_error'}
    groups={'grounded_qa':[r for r in new if r['family'] not in boundary],'tool_boundaries':[r for r in new if r['family'] in boundary],'natural_dialogue':[r for r in old if r['training_group']!='fixture_grounding'],'positive_tools':[r for r in old if r['training_group']=='fixture_grounding']}
    assert [len(v) for v in groups.values()]==[1600,500,910,400]
    protected=set();norm=lambda x:' '.join(re.findall(r'\w+',x.casefold()))
    for split in ['development','confirmation']:
        for l in (ROOT/'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2'/f'{split}.jsonl').read_text().splitlines():protected.add(norm(json.loads(l)['turns'][0]['user']))
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));rows=[];indices={};ids=[];masks=[];lengths=[];counts=[];seen=set()
    for name,records in groups.items():
        indices[name]=[]
        for r in records:
            first=norm(next(m['content'] for m in r['messages'] if m['role']=='user'))
            if first in protected:raise RuntimeError('Protected opening overlap:'+r['id'])
            if r['id'] in seen:raise RuntimeError('Duplicate ID')
            seen.add(r['id']);encoded=encode_episode(tok,r['messages'])
            if encoded is None:raise RuntimeError('Unencodable row')
            x,m,n=encoded;indices[name].append(len(rows));rows.append({**r,'training_group':name});ids.append(x);masks.append(m);lengths.append(n);counts.append(int(m.sum()))
    shares={'grounded_qa':.45,'tool_boundaries':.20,'natural_dialogue':.30,'positive_tools':.05};rng=random.Random(2026110308);bags={};targets={k:0 for k in groups};draws={k:0 for k in groups};order=[];inputs=0
    while inputs<2000000:
        k=min(groups,key=lambda x:targets[x]/shares[x])
        if not bags.get(k):bags[k]=indices[k].copy();rng.shuffle(bags[k])
        i=bags[k].pop();order.append(i);inputs+=lengths[i]-1;targets[k]+=counts[i];draws[k]+=1
    (out/'records.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'),ensure_ascii=False)+'\n' for r in rows));np.savez_compressed(out/'episodes.npz',ids=np.stack(ids),mask=np.stack(masks),length=np.array(lengths,np.int32));(out/'order.json').write_text(json.dumps({'order':order,'seed':2026110308}))
    manifest={'records':len(rows),'group_records':{k:len(v) for k,v in groups.items()},'desired_supervised_mix':shares,'scheduled_input_tokens':inputs,'scheduled_supervised_tokens':targets,'scheduled_draws':draws,'sources':{str(p.relative_to(ROOT)):sha(p) for p in [oldpath,newpath]},'files':{n:sha(out/n) for n in ['records.jsonl','episodes.npz','order.json']},'exact_protected_opening_overlap':0,'limitations':['Only40newnatural dialogues are currently available; their remaining authoring continues.','2100grounded/boundary rows and400positive-tool rows are explicitly programmatic, not independent natural conversations.','No claim of quality improvement until actual development review.']};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    run=ROOT/'runs/eight-hour-improvement-v7';run.mkdir(parents=True,exist_ok=True);latest=json.loads((ROOT/'runs/eight-hour-improvement-v3/training/latest.json').read_text())['directory']
    cfg={'run_dir':str(run.relative_to(ROOT)),'base_checkpoint':'runs/eight-hour-improvement-v3/training/'+latest,'data_dir':str(out.relative_to(ROOT)),'deadline_unix':1793672065,'max_nonpadding_input_tokens':500000,'max_active_seconds':3600,'learning_rate':1e-5,'batch_size':2,'checkpoint_every_steps':500,'min_free_disk_bytes':15*2**30,'max_mlx_allocator_bytes':12*2**30,'checkpoint_retention':'latest two plus selected best; per-file audited deletions','seed':2026110308,'initial_stage_cap':500000,'potential_continuation_cap':2000000}
    (run/'training-config.json').write_text(json.dumps(cfg,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
