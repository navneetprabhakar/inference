"""Export hash-bound diagnostic inputs from verified admitted local streams."""
import json
from pathlib import Path
import shutil
import numpy as np
from own_base_language_streams import AdmittedStreams,sha
from cloud_training.runtime import atomic_json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/gcp-a100-diagnostic-input-v1'

def main():
    if OUT.exists():raise ValueError('immutable export already exists')
    spec_path=ROOT/'reports/fresh-broad-continuation-v3/activation.json'
    spec=json.loads(spec_path.read_text());run=Path(spec['run'])
    ledger=json.loads((run/'campaign.json').read_text())
    assert ledger['state']=='completed' and ledger['trained_tokens']==74997760
    assert not any(Path(p).exists() for p in spec['stop_paths'])
    entry=json.loads((run/'latest.json').read_text())[0];parent=run/entry['file']
    assert parent.name in json.loads((run/'protected.json').read_text())
    assert sha(parent)==entry['sha256'] and parent.stat().st_size==entry['bytes']
    data=AdmittedStreams(spec)
    cursor=data.schedule.state_at(9155)
    # Three LR branches consume the SAME fresh5M slice independently. Extra
    # rows are for disposable benchmark/parity updates, never promoted.
    exported=[];row_manifest=[]
    for _ in range(640):
        rows,cursor=data.schedule.next_update(cursor)
        for r in rows:
            exported.append(data.row(r).astype('<u2'));row_manifest.append(r)
    OUT.mkdir();np.save(OUT/'train.npy',np.stack(exported),allow_pickle=False)
    validation=[data.validation_row(w).astype('<u2') for w in data.validation['windows']]
    atomic_json(OUT/'validation.json',[x.tolist() for x in validation])
    atomic_json(OUT/'rows.json',row_manifest)
    shutil.copy2(parent,OUT/'parent.pt')
    shutil.copy2(ROOT/'reports/base-foundation-100m/diagnostics.json',OUT/'public-diagnostics.json')
    shutil.copytree(ROOT/'data/tokenizer',OUT/'data/tokenizer')
    manifest={'schema':1,'state':'verified_admitted_training_slice_for_disposable_diagnostics',
      'parent':entry,'activation_sha256':sha(spec_path),'source_start_updates':spec['source_start_updates']+9155,
      'updates':640,'targets_per_update':8192,'row_shape':[640*16,513],
      'purpose':'benchmark and three sequential equal-data LR diagnostics; no long training or assistant promotion',
      'local_originals_retained':True,'source_schedule':data.schedule.identity,
      'files':{str(p.relative_to(OUT)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file()}}
    atomic_json(OUT/'inputs.json',manifest)
    atomic_json(ROOT/'reports/gcp-a100-diagnostic-v1/input-receipt.json',{'manifest_sha256':sha(OUT/'inputs.json'),'parent':entry,'files':manifest['files'],'source_start_updates':manifest['source_start_updates']})
    print(json.dumps({'state':'exported','directory':str(OUT),'files':len(manifest['files'])}))

if __name__=='__main__':main()
