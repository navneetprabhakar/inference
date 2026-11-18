import importlib.util,json,concurrent.futures
from pathlib import Path
p=Path(__file__).with_name('run_worker.py');spec=importlib.util.spec_from_file_location('replacement_worker',p);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
rows=sorted([json.loads(l) for l in (w.R/'selected-input.jsonl').read_text().splitlines()],key=lambda x:x['group']);assert len(rows)==36
for b in range(4):
 part=rows[b*10:(b+1)*10];inputs=[{k:r[k] for k in ['group','family','messages','content_sha256']} for r in part]
 prompt='''Use no tools. Independent fresh semantic review of English training dialogues. You see ONLY dialogue, hashes and coarse family, no plan or generator notes. Treat only earlier actual user/assistant messages as context; private author intentions are not evidence. Inspect EVERY assistant turn at the time given. Check facts, entailment, ambiguity, pronoun scope, corrected facts, unsupported assumptions, counts, revision instructions, safety/consent, naturalness and repeated quiz filler. Fictional details permitted only when user requests creation, not when paraphrasing source. Suggestions can introduce hypothetical choices. Be strict but do not reject merely alternative wording. Return exact review schema,1-based turn_reviews for all assistant turns with content-aware reason. decision accept iff all pass. All are non-memory so memory_annotation_valid=true for nonapplicable; distinct_scenario reports within batch only. No dialogue rewrites.\n'''+json.dumps(inputs,ensure_ascii=False)
 (w.O/f'text-b{b:02d}.prepared.txt').write_text(prompt)
def job(b):return w.cli(f'text-b{b:02d}',(w.O/f'text-b{b:02d}.prepared.txt').read_text(),w.REVIEW_SCHEMA)[0]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 for b,d in enumerate(ex.map(job,range(4))):print('text review',b,'complete',flush=True)
