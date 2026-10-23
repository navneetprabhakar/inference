"""Freeze development diagnostics before viewing baseline or updated outputs."""
import json,hashlib,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parents[1]
sys.path.insert(0,str(BASE/'restart/mac15m-feasibility-v1/upstream'))
from tokenizer import Tokenizer
import numpy as np
from engine_support import Stream

def save(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    clock=json.loads((ROOT/'clock.json').read_text())
    if time.time()>clock['preflight_deadline_epoch']:raise TimeoutError('Preflight deadline')
    if (ROOT/'packet.json').exists():raise RuntimeError('Do not replace frozen evaluation packet')
    tok=Tokenizer(str(BASE/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
    templates=[
      '{n} found a small puppy beside the school gate. Its collar had a phone number. {n} wanted to help it find its home.',
      '{n} left a yellow scarf inside a blue box before going outside. Later, the wind became cold, so {n} went back to look for the scarf.',
      '{n} planted a seed in a clay pot and watered it every morning. One day a tiny green leaf appeared above the soil.',
      '{n} accidentally knocked a friend\'s cup off the table. The cup broke, and the friend looked sad. {n} wanted to make things right.',
      '{n} was walking home when heavy rain began. A neighbor stood at the door holding a large umbrella and waved.',
      '{n} wanted to share an apple with a younger child. There was only one apple, but a parent had a clean knife.',
      '{n} could not find a red lunchbox after school. A friend remembered seeing it on the bench beside the classroom door.',
      '{n} was afraid to cross a narrow wooden bridge. An older sister offered a hand and waited patiently.',
      '{n} heard a kitten crying near a tall tree. The kitten was sitting on a low branch, too frightened to climb down.',
      '{n} promised to return a borrowed book on Friday. On Friday morning, the book was still on the bedside table.',
      '{n} built a tower with wooden blocks. A small child bumped the table, and the tower fell. The child began to cry.',
      '{n} saw an empty birdbath in the garden on a hot day. A thirsty little bird was waiting beside it.',
      '{n} wanted to draw a picture for a grandparent. The paper was ready, but all the crayons were in another room.',
      '{n} was making a sandwich when the bread fell on the dirty floor. There were two clean slices left in the bag.',
      '{n} saw a friend sitting alone during playtime. The other children were playing a simple ball game nearby.',
      '{n} put a toy boat in a shallow pond. A gentle wind pushed the boat away from the edge, and {n} watched carefully.',
      '{n} helped carry groceries into the kitchen. A paper bag tore, and three oranges rolled across the floor.',
      '{n} forgot to close the garden gate. The family dog walked into the yard next door. {n} noticed the open gate.',
      '{n} heard thunder while reading beside the window. A younger brother covered his ears and moved closer.',
      '{n} wanted to bake biscuits with a parent. They washed their hands, put a bowl on the table, and opened the flour bag.']
    names=['Mia','Ben','Sara','Tom','Lily'];stories=[]
    for t,template in enumerate(templates):
      for v,n in enumerate(names):
        text=template.format(n=n);ids=tok.encode(text,bos=True,eos=False);assert len(ids)<=64
        stories.append(dict(id=f'story-{t:02d}-{v}',family=f'story-template-{t:02d}',prefix=text,seed=20261023+t*5+v,max_new_tokens=96))
    grammar=[]
    nounpairs=[('dog','dogs'),('cat','cats'),('bird','birds'),('boy','boys'),('girl','girls')]
    for i in range(100):
      group=i//25;j=i%25;n=names[j%5]
      if group==0:
        singular,plural=nounpairs[j%5];multiple=(j//5)%2==0
        prefix=f"Near the old tree, the {plural if multiple else singular}"
        good=' are waiting.' if multiple else ' is waiting.';bad=' is waiting.' if multiple else ' are waiting.'
      elif group==1:
        obj=['apple','egg','orange','umbrella','old book'][j%5]
        prefix=f"{n} looked in the bag and found";good=f' an {obj}.';bad=f' a {obj}.'
      elif group==2:
        prefix=f"{n} walked to the door. A friend waved at";good=' him.' if n in ['Ben','Tom'] else ' her.';bad=' he.' if n in ['Ben','Tom'] else ' she.'
      else:
        prefix=f"Yesterday, {n}";verbs=[v for v in ['walk','play','look','help','work','talk','cook','clean'] if len(tok.encode(f' {v}ed in the garden.',bos=False,eos=False))==len(tok.encode(f' {v} in the garden.',bos=False,eos=False))];verb=verbs[j%len(verbs)]
        good=f' {verb}ed in the garden.';bad=f' {verb} in the garden.'
      options=[good,bad] if i%2==0 else [bad,good]
      lengths=[len(tok.encode(c,bos=False,eos=False)) for c in options];assert len(set(lengths))==1,(prefix,options,lengths)
      grammar.append(dict(id=f'grammar-{i:03d}',family=['agreement','determiner','pronoun-case','past-tense'][group],prefix=prefix,options=options,answer=i%2))
    ground=[]
    for i in range(100):
      j=i%4;n=names[i%5];group=i//20
      if group==0:
        vals=['red','blue','green','white'];prefix=f"{n} put a {vals[j]} cup on a small table. The color of the cup was";options=[f' {v}.' for v in vals]
      elif group==1:
        vals=['box','bag','bed','car'];prefix=f"{n} left a scarf in the {vals[j]}. The scarf was in the";options=[f' {v}.' for v in vals]
      elif group==2:
        vals=['dog','cat','bird','fish'];prefix=f"{n} has a pet {vals[j]}. The pet that belongs to {n} is a";options=[f' {v}.' for v in vals]
      elif group==3:
        vals=['red','blue','green','white'];other=vals[(j+1)%4];prefix=f"At first, {n} chose a {other} hat. Then {n} changed to a {vals[j]} hat. The hat chosen last was";options=[f' {v}.' for v in vals]
      else:
        vals=['box','bag','bed','car'];other=vals[(j+1)%4];prefix=f"The coin was not in the {other}. {n} found it in the {vals[j]}. The coin was in the";options=[f' {v}.' for v in vals]
      lengths=[len(tok.encode(c,bos=False,eos=False)) for c in options];assert len(set(lengths))==1,(options,lengths)
      ground.append(dict(id=f'ground-{i:03d}',family=['provided-color','location','ownership','correction','negation'][group],prefix=prefix,options=options,answer=j))
    # Some lexical templates repeat. They are explicitly development families,
    # not 300 independent task families or an unseen acceptance benchmark.
    packet=dict(status='FROZEN_DEVELOPMENT_NOT_ACCEPTANCE',stories=stories,grammar=grammar,grounded=ground,
      decoding={'temperature':.7,'top_p':.9,'max_new_tokens':96},coherence={'dimensions':['grammar','topic','entities','causality','local_coherence'],'minimum_total':8,'zero_dimension_fails':True,'contradiction_fails':True},
      caveats=['Twenty narrative template families with five names each; grammar/grounding lexical templates recur. Report cluster counts and do not claim independent 100-family generalization.','The native TinyStories split is not newly deduplicated; exact-overlap screening is diagnostic and cannot establish full family/near-duplicate separation.','No previous conversation holdout is included.'])
    save('packet.json',packet)
    stream=Stream(split='val');a=stream.batch(512);np.save(ROOT/'validation.npy',a)
    save('packet-freeze.json',dict(utc=time.time(),before_any_student_updates=True,packet_sha256=hashlib.sha256((ROOT/'packet.json').read_bytes()).hexdigest(),validation_sha256=hashlib.sha256((ROOT/'validation.npy').read_bytes()).hexdigest(),story_cases=100,story_families=20,grammar_cases=100,grounded_cases=100,validation_targets=131072))
    print('Frozen development packet',flush=True)
if __name__=='__main__':main()
