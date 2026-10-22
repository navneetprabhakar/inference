"""Actual pinned tokenizer/classifier imports on synthetic text only; no fitting."""
from pathlib import Path
import json,hashlib,sys,importlib.metadata,time,resource
import tokenizers,engine,rules,classify,custody,boundaries,pilot
p=json.loads((Path(__file__).resolve().parent/'profile.json').read_text())
assert str(Path(sys.executable).resolve())==p['python'] and sys.version_info[:3]==(3,12,11)
assert importlib.metadata.version('tokenizers')=='0.22.2'
assert Path(tokenizers.__file__).resolve()==Path(p['tokenizers_init']).resolve()
for k in ['tokenizer_manifest','tokenizer_core','fasttext','language_model']:assert rules.sha(p[k]['path'])==p[k]['sha256']
t=rules.load_tokenizer(p);text='This synthetic fixture is a complete English sentence about books, people, and learning. '*5
x=t.encode(text,add_special_tokens=False).ids;assert x and x==t.encode(text,add_special_tokens=False).ids
z=engine.diagnostics(text,t,p,10,lambda *a:None);assert z['tokens']==len(x) and z['scored']==2 and z['skipped']==0 and z['passed']==1
# Worst observed envelope character-size synthetic fixture, no retained source.
maximum=1885992;unit='This synthetic English passage preserves exact words and punctuation while testing bounded document processing. '
large=(unit*((maximum+len(unit)-1)//len(unit)))[:maximum];start=time.monotonic();large_result=engine.diagnostics(large,t,p,30,lambda *a:None);elapsed=time.monotonic()-start
assert len(large_result['rows'])==1+(maximum+1023)//1024
benchmark={'synthetic_characters':maximum,'synthetic_windows':len(large_result['rows']),'seconds':elapsed,'self_highwater_RSS_native_units_Darwin_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'not_a_retained_source_throughput_guarantee':True}
print(json.dumps({'status':'PASS_ACTUAL_PROJECT_RUNTIME_SYNTHETIC_ONLY','python':str(sys.executable),'resolved_python':p['python'],'version':sys.version.split()[0],'tokenizers':'0.22.2','tokenizer_import_origin':tokenizers.__file__,'fasttext_existing_fixed_artifacts':True,'max_envelope_synthetic_benchmark':benchmark,'synthetic_content_tokens':len(x),'synthetic_scored_windows':z['scored'],'student_model_or_tokenizer_fit_operations':0,'retained_PG_body_reads':0}))
