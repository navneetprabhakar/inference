import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('worker',Path(__file__).with_name('run_worker.py'));w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
plans=json.loads((w.R/'replacement-plans.json').read_text());w.batch(13,plans)
