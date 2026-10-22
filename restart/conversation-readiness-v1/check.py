"""Read-only, bounded response check of our latest from-scratch checkpoint."""
import hashlib,json,sys,time
from pathlib import Path
import torch
BASE=Path(__file__).resolve().parents[2]
UP=BASE/'restart/mac15m-feasibility-v1/upstream'
sys.path.insert(0,str(UP))
from model import ModelArgs,Transformer
from tokenizer import Tokenizer
OUT=Path(__file__).resolve().parent
CHECK=BASE/'restart/mac-native-benchmark-v1/confirmation/checkpoint.pt'
EXPECTED='194f0d3d0574ce86cddeff9a88e38993bf00837b583c1dea2f6c0f506d8255b2'
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    if (OUT/'responses.json').exists():raise RuntimeError('Preserve original response check; use a new directory for another attempt')
    assert sha(CHECK)==EXPECTED
    torch.set_num_threads(4);torch.manual_seed(20261022)
    state=torch.load(CHECK,map_location='cpu',weights_only=False)
    model=Transformer(ModelArgs(**state['model_args'])).to('mps');model.load_state_dict(state['model'],strict=True);model.eval()
    tokenizer=Tokenizer(str(UP/'tokenizer.model'))
    stories=[
      'Once upon a time, a little girl named Lily found a lost puppy. She',
      'Tom wanted to share his red ball with his friend. He walked over and said, "',
      'It began to rain while the children were outside. They decided to',
      'Sara planted a seed in a small pot. Every morning, she',
      'Ben broke his sister\'s toy by accident. He felt sorry, so he',
      'The rabbit was hungry, but the carrot was across the river. A kind duck',
      'Mia could not find her blue hat. She looked under the bed and',
      'At the end of the day, Dad read a story to the children. They']
    questions=[
      ('greeting','Hello! How are you?'),
      ('name','My name is Nila. What is my name?'),
      ('grounding','The cup is blue. What color is the cup?'),
      ('arithmetic','I have two apples and get one more. How many apples do I have?'),
      ('negation','I do not like milk. Do I like milk?'),
      ('correction','My dog is named Max. Sorry, I meant Pip. What is my dog named?'),
      ('clarification','Can you help me choose one?'),
      ('copy','Repeat exactly: Good morning.'),
      ('steps','How do I wash my hands? Give two simple steps.'),
      ('story_request','Tell me a short story about a friendly cat.'),
      ('honesty','Did you send an email to my friend?'),
      ('turn_context','User: My favorite color is green.\nAssistant: I will remember that.\nUser: What is my favorite color?')]
    cases=[dict(id=f'story-{i}',kind='story',prompt=p,temperature=.7,max_new_tokens=64) for i,p in enumerate(stories)]
    for name,q in questions:
        for fmt in ['roles','qa']:
            prompt=(q+'\nAssistant:') if name=='turn_context' else (f'User: {q}\nAssistant:' if fmt=='roles' else f'Question: {q}\nAnswer:')
            cases.append(dict(id=f'{name}-{fmt}',kind='conversation',prompt=prompt,temperature=0.,max_new_tokens=48))
    save('contract.json',dict(checkpoint=str(CHECK.relative_to(BASE)),sha256=EXPECTED,optimizer_step=state['optimizer_step'],completed_targets=state['completed_targets'],learned_parameters=sum(p.numel() for p in model.parameters()),training=False,full_training_authorized=False,case_count=len(cases),context=256,deadline_seconds=600,teacher_model='gpt-6-luna',seed=20261022,note='Diagnostic prompts, not an independent final acceptance holdout; base has no conversation SFT. QA vs roles is a template sensitivity check.'))
    start=time.monotonic();results=[]
    with torch.inference_mode():
        for case in cases:
            ids=tokenizer.encode(case['prompt'],bos=True,eos=False);generated=[]
            for _ in range(case['max_new_tokens']):
                if time.monotonic()-start>600:raise TimeoutError('Read-only response-check deadline')
                x=torch.tensor([ids[-256:]],device='mps',dtype=torch.long)
                logits=model(x)[0,-1,:].float()
                if not torch.isfinite(logits).all().item():raise RuntimeError('Nonfinite logits')
                if case['temperature']==0.:next_id=int(torch.argmax(logits).item())
                else:
                    logits=logits/case['temperature'];threshold=torch.topk(logits,40).values[-1]
                    logits[logits<threshold]=-float('inf');next_id=int(torch.multinomial(torch.softmax(logits,dim=-1),1).item())
                ids.append(next_id)
                if next_id==tokenizer.eos_id:break
                generated.append(next_id)
            result={**case,'response':tokenizer.decode(generated),'generated_tokens':len(generated),'eos':next_id==tokenizer.eos_id}
            results.append(result);save('responses.json',results)
            print(json.dumps(result,ensure_ascii=False),flush=True)
    assert sha(CHECK)==EXPECTED
    save('verification.json',dict(status='PASS',checkpoint_unchanged=True,weights_updated=False,seconds=time.monotonic()-start,responses=len(results),generated_tokens=sum(r['generated_tokens'] for r in results)))
if __name__=='__main__':main()
