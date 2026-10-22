"""Author deterministic research grammar candidates. Not admission/freeze evidence."""
import hashlib,json
from pathlib import Path
from slm.common.tokenizer import BPE
O=Path(__file__).resolve().parent
TOK=BPE.load(O.parent/'tokenizer-8192')
# Each split has independent sentence frames and entity vocabulary. Five frames
# per subtype, five lexical instances, two grammatical directions => 50 items.
CATALOG={
'development':{
 'nouns':[('rabbit','rabbits'),('farmer','farmers'),('sailor','sailors'),('painter','painters'),('dancer','dancers')],
 'names':['Mara','Nolan','Tessa','Felix','Dora'],
 'agreement':['The {noun} {verb} waiting beside the gate.','Near the bridge, the {noun} {verb} resting.','The {noun} behind the fence {verb} quiet.','At dawn, the {noun} {verb} ready to leave.','The {noun} in the garden {verb} hungry.'],
 'tense':[('At lunch, {name} {past} the bread.','By noon, {name} had {part} the bread.','ate','eaten'),('Yesterday, {name} {past} the parcel.','By sunset, {name} had {part} the parcel.','took','taken'),('Last night, {name} {past} the lantern.','By bedtime, {name} had {part} the lantern.','seen','seen'),('Earlier, {name} {past} the glass.','Before dinner, {name} had {part} the glass.','broke','broken'),('At the market, {name} {past} the basket.','Before going home, {name} had {part} the basket.','sold','sold')],
 'pronoun':[('{name} smiled because {pronoun} felt happy.','A friend waved to {pronoun} near the gate.'),('{name} knew that {pronoun} could swim.','The teacher waited for {pronoun} by the pool.'),('When {pronoun} arrived, {name} opened the door.','{name} left a chair for {pronoun} by the door.'),('{name} wondered whether {pronoun} had enough time.','{name} carried a bag for {pronoun} on the journey.'),('After {pronoun} sat down, {name} poured the tea.','{name} put a cup beside {pronoun} on the bench.')],
 'determiner':['{det} {noun} slept under the tree.','We watched {det_lower} {noun} cross the field.','Someone had left food for {det_lower} {noun}.','The child pointed at {det_lower} {noun}.','We walked slowly behind {det_lower} {noun}.']},
'final':{
 'nouns':[('badger','badgers'),('baker','bakers'),('miner','miners'),('carpenter','carpenters'),('gardener','gardeners')],
 'names':['Iona','Rufus','Petra','Silas','Willa'],
 'agreement':['Outside the cottage, the {noun} {verb} sheltering from rain.','The {noun} near the well {verb} watching the clouds.','While a bell rang, the {noun} {verb} still asleep.','The {noun} across the road {verb} preparing for winter.','Inside the shed, the {noun} {verb} safe from the storm.'],
 'tense':[('During the picnic, {name} {past} an apple.','When the picnic ended, {name} had {part} an apple.','ate','eaten'),('On Monday, {name} {past} a small lamp.','When Tuesday came, {name} had {part} a small lamp.','took','taken'),('After sunrise, {name} {past} a bright bird.','When the sun set, {name} had {part} a bright bird.','saw','seen'),('During the move, {name} {past} a wooden bowl.','When the move ended, {name} had {part} a wooden bowl.','broke','broken'),('On the last trip, {name} {past} a silver coin.','When the trip ended, {name} had {part} a silver coin.','gave','given')],
 'pronoun':[('{name} noticed that {pronoun} needed a coat.','A neighbour fetched a coat for {pronoun}.'),('Before {pronoun} left, {name} checked the window.','{name} closed the window behind {pronoun}.'),('{name} was certain that {pronoun} could find the trail.','{name} marked the trail ahead of {pronoun}.'),('Unless {pronoun} hurried, {name} would miss the train.','{name} saved a train ticket for {pronoun}.'),('Although {pronoun} was tired, {name} kept walking.','{name} set a lantern near {pronoun}.')],
 'determiner':['A visitor offered water to {det_lower} {noun}.','{det} {noun} approached the old mill.','There was a narrow path beside {det_lower} {noun}.','We heard footsteps beyond {det_lower} {noun}.','An old cart stood between the barn and {det_lower} {noun}.']}}
# Distinct past/participle forms are necessary: ambiguous/syncretic pairs are
# excluded by construction, never assigned a guessed label.
CATALOG['development']['tense'][2]=('Last night, {name} {past} the lantern.','By bedtime, {name} had {part} the lantern.','saw','seen')
CATALOG['development']['tense'][4]=('At the market, {name} {past} the basket to a friend.','Before going home, {name} had {part} the basket to a friend.','gave','given')

def build(split):
    c=CATALOG[split];items=[]
    for subtype in ['agreement','tense','pronoun','determiner']:
        for frame in range(5):
            for lexical in range(5):
                for direction in range(2):
                    noun=c['nouns'][lexical][direction];name=c['names'][lexical]
                    if subtype=='agreement':
                        template=c[subtype][frame];forms=['was','were'];good=direction
                        alternatives=[template.format(noun=noun,verb=x) for x in forms]
                    elif subtype=='tense':
                        past,part,a,b=c[subtype][frame];assert a!=b
                        template=[past,part][direction];good=direction
                        alternatives=[template.format(name=name,past=x,part=x) for x in [a,b]]
                    elif subtype=='pronoun':
                        template=c[subtype][frame][direction];good=direction
                        alternatives=[template.format(name=name,pronoun=x) for x in ['he','him']]
                    else:
                        template=c[subtype][frame];good=direction
                        alternatives=[template.format(noun=noun,det=x.capitalize(),det_lower=x) for x in ['this','these']]
                    alternatives=[' '+x for x in alternatives]
                    lengths=[len(TOK.encode(x)) for x in alternatives]
                    position=(frame*5+lexical+direction)%2
                    if good!=position:alternatives.reverse();lengths.reverse()
                    items.append({'id':f'{split}:{subtype}:{frame}:{lexical}:{direction}',
                     'split':split,'subtype':subtype,'template_family':f'{split}:{subtype}:{frame}',
                     'entity':name if subtype in ('tense','pronoun') else noun,
                     'prompt':'','alternatives':alternatives,'correct_index':position,
                     'continuation_token_lengths':lengths,'length_match':len(set(lengths))==1,
                     'label_basis':'Authored grammatical contrast; requires review and leakage screening before freeze.'})
    return items

def main():
    results={}
    for split in CATALOG:
        items=build(split);path=O/(split+'-grammar-candidates.jsonl')
        if path.exists():raise FileExistsError('Preserve prior draft')
        path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items))
        results[split]={'items':len(items),'length_mismatches':[x['id'] for x in items if not x['length_match']],
                        'correct_positions':[sum(x['correct_index']==i for x in items) for i in range(2)],
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (O/'grammar-build-result.json').write_text(json.dumps({'status':'DRAFT_NOT_FROZEN','results':results},indent=2)+'\n')
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
