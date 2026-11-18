import importlib.util,json
from pathlib import Path
p=Path(__file__).with_name('run_worker.py');spec=importlib.util.spec_from_file_location('replacement_worker',p);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
r=next(r for r in map(json.loads,(w.R/'selected-input.jsonl').read_text().splitlines()) if r['group']=='c_replace_020');c=next(c for c in json.loads((w.ROOT/r['generation']['raw_artifact']).read_text())['conversations'] if c['group']==r['group']);w.review('c020-text-rebind',[c],{c['group']:{}});print('c020 rebound',flush=True)
