"""Separate answer-content versus stop-token reference loss; not free-generation correctness."""
# Creator: Navneet Prabhakar
import json,time
from datetime import datetime
from pathlib import Path
import numpy as np
from slm.common.tokenizer import BPE,OFFSET
from slm.inference.greedy import GreedyModel
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-conversation-run-v1')
def main():
 out=ROOT/'loss-component-diagnostic-v1.json'
 if out.exists():raise FileExistsError(out)
 p=json.loads(Path('configs/grounded-conversation-run-v1.json').read_text());done=json.loads((ROOT/'completion.json').read_text())
 if not done['complete']:raise ValueError('Actual terminal capture must precede this diagnostic')
 deadline=datetime.fromisoformat(json.loads((ROOT/'process.json').read_text())['deadline_utc']).timestamp();start=time.monotonic();refs=Path(p['heldout_references']);rows=[json.loads(l) for l in refs.open()];bpe=BPE.load(p['tokenizer']);results={}
 for name,path in [('source',Path(p['source_model'])),('trained',ROOT/'terminal/model')]:
  model=GreedyModel(path,p['tokenizer'],'mlx','default',expected_tokenizer_hash=sha(Path(p['tokenizer'])/'manifest.json'),embedding_implementation='dense-onehot-v1');scores=[]
  for r in rows:
   if time.monotonic()-start>900 or time.time()>deadline-300:raise TimeoutError('Original local clock/diagnostic wall cap')
   x,y,mask=bpe.serialize(r['messages'],objective='assistant');parts={};count={}
   for kind,selection in [('answer_content',np.asarray(y)>=OFFSET),('structural',np.asarray(y)<OFFSET)]:
    segment=np.asarray(mask,dtype=np.float32)*selection;count[kind]=int(segment.sum())
    if not count[kind]:raise ValueError('Nonempty mask segment required')
    value=model.impl.loss(model.params,model.config,model.array([x]),model.array([y]),model.array([segment.tolist()]),loss_implementation=p['recipe']['loss_implementation'],embedding_implementation='dense-onehot-v1');parts[kind]=float(value)
    if not np.isfinite(parts[kind]):raise FloatingPointError('Nonfinite component reference loss')
   scores.append(dict(paragraph_id=r['id'],split_group=r['split_group'],targets=count,nll=parts))
  results[name]=dict(model_manifest_sha256=sha(path/'manifest.json'),equal_document_means={k:float(np.mean([r['nll'][k] for r in scores])) for k in ('answer_content','structural')},total_targets={k:sum(r['targets'][k] for r in scores) for k in ('answer_content','structural')},rows=scores);del model
 result=dict(creator='Navneet Prabhakar',complete=True,supervised_gradient_positions=0,teacher_calls=0,model_mutation=False,reference_dialogues_sha256=sha(refs),results=results,seconds=time.monotonic()-start,scope='Reference-conditioned loss on the same100source dialogues with original human answer prefixes. Fallible source labels retained. Same original FP32 loss/embedding runtime, disjoint content and message-end/EOS masks. This is an objective diagnostic, not actual student-history inference, semantic correctness, causal proof or model promotion. All raw free-generated replies scored separately.')
 out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v['equal_document_means'] for k,v in results.items()},indent=2))
if __name__=='__main__':main()
