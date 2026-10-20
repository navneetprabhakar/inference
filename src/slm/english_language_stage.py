"""Finite substantial language continuation and raw-history regression capture."""
# Creator: Navneet Prabhakar
import json,os,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from slm.common import checkpoint
from slm.common.curriculum import CurriculumTrainer
from slm.common.tokenizer import BPE
from slm.data.curriculum import CurriculumBatches
from slm.data.english_corpus import lines
from slm.data.stream_hash import sha
from slm.data.schema import digest
from slm.english_learning import Meter,nll,compare_learning,save
from slm.inference.greedy import GreedyModel

def conversations(model,tokenizer,output,backend='torch',device='cuda'):
 output=Path(output)
 if output.exists():raise FileExistsError(output)
 output.mkdir();plan=json.loads(Path('configs/current-model-100-conversations-v1.json').read_text());cases=plan['conversations']
 if len(cases)!=100 or any(len(c['turns'])!=3 for c in cases):raise ValueError('Frozen100three-turn regression suite required')
 m=GreedyModel(model,tokenizer,backend,device,expected_tokenizer_hash=sha(Path(tokenizer)/'manifest.json'),embedding_implementation='dense-onehot-v1')
 save(output/'session.json',dict(creator='Navneet Prabhakar',student=m.identity,protocol_sha256=sha('configs/current-model-100-conversations-v1.json'),teacher_calls=0,human_attestation=False,assessment_pending=True))
 with (output/'turns.jsonl').open('x') as f:
  for case in cases:
   history=[]
   for turn,request in enumerate(case['turns'],1):
    history.append(dict(role='user',content=request['user']));response=m.generate(history,plan['max_new_tokens'])
    row=dict(conversation=case['id'],category=case['category'],turn=turn,user=request['user'],success_criterion=request['success_criterion'],context_sha256=digest(history),response=response)
    f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno());history.append(dict(role='assistant',content=response['text']))
   print(json.dumps(dict(conversations_completed=case['id'])),flush=True)
 rr=list(lines(output/'turns.jsonl'))
 for part in range(2):
  text=['# Actual English recovery conversation assessment', '', 'Creator: Navneet Prabhakar', '', 'Raw student replies; direct quality assessment pending. Same visible regression protocol as prior0/100baseline, not a fresh final test.','']
  for c in cases[part*50:(part+1)*50]:
   text+=['## Conversation '+str(c['id'])+' — '+c['category'],'']
   for r in [r for r in rr if r['conversation']==c['id']]:
    text+=['User: '+r['user'],'','```text',r['response']['text'],'```','']
  (output/f'transcripts-part-{part+1}.md').write_text('\n'.join(text))
 save(output/'completion.json',dict(creator='Navneet Prabhakar',complete=True,conversations=100,turns=len(rr),turns_sha256=sha(output/'turns.jsonl'),actual_history=True,assessment_pending=True))

def run(plan,root,corpus,tokenizer,plan_hash):
 output=root/'language'
 if output.exists():raise FileExistsError('Retain previous language attempt')
 launch=json.loads((root/'cloud-launch.json').read_text());created=datetime.fromisoformat(launch['creation_started_at_utc']);lifetime_limit=45*3600
 def remaining():return lifetime_limit-(datetime.now(timezone.utc)-created).total_seconds()
 if remaining()<3600:raise TimeoutError('Insufficient bounded VM lifetime for language phase')
 docs=list(lines(corpus/'development.jsonl'));bpe=BPE.load(tokenizer)
 with CurriculumBatches(root/'curriculum',plan['curriculum_bindings'],tokenizer,plan['curriculum_sha256']) as data:
  config,weights=checkpoint.load(root/'cuda/checkpoint/model');t=CurriculumTrainer(config,weights,data,'torch','cuda')
  output.mkdir();initial=nll(t,bpe,docs,output/'initial-nll.json');meter=Meter(root/'physical.sqlite',plan_hash,maximum=100000000,phase_maximum=78000000)
  scheduled=list(plan['language']['checkpoints']);next_index=0;bad=0;start=time.monotonic();stop='data_exhausted';latest=None
  try:
   with (output/'updates.jsonl').open('x') as log:
    while t.cursor<len(data):
     if remaining()<3600:stop='vm_lifetime_cleanup_reserve';break
     _,end=t._update_context();positions=data.counts(end)[0]-data.counts(t.cursor)[0];cursor=t.cursor
     meter.reserve('language',cursor,positions);r=t.update();meter.complete('language',cursor)
     log.write(json.dumps(r)+'\n');log.flush()
     if t.step%16==0:
      os.fsync(log.fileno());save(output/'progress.json',dict(**r,seconds=time.monotonic()-start,physical_positions_reserved=meter.total(),vm_seconds_remaining=remaining()))
      print(json.dumps(dict(phase='language',**r,elapsed=time.monotonic()-start)),flush=True)
     if next_index<len(scheduled) and t.tokens>=scheduled[next_index]:
      name=f'positions-{t.tokens:09d}';latest=output/name;t.save(latest)
      measured=nll(t,bpe,docs,output/(name+'-nll.json'));quality=compare_learning(initial,measured)
      bad=bad+1 if min(quality['source_improvements_nats'].values())<-.1 else 0
      save(output/(name+'-quality.json'),quality);next_index+=1
      if bad>=2:stop='two_scheduled_slice_regressions';break
    latest=output/'terminal';t.save(latest)
    measured=nll(t,bpe,docs,output/'terminal-nll.json');quality=compare_learning(initial,measured)
    save(output/'completion.json',dict(creator='Navneet Prabhakar',complete=True,plan_sha256=plan_hash,termination=stop,tokens=t.tokens,steps=t.step,selected_source='cuda paired96-update own random-origin branch; explicit fresh language optimizer',quality=quality,language_generation_gate_pending=True,sft_allowed=False,checkpoint_manifest_sha256=sha(latest/'manifest.json'),physical_positions_reserved=meter.total(),seconds=time.monotonic()-start))
  except BaseException as error:
   save(output/'failure.json',dict(complete=False,error_type=type(error).__name__,message=str(error)[:1000],physical_positions_reserved=meter.total(),no_automatic_replay=True));raise
  finally:meter.close()
 # Final same-checkpoint CUDA signature is checked again on return to MLX.
 from importlib.util import spec_from_file_location,module_from_spec
 spec=spec_from_file_location('english_runner','scripts/run-english-learning.py');module=module_from_spec(spec);spec.loader.exec_module(module)
 module.snapshot(t,bpe,docs,output/'terminal-inference.npz')
 # Free optimizer and gradient state before generation; checkpoint remains canonical FP32.
 del t,weights
 m=GreedyModel(latest/'model',tokenizer,'torch','cuda',expected_tokenizer_hash=sha(Path(tokenizer)/'manifest.json'),embedding_implementation='dense-onehot-v1')
 with (output/'terminal-prose.jsonl').open('x') as f:
  for case in json.loads((corpus/'generation-prefixes.json').read_text()):
   response=m._generate_ids(case['prefix_tokens'],64);f.write(json.dumps(dict(example_id=case['example_id'],source=case['source'],prefix=m.tokenizer.decode(case['prefix_tokens']),response=response),ensure_ascii=False)+'\n');f.flush()
 del m
 conversations(latest/'model',tokenizer,output/'conversation-100')
 save(output/'assessment-ready.json',dict(creator='Navneet Prabhakar',complete=True,actual_conversations=100,actual_turns=300,direct_quality_review_pending=True,model_promoted=False,teacher_calls=0))
