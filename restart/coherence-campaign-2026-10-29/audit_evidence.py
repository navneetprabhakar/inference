"""Read-only CPU audit of historical evidence; no student/teacher calls."""
import json,hashlib,random,collections,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(P.parent/'phase-a-2026-10-28'))
from build import serial,sp
import numpy as np

def read(n):return json.loads((ROOT/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 B='restart/foundation-resolution-v1/B/';receipt=read(B+'checkpoint.json');assert sha(ROOT/receipt['path'])==receipt['sha256'];native=read('restart/mac15m-feasibility-v1/data-receipt.json');rows=read(B+'options.json');options={}
 for kind,variant in sorted({(r['kind'],r['variant']) for r in rows}):
  subset=[r for r in rows if (r['kind'],r['variant'])==(kind,variant)];correct=[max(range(len(r['scores'])),key=r['scores'].__getitem__)==r['answer'] for r in subset];assert correct==[r['correct'] for r in subset];options[kind+'|'+variant]=dict(correct=sum(correct),total=len(correct))
 grammar=[r for r in rows if r['kind']=='grammar'];options['grammar_distinct_pairs']=len({(r['prefix'],tuple(sorted(r['options']))) for r in grammar})
 stories=read(B+'stories.json');chosen=sorted(random.Random(291029).sample(range(len(stories)),8));sample=[{k:r[k] for k in ['id','family','prefix','response','eos']} for i,r in enumerate(stories) if i in chosen]
 cases=read('restart/phase-a-completion-2026-10-29/natural-development.json');contexts={}
 for cap in [32,48]:
  worst=[]
  for case in cases:
   history=[];prior=0
   for t,turn in enumerate(case['turns']):
    history.append(dict(role='user',content=turn['user']));n=len(serial(history)[0])-prior+t*cap+cap;worst.append(n);history.append(dict(role='assistant',content=turn['reference']));prior+=len(sp.encode(turn['reference']))+1
  contexts[str(cap)]=dict(maximum=max(worst),overflow_turns=sum(n>256 for n in worst),total_turns=len(worst))
 # Exact block overlap only; cannot establish document/family independence.
 val=np.load(ROOT/'restart/foundation-stage3-v1/validation.npy',mmap_mode='r');replay=np.load(ROOT/'restart/conversation-improvement-v1/private/replay.npy',mmap_mode='r');vkeys={hashlib.sha256(np.asarray(x,np.int32).tobytes()).hexdigest() for x in val};rkeys={hashlib.sha256(np.asarray(x,np.int32).tobytes()).hexdigest() for x in replay.reshape(-1,257)}
 d0=read('restart/foundation-recovery-v2-corrected/D0/result.json');current=read('restart/tiny-copy-execution-2026-10-29/result.json')
 sources=[B+'checkpoint.json',B+'summary.json',B+'stories.json',B+'options.json','restart/mac15m-feasibility-v1/data-receipt.json','restart/foundation-recovery-v2-corrected/D0/result.json','restart/phase-a-completion-2026-10-29/natural-development.json','restart/tiny-copy-execution-2026-10-29/result.json','restart/foundation-stage3-v1/validation.npy','restart/conversation-improvement-v1/private/replay.npy','restart/phase-a-2026-10-28/build.py','restart/mac15m-feasibility-v1/upstream/tokenizer.model']
 out=dict(status='AUDIT_COMPLETE_READINESS_NOT_ESTABLISHED',checkpoint=receipt,architecture=dict(parameters=15191712,embedding_parameters=9216000,embedding_share=9216000/15191712,context=256,vocabulary=32000),native_inventory={k:native[k] for k in ['training','validation','split','corpus_position_caveat']},retained_exposure_inventory_ratio=receipt['completed_targets']/native['training']['distinct_corpus_positions'],options=options,stories=dict(count=len(stories),families=len({r['family'] for r in stories}),eos=sum(r['eos'] for r in stories),at_cap=sum(r['generated_tokens']==r['max_new_tokens'] for r in stories),bos_cases=sum(bool(r['BOS_positions']) for r in stories),sample_indices=chosen),natural_packet=dict(conversations=len(cases),families=dict(collections.Counter(r['family'] for r in cases)),contexts=contexts),block_audit=dict(validation_rows=len(val),unique_validation_rows=len(vkeys),replay_rows=int(np.prod(replay.shape[:-1])),unique_replay_rows=len(rkeys),exact_cross_overlap=len(vkeys&rkeys),limit='No document-level or near-duplicate guarantee'),broad_admission=dict(status=d0['status'],documents=d0['admitted_documents'],tokens=d0['admitted_native_content_tokens'],reasons=d0['reasons']),current_successor_usage=dict(charges=current['charges'],seconds=current['seconds']),source_hashes={n:sha(ROOT/n) for n in sources},new_student_forwards=0,new_optimizer_updates=0,new_teacher_calls=0)
 (P/'evidence.json').write_text(json.dumps(out,indent=2)+'\n');(P/'historical-sample.json').write_text(json.dumps(sample,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['status','options','stories','natural_packet','block_audit','broad_admission']},indent=2))
if __name__=='__main__':main()
