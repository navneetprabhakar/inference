import importlib.util,json
from pathlib import Path
p=Path(__file__).with_name('run_worker.py');spec=importlib.util.spec_from_file_location('replacement_worker',p);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
raw=w.O/'four-plan.raw.json';plans=json.loads(raw.read_text())['scenarios'];assert len(plans)==4
for p in plans:p['turns']=4
w.write(w.R/'four-scenario-plan.json',{'plans':plans,'raw_artifact':str(raw.relative_to(w.ROOT)),'raw_sha256':w.sha(raw),'planned_before_generation':True})
w.batch(5,plans)
