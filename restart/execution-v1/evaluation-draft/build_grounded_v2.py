"""Controlled narrative comprehension drafts with explicit state-based oracles."""
import hashlib,json,random
from pathlib import Path
from slm.common.tokenizer import BPE
O=Path(__file__).resolve().parent;TOK=BPE.load(O.parent/'tokenizer-8192')
COLORS=['red','blue','green','white'];PLACES=['box','bed','bag','cup']
NAMES={'development':['Mara','Tessa','Lena','Eva'],'final':['Iona','Petra','Silas','Ada']}
WEATHER=['cold','warm','windy','rainy','sunny']
FACT={
'development':[
 'On a {weather} morning, four things lay on a table. The scarf was {scarf}. The hat was {hat}. The coat was {coat}. The glove was {glove}.',
 'A child sorted some clothes on a {weather} afternoon. A {hat} hat lay beside a {glove} glove. The child also found a {scarf} scarf and a {coat} coat.',
 'During a {weather} day, a painter checked four pieces of clothing. The coat was {coat}, the scarf was {scarf}, the glove was {glove}, and the hat was {hat}.',
 'It was {weather} outside. Inside a cabin, a {glove} glove hung beside a {coat} coat. A {hat} hat and a {scarf} scarf rested on a chair.',
 'After a {weather} walk, a child unpacked a bag. Out came a {scarf} scarf, a {glove} glove, a {hat} hat, and a {coat} coat.'],
'final':[
 'The shopkeeper opened the chest during a {weather} evening. It contained a hat colored {hat}, a glove colored {glove}, a scarf colored {scarf}, and a coat colored {coat}.',
 'Before leaving on a {weather} day, a visitor checked the clothes on the hooks. The glove looked {glove}. The coat looked {coat}. The hat looked {hat}. The scarf looked {scarf}.',
 'A {weather} breeze blew through the open window. On the shelf were four garments: a coat that was {coat}, a scarf that was {scarf}, a hat that was {hat}, and a glove that was {glove}.',
 'At the end of a {weather} journey, a traveller arranged four garments on a bench. One was a {coat} coat. Another was a {hat} hat. The remaining two were a {glove} glove and a {scarf} scarf.',
 'A tailor worked indoors while the weather was {weather}. The finished scarf was {scarf}; the finished glove was {glove}. The completed hat was {hat}, and the completed coat was {coat}.']}
REF={
'development':[
 ('{sender} handed a ribbon to {recipient}. {observer} watched from the doorway while {other} opened the window. The recipient tucked the ribbon into a pocket.','Who tucked the ribbon into a pocket?'),
 ('{sender} gave a shell to {recipient}. {observer} carried a basket and {other} held a lamp. The person who received the shell put it on a shelf.','Who put the shell on a shelf?'),
 ('A note passed from {sender} to {recipient}. {observer} sat on a stool while {other} looked outside. The receiver read the note aloud.','Who read the note aloud?'),
 ('{sender} offered a flower to {recipient}, who accepted it. {observer} was sweeping and {other} was reading. The person who accepted the flower placed it in a vase.','Who placed the flower in a vase?'),
 ('{recipient} accepted a small bell from {sender}. {other} shut the gate while {observer} tied a shoe. The receiver rang the bell once.','Who rang the bell?')],
'final':[
 ('The parcel changed hands from {sender} to {recipient}. {other} mended a chair while {observer} folded a blanket. Its new owner put the parcel under the chair.','Who put the parcel under the chair?'),
 ('{sender} presented a wooden bird to {recipient}. {observer} filled a bowl and {other} lit a candle. The person given the bird examined its wings.','Who examined the wooden bird?'),
 ('{recipient} was given a candle by {sender}. Nearby, {other} opened a book and {observer} moved a stool. The person who had received the candle placed it on the mantel.','Who placed the candle on the mantel?'),
 ('A ticket was delivered by {sender} to {recipient}. {other} held an umbrella while {observer} closed a case. The person to whom it was delivered kept the ticket in a wallet.','Who kept the ticket in a wallet?'),
 ('{sender} passed a marble to {recipient}. {observer} walked to the door and {other} sat by the fire. The new holder rolled the marble across the floor.','Who rolled the marble across the floor?')]}

