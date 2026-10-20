"""Actual raw-history local conversation capture under a separately frozen protocol."""
# Creator: Navneet Prabhakar
import json,os,time
from pathlib import Path
from slm.inference.greedy import GreedyModel
from slm.data.stream_hash import sha
from slm.data.schema import digest

def capture(model,tokenizer,protocol,output,wall_seconds=3600):
    output=Path(output);protocol=Path(protocol)
    if output.exists():raise FileExistsError('Preserve earlier conversation captures')
    p=json.loads(protocol.read_text());cases=p['conversations'];limit=p['max_new_tokens']
    if len(cases)!=100 or any(len(c['turns'])!=3 for c in cases):raise ValueError('Exactly100 independent3turn cases required')
    output.mkdir();m=GreedyModel(model,tokenizer,'mlx','default',expected_tokenizer_hash=sha(Path(tokenizer)/'manifest.json'),embedding_implementation='dense-onehot-v1');started=time.monotonic()
    (output/'session.json').write_text(json.dumps(dict(creator='Navneet Prabhakar',student=m.identity,protocol_sha256=sha(protocol),system_prompt=None,teacher_calls=0,assessment_pending=True,human_attestation=False),indent=2)+'\n')
    with (output/'turns.jsonl').open('x') as f:
        for c in cases:
            history=[]
            for turn,request in enumerate(c['turns'],1):
                if time.monotonic()-started>wall_seconds:raise TimeoutError('Finite raw conversation deadline')
                history.append(dict(role='user',content=request['user']));response=m.generate(history,limit)
                row=dict(conversation=c['id'],category=c['category'],turn=turn,user=request['user'],success_criterion=request['success_criterion'],context_sha256=digest(history),response=response)
                f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno());history.append(dict(role='assistant',content=response['text']))
            if c['id']%10==0:print(json.dumps(dict(phase=output.name,conversations=c['id'],seconds=time.monotonic()-started)),flush=True)
    result=dict(creator='Navneet Prabhakar',complete=True,conversations=100,actual_turns=300,actual_history=True,turns_sha256=sha(output/'turns.jsonl'),assessment_pending=True,seconds=time.monotonic()-started)
    (output/'completion.json').write_text(json.dumps(result,indent=2)+'\n');return result
