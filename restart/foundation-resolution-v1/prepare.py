"""CPU-only prospective cases, controls, tokenizer checks and source freeze."""
import json,sys,time
from common import ROOT,PROJECT,UPSTREAM,OLD,save,sha,read,check
from scorer import continuation,controls
sys.path.insert(0,str(UPSTREAM));from tokenizer import Tokenizer

def main():
 check('R0');tok=Tokenizer(str(UPSTREAM/'tokenizer.model'))
 templates=[
 ('lost-key','{n} dropped a key beside the garden bench. A bird picked it up and put it in its nest. {n} saw where the bird went.'),
 ('sharing','{n} brought two apples to the park. A friend had forgotten to bring a snack. The friends sat together under a tree.'),
 ('rain','{n} saw dark clouds above the playground. The first drops of rain fell on the slide. Everyone began gathering their things.'),
 ('repair','{n} noticed a loose wheel on a toy cart. An adult brought a small tool to help. They placed the cart on the table.'),
 ('birthday','{n} made a birthday card for a grandmother. The glue was still wet, so the card lay open on the desk. Soon it would be time to leave.'),
 ('cat','{n} heard a cat crying behind a closed door. The cat belonged to a neighbor. The neighbor was looking for it outside.'),
 ('teamwork','{n} tried to carry a large empty box through a narrow doorway. A friend held the door open. Together they turned the box sideways.'),
 ('cooking','{n} helped an adult make soup. The pot was hot, and the adult held it while {n} set bowls on the table. A pleasant smell filled the kitchen.'),
 ('truth','{n} accidentally tore a library book. The librarian asked what had happened. {n} looked at the torn page and took a deep breath.'),
 ('directions','{n} wanted to reach the pond. A sign pointed left toward the pond and right toward the hill. {n} stopped to read it.'),
 ('waiting','{n} planted beans in a small pot. For several days nothing appeared. Then a green shoot pushed through the soil.'),
 ('ownership','{n} borrowed a blue pencil from a classmate. After drawing a picture, {n} put down the pencil. The classmate needed it for a lesson.'),
 ('cold','{n} saw a friend shivering at a windy bus stop. {n} had an extra scarf in a bag. The bus had not arrived yet.'),
 ('promise','{n} promised to feed a pet rabbit before playing outside. Friends called from the garden. The rabbit waited beside its empty food bowl.'),
 ('river','{n} watched leaves floating down a stream. A small toy boat was caught on a stone near the bank. An adult stood nearby.'),
 ('learning','{n} struggled to tie a shoelace. A patient older cousin showed each step slowly. {n} decided to try again.'),
 ('fairness','{n} and a friend both wanted the same swing. There was only one free swing at the park. They began talking about taking turns.'),
 ('surprise','{n} found a small wrapped parcel on the table. A note said it was for a sister who would arrive after lunch. {n} read the note carefully.'),
 ('animal-fantasy','In a forest where animals could talk, {n} the fox invited a rabbit to tea. The rabbit brought berries. They sat beside a warm fireplace.'),
 ('change-plan','{n} planned to fly a kite, but the wind stopped. A friend brought a ball instead. They looked across the quiet field.')]
 probes=[]
 for i,(family,text) in enumerate(templates):
  for j,n in enumerate(['Nora','Leo']):
   prefix=text.format(n=n);assert len(tok.encode(prefix,bos=True,eos=False))<=96
   probes.append(dict(id=f'new-{i:02d}-{j}',family=family,prefix=prefix,seed=2026102300+i*2+j,max_new_tokens=96))
 anchors=[]
 premises=[('Ada left her red hat in a box.','Ada opened the box and found her red hat inside. She put it on before going outside.','Ada had never owned a hat. The hat she had left in the box was not hers and had never existed.'),
 ('Ben has a pet dog named Pip.','Ben filled a bowl with water for Pip. The dog drank and then lay beside him.','Pip was Ben\'s dog. Pip had never been a dog and Ben had never had any pet.'),
 ('Cara put all three coins in an empty jar. Nobody moved them.','Cara looked into the jar and saw the three coins. She left them there.','The jar contained no coins at all, even though all three were still inside and nothing had moved.'),
 ('Dan is waiting for his sister Eve at the gate.','Eve walked up to the gate and waved. Dan smiled and greeted his sister.','Eve was Dan\'s sister, but Dan had no sister and Eve had never been related to him.'),
 ('A blue cup is on the table. It is the only cup in the room.','Fay picked up the blue cup from the table. She carried it carefully to the sink.','There were no cups in the room, and the blue cup still on the table was the only cup there.'),
 ('Gus planted a seed yesterday. Today a tiny shoot appeared.','Gus watered the soil gently. He was pleased to see the little plant growing.','Gus had never planted anything, and the seed he planted yesterday had never been planted.'),
 ('Hana borrowed a book from Ivy and promised to return it.','Hana finished reading and brought the book back. Ivy thanked her for returning it.','Hana owned every book herself. The borrowed book was never borrowed and Ivy had never owned it.'),
 ('Jack is indoors while heavy rain falls outside.','Jack watched the rain through the window. He decided to wait inside until it eased.','Jack stayed indoors and was outside the whole time, with no movement or change of place.'),
 ('Kim has a brother named Len. Len is sitting beside Kim.','Kim offered Len a biscuit. Her brother smiled and thanked her.','Len was Kim\'s brother, yet Kim had no brothers and Len was not related to Kim in any way.'),
 ('Moe placed a green ball in a bag and closed the bag.','Moe opened the bag later and took out the green ball. He rolled it across the floor.','The green ball remained in the closed bag, but it was never in any bag at any time.')]
 for i,(prefix,good,bad) in enumerate(premises):
  for positive,response in [(True,good),(False,bad)]:anchors.append(dict(id=f'anchor-{i:02d}-{int(positive)}',prefix=prefix,response=response,positive=positive))
 save(ROOT/'probes.json',dict(status='POST_FAILURE_DEVELOPMENT_NOT_ACCEPTANCE',stories=probes))
 save(ROOT/'anchors-private.json',anchors)
 save(ROOT/'rubric.json',dict(dimensions=['grammar','topical continuity','reference/entity consistency','causal/temporal consistency','local coherence'],scale='0 major meaning-changing/hard-to-follow failure; 1 understandable minor error or awkwardness; 2 clear consistent natural text',binary='sum>=8, min>0, no contradiction, no incoherent_sentence',clarifications='Narrative development and new characters allowed if plausibly connected. An implied problem need not be solved. Talking animals allowed when internally consistent. An unfinished final sentence alone is not a failure. Empty, wholly unrelated or context-ignoring repetition fails.'))
 packet=read(OLD/'packet.json');ct=controls(packet['grounded']);checks=[]
 for kind in ['grammar','grounded']:
  for c in packet[kind]:
   lengths=[]
   for option in c['options']:
    ids,n=continuation(tok,c['prefix'],option);lengths.append(len(ids)-n)
    checks.append(dict(id=c['id'],text=c['prefix']+option,joint_ids=ids,prefix_length=n,suffix_length=len(ids)-n))
   assert len(set(lengths))==1
   if kind=='grounded':
    for prefix in ct[c['id']][:2]:
     lens=[len(continuation(tok,prefix,o)[0])-continuation(tok,prefix,o)[1] for o in c['options']];assert len(set(lens))==1
 assert len(checks)==600
 save(ROOT/'tokenization-audit.json',dict(candidate_count=len(checks),all_joint_spans_valid=True,cases=checks,controls=ct))
 save(ROOT/'packet-reference.json',dict(path=str((OLD/'packet.json').relative_to(PROJECT)),sha256=sha(OLD/'packet.json'),validation_sha256=sha(OLD/'validation.npy'),tokenizer_sha256=sha(UPSTREAM/'tokenizer.model')))
 print(json.dumps(dict(probes=40,anchors=20,candidates=600,CPU_preparation='PASS')))
if __name__=='__main__':main()
