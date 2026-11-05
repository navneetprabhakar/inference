"""Freeze audited available data for an interim run while CLI authoring continues."""
import hashlib,json,random
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT,encode_episode
from audit_teacher_fixture_trajectories import audit

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=ROOT/'data/eight-hour-improvement-v6';out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():raise RuntimeError('Already frozen; do not overwrite')
    freshpaths=[ROOT/'data/eight-hour-improvement-v5-authored'/f'batch-{i:03d}.jsonl' for i in [1,2]]
    toolpath=ROOT/'data/eight-hour-tool-grounding-v1/batch-001.jsonl';priorpath=ROOT/'data/eight-hour-improvement-v3-reviewed/records.jsonl'
    for paths in [freshpaths,[toolpath]]:
        result=audit(paths)
        if result['errors']:raise RuntimeError(result['errors'])
    fresh=[json.loads(l) for p in freshpaths for l in p.read_text().splitlines() if l]
    prior=[json.loads(l) for l in priorpath.read_text().splitlines() if l and json.loads(l)['family']=='reviewed_multiturn_dialogue']
    fixtures=[json.loads(l) for l in toolpath.read_text().splitlines() if l]
    assert [len(fresh),len(prior),len(fixtures)]==[40,870,400]
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));groups={'fresh_authored':fresh,'prior_reviewed':prior,'fixture_grounding':fixtures};rows=[];group_indices={};ids=[];masks=[];lengths=[];target_counts=[]
    for name,records in groups.items():
        group_indices[name]=[]
        for record in records:
            encoded=encode_episode(tok,record['messages'])
            if encoded is None:raise RuntimeError('Unencodable record '+record['id'])
            token,mask,n=encoded;group_indices[name].append(len(rows));rows.append({**record,'training_group':name});ids.append(token);masks.append(mask);lengths.append(n);target_counts.append(int(mask.sum()))
    rng=random.Random(2026110306);shares={'fresh_authored':.1,'prior_reviewed':.5,'fixture_grounding':.4};bags={};emitted={k:0 for k in groups};counts={k:0 for k in groups};order=[];inputs=0
    while inputs<1000000:
        name=min(groups,key=lambda k:emitted[k]/shares[k])
        if not bags.get(name):bags[name]=group_indices[name].copy();rng.shuffle(bags[name])
        i=bags[name].pop();order.append(i);inputs+=lengths[i]-1;emitted[name]+=target_counts[i];counts[name]+=1
    (out/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
    np.savez_compressed(out/'episodes.npz',ids=np.stack(ids),mask=np.stack(masks),length=np.array(lengths,np.int32))
    (out/'order.json').write_text(json.dumps({'order':order,'seed':2026110306}))
    manifest={'records':len(rows),'group_records':{k:len(v) for k,v in groups.items()},'schedule_input_tokens':inputs,'scheduled_supervised_tokens':emitted,'scheduled_rows':counts,'desired_supervised_token_mix':shares,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in freshpaths+[toolpath,priorpath]},'files':{n:sha(out/n) for n in ['records.jsonl','episodes.npz','order.json']},'limitation':'Interim available-data experiment; does not replace completing all200 fresh authored dialogues. Planned schedule1Minput, initial run stagecap500k.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    run=ROOT/'runs/eight-hour-improvement-v6';run.mkdir(parents=True,exist_ok=True)
    latest=json.loads((ROOT/'runs/eight-hour-improvement-v3/training/latest.json').read_text())['directory']
    config={'run_dir':str(run.relative_to(ROOT)),'base_checkpoint':'runs/eight-hour-improvement-v3/training/'+latest,'data_dir':str(out.relative_to(ROOT)),'deadline_unix':1793672065,'max_nonpadding_input_tokens':500000,'max_active_seconds':1800,'learning_rate':1e-5,'batch_size':2,'checkpoint_every_steps':500,'min_free_disk_bytes':15*2**30,'max_mlx_allocator_bytes':12*2**30,'checkpoint_retention':'latest two resumable and selected best','seed':2026110306,'initial_stage_cap':500000,'potential_continuation_cap':1000000}
    (run/'training-config.json').write_text(json.dumps(config,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