def build(split):
    rng=random.Random(2026102110+(split=='final'));items=[]
    for kind,groups in [('explicit_fact',10),('temporal',5),('reference',5)]:
        for group in range(groups):
            cohort=[]
            for variant in range(5):
                idx=len(items);answer=(group*5+variant)%4;weather=WEATHER[variant]
                if kind=='explicit_fact':
                    # Query scarf in first five families and glove in the next five.
                    target='scarf' if group<5 else 'glove';objects=['scarf','hat','coat','glove']
                    mapping={target:COLORS[answer]};remaining=[c for c in COLORS if c!=COLORS[answer]];rng.shuffle(remaining)
                    mapping.update(zip([o for o in objects if o!=target],remaining))
                    passage=FACT[split][group%5].format(weather=weather,**mapping)
                    question=f'What color was the {target}?'
                    answers=[f' The {target} was {c}.' for c in COLORS]
                    oracle={'kind':'explicit_mapping','mapping':mapping,'query':target,'answer':COLORS[answer]}
                elif kind=='temporal':
                    # A four-state trajectory with distinct locations. All choices
                    # occur in the passage; query an exact intermediate/final state.
                    query=[1,2,3,1,2][group]
                    remaining=[p for p in PLACES if p!=PLACES[answer]];rng.shuffle(remaining)
                    states=[]
                    for step in range(4):states.append(PLACES[answer] if step==query else remaining.pop())
                    if split=='development':
                        passage=(f'On a {weather} day, a coin lay beside the {states[0]}. '
                          f'First, a child moved it beside the {states[1]}. Next, the child moved it beside the {states[2]}. '
                          f'Finally, the coin was moved beside the {states[3]}.')
                        question=['','Where was the coin after the first move?','Where was the coin after the second move?','Where was the coin after the final move?'][query]
                    else:
                        passage=(f'During a {weather} evening, a button began beside the {states[0]}. '
                          f'Its first new resting place was beside the {states[1]}. Its second new resting place was beside the {states[2]}. '
                          f'For its third and last move, someone put it beside the {states[3]}.')
                        question=['','Where was the button before its second move?','Where was the button before its third move?','Where was the button when all moves were finished?'][query]
                    answers=[f' It was beside the {p}.' for p in PLACES]
                    oracle={'kind':'state_trajectory','states':states,'query_state':query,'answer':PLACES[answer]}
                else:
                    names=NAMES[split];recipient=names[answer];others=[n for n in names if n!=recipient];rng.shuffle(others)
                    roles=dict(recipient=recipient,sender=others[0],observer=others[1],other=others[2])
                    template,question=REF[split][group]
                    passage=f'It was a {weather} day. '+template.format(**roles)
                    answers=[f' It was {n}.' for n in names]
                    oracle={'kind':'role_reference','roles':roles,'query_role':'recipient','answer':recipient}
                # Position is fixed globally before any model output; lexical answer
                # and answer position are not linked by a fixed permutation.
                correct_position=idx%4;order=list(range(4));rng.shuffle(order)
                where=order.index(answer);order[where],order[correct_position]=order[correct_position],order[where]
                alternatives=[answers[i] for i in order];lengths=[len(TOK.encode(x)) for x in alternatives]
                assert len(set(lengths))==1
                item={'id':f'{split}:grounded:{idx:03d}','split':split,'subtype':'explicit_fact' if kind=='explicit_fact' else 'temporal_reference',
                  'detail_subtype':kind,'template_family':f'{split}:{kind}:{group%5 if kind=="explicit_fact" else (0 if kind=="temporal" else group)}',
                  'passage':passage,'question':question,'prompt':passage+'\nQuestion: '+question+'\nAnswer:',
                  'alternatives':alternatives,'correct_index':correct_position,'continuation_token_lengths':lengths,
                  'oracle':oracle,'controls':{'empty_prompt':'Question: '+question+'\nAnswer:'}}
                items.append(item);cohort.append(item)
            # Actual derangement within compatible question/template groups;
            # shifted passage has different answer and same answer vocabulary.
            for i,item in enumerate(cohort):
                source=cohort[(i+2)%5]
                assert source['oracle']['answer']!=item['oracle']['answer']
                item['controls'].update(shuffled_source_id=source['id'],shuffled_prompt=source['passage']+'\nQuestion: '+item['question']+'\nAnswer:',shuffled_passage_answer=source['oracle']['answer'])
    return items

def main():
    result={}
    for split in NAMES:
        rows=build(split);assert len(rows)==100
        path=O/(split+'-grounded-v2-candidates.jsonl')
        if path.exists():raise FileExistsError('Draft exists; do not overwrite')
        path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
        result[split]={'items':len(rows),'answer_positions':[sum(x['correct_index']==i for x in rows) for i in range(4)],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (O/'grounded-v2-build-result.json').write_text(json.dumps({'status':'DRAFT_NOT_FROZEN','results':result},indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
