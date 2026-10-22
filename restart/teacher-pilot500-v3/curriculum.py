"""Fifty distinct task families; full families stay in a single split."""
# Creator: Navneet Prabhakar
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parent

PASSAGES=[
 'A storm soaked the boxes outside a small bookshop. Lina moved the dry books upstairs and laid the damp ones on towels. By evening the owner had called off the outdoor sale.',
 'A school radio lost power just before a music show. Arun found a charged battery in a cupboard. The presenters started seven minutes late and thanked the listeners for waiting.',
 'A visitor left a blue scarf on a ferry. The cleaner put it in the lost-property office rather than taking it home. The visitor collected it the next morning.',
 'Two neighbours wanted to plant the same empty strip of land. One preferred flowers and the other wanted herbs. They agreed to divide the strip and share the watering.',
 'Maya practised a speech in an empty theatre. A friend said the ending was hard to hear. She slowed down and repeated the final sentence more clearly.',
 'A delivery of red tiles arrived at a shop that had ordered grey tiles. The manager kept the boxes sealed and contacted the supplier. Work stopped while a replacement was arranged.',
 'A child found a cracked bird-shaped ornament beside a gate. Its owner said it had belonged to her grandfather. They wrapped the pieces carefully and placed them in a box.',
 'The museum moved a painting away from a sunny window. Staff explained that the light could fade its colours. Visitors could still see it in an interior gallery.',
 'A baker made a smaller batch after several loaves went unsold. The next day every loaf sold before closing. She wrote down the result before deciding whether to change the recipe.',
 'A hiking group reached a closed bridge. Their map showed another crossing farther upstream. They checked the route together and turned back before it grew dark.',
]

def make():
    rows=[];rng=random.Random(221022500)
    names=['Ada','Ishan','Mei','Noor','Luis','Faye','Kiran','Rosa','Theo','Zara']
    for i in range(10):
      name=names[i];n=i+2;other=names[(i+3)%10]
      def add(f,u,v,o1='',o2='',required1=(),required2=(),caps=(80,80)):
        rows.append(dict(id=f'{f}-{i:02d}',family=f,variant=i,users=[u,v],
                         oracle_notes=[o1,o2],required=[list(required1),list(required2)],wordcaps=list(caps)))
      cap=15+i;people=cap+[-3,2,0,-1,4,-2,1,-4,3,-5][i];extra=[1,2,3,0,2,5,0,1,2,6][i]
      def fit(k):return f'Yes; {cap-k} seats remain.' if k<=cap else f'No; shortfall {k-cap} seats.'
      add('capacity_decisions',f'A room has {cap} seats and {people} visitors. Can everybody sit? State the remaining seats or shortfall.',
          f'{extra} more visitors arrive. Can everyone sit now? Give the updated remaining seats or shortfall.',fit(people),fit(people+extra))
      a=17+3*i;b=31+i;newa=22+2*i
      def cheaper(x,y):return f'A is cheaper by {y-x} credits.' if x<y else f'B is cheaper by {x-y} credits.' if y<x else 'They cost the same.'
      add('price_comparisons',f'Option A costs {a} credits and B costs {b} credits. Which costs less, and what is the difference?',
          f'A changes to {newa} credits; B is unchanged. Compare them again.',cheaper(a,b),cheaper(newa,b))
      start=8*60+10*i;setup=5+i;practice=15;end=start+setup+practice
      def clock(t):return f'{t//60:02d}:{t%60:02d}'
      add('sequential_schedules',f'I can start at {clock(start)}. Setup takes {setup} minutes, followed by {practice} minutes of practice. Give the two time intervals.',
          'Setup needs five extra minutes. Keep the original finish time and shorten practice. Give the revised intervals.',
          f'Setup {clock(start)} to {clock(start+setup)}; practice {clock(start+setup)} to {clock(end)}.',
          f'Setup {clock(start)} to {clock(start+setup+5)}; practice {clock(start+setup+5)} to {clock(end)}.')
      add('unit_conversion',f'In this shop, each pack contains {n} cards. How many cards are in {n+3} packs?',
          'I remove one full pack and add two loose cards. What is the total now?',str(n*(n+3)),str(n*(n+2)+2))
      stock=30+i*2;order=12+i;ship=3+i
      add('stock_accounting',f'A stall starts with {stock} notebooks and sells {order}. How many remain?',
          f'It then receives {ship} more notebooks and sells 4. Give the new stock.',str(stock-order),str(stock-order+ship-4))
      limit=40+i*3;cost=13+i;cost2=18+i
      brush=3+i%4
      add('budget_revisions',f'My craft budget is {limit} credits. Paint costs {cost} and paper costs {cost2}. How much is left after buying both?',
          f'I add a brush costing {brush} credits. Am I still within budget, and how much remains?',str(limit-cost-cost2),f'Yes; {limit-cost-cost2-brush} credits remain.')
      add('cart_totals',f'I buy {n} cups at 4 credits each and one tray at {i+7} credits. What is the total?',
          'Remove one cup and add a second tray at the same tray price. What is the revised total?',str(n*4+i+7),str((n-1)*4+2*(i+7)))
      objects=['brass key','green folder','red umbrella','silver bookmark','blue notebook','wooden whistle','black pouch','striped scarf','glass marble','yellow cap']
      obj=objects[i]
      add('tracking_possessions',f'{name} gave a {obj} to {other}. {other} put it in a desk drawer. Who has it, and where is it?',
          f'{other} returns it to {name}, who puts it on a shelf. Where is it now and who has it?',f'{other}; desk drawer.',f'{name}; shelf.',[other,'drawer'],[name,'shelf'])
      add('event_order',f'In a story, {name} waters a plant after opening the window but before writing a letter. What happens immediately before and after watering?',
          'Insert making tea between watering and writing. What happens immediately after watering now?',
          'Before: opening the window. After: writing a letter.','Making tea.',['window','letter'],['tea'])
      add('pronoun_resolution',f'{name} lent {other} a coat because {other} was cold. Who was cold, and who owned the coat initially?',
          f'{other} thanked {name} and returned the coat. Who owns it now?',f'{other} was cold; {name} owned the coat.',name,[other,name],[name])
      add('exceptions_and_negation',f'A fictional library lets members borrow maps, but fragile maps must stay inside. {name} is a member and asks to take a fragile map home. Is that allowed?',
          'The librarian replaces it with a non-fragile map. Is taking that replacement home allowed under the stated rule?',
          'No; the fragile-map exception applies.','Yes; members may borrow a non-fragile map.')
      stops=[f'Pine{i}',f'Elm{i}',f'Oak{i}',f'Birch{i}']
      add('route_constraints',f'The only paths are {stops[0]}–{stops[1]}, {stops[1]}–{stops[2]} and {stops[2]}–{stops[3]}. Give a route from {stops[0]} to {stops[3]}.',
          f'The path between {stops[1]} and {stops[2]} closes. '+(f'A new path connects {stops[0]} directly to {stops[2]}. ' if i%2==0 else '')+'Is a route between the original endpoints still possible?',
          ' → '.join(stops),f'Yes: {stops[0]} to {stops[2]} to {stops[3]}.' if i%2==0 else 'No; the closure disconnects the endpoints.',stops)
      add('rule_based_labels',f'Label a parcel LARGE if its weight is at least 10 units; otherwise label it SMALL. This parcel weighs {n+3} units. Give its label.',
          'The rule changes: LARGE now means at least 7 units. Relabel the same parcel.',
          'LARGE' if n+3>=10 else 'SMALL','LARGE' if n+3>=7 else 'SMALL')
      days=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];day=days[i%7]
      add('weekday_offsets',f'Today is {day}. What weekday will it be in {n} days? Count tomorrow as day one.',
          'And what weekday was it two days before today?',days[(i%7+n)%7],days[(i%7-2)%7])
      nums=[n*3,n+1,n*2,n-1]
      add('sorting_and_selection',f'Sort these values from smallest to largest: {nums}.',
          'Remove the largest value. What is the largest remaining value?',str(sorted(nums)),str(sorted(nums)[-2]))
      colours=['blue','red','green','yellow','black','white','purple','orange','pink','grey'];c1=colours[i];c2=colours[(i+1)%10];c3=colours[(i+2)%10]
      add('set_constraints',f'The {c1} bag is light but has no zip. The {c2} bag is heavy and has a zip. The {c3} bag is light and has a zip. I need both a light bag and a zip. Which fits?',
          f'The {c3} bag is unavailable. Does either remaining bag satisfy both requirements?',
          f'The {c3} bag.',f'No; {c1} lacks a zip and {c2} is heavy.',[c3])
      add('directory_extraction',f'Fictional directory: North desk, contact {name}, opens {clock(start)}, extension {210+i}; South desk, contact {other}, opens 12:00. Return the North contact and extension only.',
          'Now give the South opening time only.',f'{name}; {210+i}.','12:00',[name,str(210+i)],['12:00'])
      add('json_formatting',f'Convert this record to a JSON object with keys name and count: name={name}, count={n}. Use a number for count.',
          f'Add the field active with boolean true, leaving name and count unchanged.',
          json.dumps(dict(name=name,count=n)),json.dumps(dict(name=name,count=n,active=True)))
      add('evidence_limits',f'A note says {name} left a parcel at the depot at {clock(start)}. It says nothing about a delivery address. What address is it going to?',
          f'New information: its destination is Cedar House {i+1}. What address should be recorded now?',
          'The note does not specify an address.',f'Cedar House {i+1}.',(),[f'Cedar House {i+1}'])
      add('conflicting_records',f'Two records disagree: one says box {i+1} contains pens and the other says it contains brushes. No record is marked newer. What should I assume?',
          'The owner confirms the brush record is correct. State the contents now.',
          'Do not choose without evidence; ask for confirmation.','Brushes.',(),['brushes'])
      add('shared_house_plans',f'{name} can clean on weekday evenings; {other} is only free on Saturday. They want to share cleaning fairly. Suggest a simple arrangement without inventing their preferences.',
          f'{other} cannot do this Saturday. Suggest how they could discuss a temporary adjustment rather than assigning a task without consent.',
          'Use the stated availability; propose discussing an equitable division.','Suggest discussing a swap or postponement, not assuming agreement.')
      add('polite_requests',f'Make this request polite while keeping its meaning: "{other}, return my {obj} by Friday."',
          'Make it friendlier and under 16 words, keeping the Friday deadline.',
          'A polite request to return the same item by Friday.','A friendly request preserving Friday and the item.',[obj,'Friday'],[obj,'Friday'],(80,16))
      problems=['a torn cover','a missing button','a scratched case','the wrong colour','an empty inner box','a loose handle','a missing lid','the wrong size','a cracked frame','a broken zip']
      add('complaint_responses',f'A customer says a parcel arrived with {problems[i]}. You know only that complaint. Draft a short helpful response acknowledging it and asking for one useful detail; do not promise a refund.',
          'They provide the order number. Explain what you would check next without claiming you have looked it up.',
          'Acknowledge the damage, request an order number or photo; no unsupported refund promise.','Describe a possible next check, without claiming tool access or a completed lookup.')
      add('cancellation_drafts',f'Write a brief request to cancel my {n}-person reservation for Friday. Do not invent a cancellation policy or claim it is already cancelled.',
          f'Change the request to reduce the booking to {n-1} people instead of cancelling it.',
          f'A draft cancellation request for {n} people on Friday.',f'A request to reduce the reservation to {n-1}, keeping Friday.')
      add('status_updates',f'Write a two-sentence update using only these facts: draft finished; review pending; {name} owns the review. Do not invent a date.',
          f'Correction: {other} now owns the review. Revise the update.',
          f'Draft finished, review pending, owner {name}.',f'Draft finished, review pending, owner {other}.',[name],[other])
      add('meeting_actions',f'Notes: {name} will check the poster on Tuesday; {other} will order paper on Wednesday. Extract the two actions with owners and days.',
          f'{other} changes the paper order to Thursday. Restate just the updated action.',
          f'{name}: check poster Tuesday. {other}: order paper Wednesday.',f'{other}: order paper Thursday.',[name,other,'Tuesday','Wednesday'],[other,'Thursday'])
      behaviours=['interrupts you during rehearsals','changes plans at the last minute','borrows your books without asking','leaves the shared table cluttered','plays loud music while you read','shares your unfinished drafts without asking','jokes about your typos in public','calls during your study time','moves your art supplies without asking','answers questions on your behalf']
      add('constructive_feedback',f'A friend {behaviours[i]}. Write a respectful sentence describing the behaviour and asking for a change, without judging their personality.',
          'They say they were trying to help. Reply briefly while keeping the request.',
          'Describe interruption and ask to finish speaking.','Acknowledge the intention and keep the behavioural request.')
      add('declining_invitations',f'Decline an invitation to {other}’s picnic warmly. You cannot attend; do not make up a reason.',
          'Make it one sentence under 18 words.',
          'Warm decline with no invented excuse.','Short warm decline.',[other],(),(80,18))
      add('apology_and_repair',f'I forgot to return a borrowed {obj}. Draft an apology that takes responsibility and asks when I can return it; do not invent excuses.',
          'They say tomorrow afternoon is suitable. Reply with that plan, as a draft message.',
          'Apology, responsibility, request a return time.','A draft confirming tomorrow afternoon.',[obj],['tomorrow','afternoon'])
      add('personal_boundaries',f'I cannot take phone calls after {17+i//2}:00 on {day}. Write a polite message setting that boundary and offering to talk earlier.',
          'The person insists on a late call. Repeat the boundary respectfully without agreeing to it.',
          f'No calls after {17+i//2}:00 on {day}; offer earlier.',f'Keep the same boundary; do not agree to the late call.')
      theme=['river','moon','forest','stars','clock','sea','rain','mountain','garden','lantern'][i]
      add('creative_naming',f'Suggest three original names for a fictional reading room with a {theme} theme. Use a numbered list.',
          'Choose one and explain its mood in one sentence; do not claim the name is legally available.',
          'Three theme-related invented names.','Select one previously suggested name and explain it.')
      starts=[
        'A small robot found a seed in an empty station. It had never seen a plant.',
        'Nora heard a tune coming from a sealed wooden box in the attic.',
        'A fox carried a lost letter to a village where nobody knew its name.',
        'The last lantern on the pier flickered as a tiny boat approached.',
        'An apprentice potter discovered a thumbprint inside a bowl she had not made.',
        'A sleepy dragon woke to find its cave filled with paper cranes.',
        'A clockmaker noticed that one clock ran backwards only when it rained.',
        'A child planted a pebble and returned each morning to water it.',
        'The village dog waited beside a bus that had not run for years.',
        'A traveller found a map with her own footprints already drawn on it.',
      ]
      add('narrative_continuations',f'Continue this fictional opening in two short sentences, preserving the premise: {starts[i]}',
          'Give it a hopeful ending in one sentence, consistent with what you just wrote.',
          'Coherent invented continuation, no contradiction of the opening.','Hopeful ending consistent with the actual prior reply.')
      analogies=[('a queue','people waiting their turn'),('a folder','a container for related files'),('a backup','an extra copy kept for recovery'),('a filter','a rule that selects matching items'),('a schedule','a plan assigning activities to times'),('a password','a secret used to help control access'),('a draft','a version that can still be revised'),('an index','a guide pointing to where items can be found'),('a checklist','a list used to check whether steps are complete'),('a template','a reusable starting pattern')]
      concept,definition=analogies[i]
      add('simple_analogies',f'For this exercise, {concept} means {definition}. Explain it to a beginner with one everyday analogy.',
          'Point out one limitation of your analogy.',
          'Accurate simple analogy for the supplied definition.','One genuine limitation of the actual analogy; no change of concept.')
      pairs=[('borrow','lend'),('before','after'),('include','exclude'),('temporary','permanent'),('optional','required'),('increase','decrease'),('arrive','depart'),('accept','decline'),('empty','full'),('earlier','later')]
      w1,w2=pairs[i]
      add('word_distinctions',f'Explain the difference between “{w1}” and “{w2}” in plain English, with a short example.',
          f'Give me a new example using “{w2}”, without repeating the first example.',
          'Correct ordinary English meanings and a suitable example.','A distinct grammatical example of the second word.',[w1,w2],[w2])
      crafts=['a simple folded bookmark','a standing name card','a folded paper fan','a small paper sleeve','a folded corner marker','a paper name tag','a folded note envelope without adhesive','a simple paper boat','a folded paper triangle','a folded zigzag strip']
      add('procedural_instructions',f'I have a sheet of paper, a pencil and a ruler. Explain how to make {crafts[i]}; assume no other tools.',
          'I have no ruler after all. Adapt the instructions without introducing scissors or glue.',
          'Practical paper-folding instructions using only listed objects.','Work without the ruler and do not introduce unlisted tools.')
      add('explaining_code',f'This Python loop should print {n} values, starting at zero: for x in range({n-1}): print(x). Explain the mistake and show the corrected range.',
          'Now I want values from one up to that same final count, inclusive. What range should I use?',
          f'Use range({n}) because stop is exclusive.',f'Use range(1, {n+1}).')
      tradeoffs=[
       ('Bag A is waterproof but heavy. Bag B is light but not waterproof.','keeping papers dry in rain','carrying less weight indoors','A; heavy','B; light'),
       ('Bus A is fast but costs more. Bus B is slow but cheap.','spending less on a trip with no deadline','arriving as fast as possible','B; slow','A; fast'),
       ('Keyboard A is quiet but large. Keyboard B is compact but loud.','working near someone who needs silence','saving desk space while alone','A; large','B; compact'),
       ('Bottle A is light but uninsulated. Bottle B is insulated but heavy.','keeping a drink warm','minimising carrying weight','B; heavy','A; light'),
       ('Lamp A is bright but bulky. Lamp B is small but dim.','lighting detailed drawings clearly','fitting the lamp in a tiny display','A; bulky','B; small'),
       ('Chair A is sturdy but fixed. Chair B folds but is less sturdy.','storing the chair in a cupboard','maximising sturdiness in a permanent spot','B; less sturdy','A; sturdy'),
       ('Notebook A has many pages but is heavy. Notebook B has few pages but is light.','writing a long project in one notebook','carrying as little as possible','A; heavy','B; light'),
       ('Cloth A absorbs much water but dries slowly. Cloth B absorbs less but dries quickly.','having the cloth dry again quickly','soaking up a large spill in one go','B; absorbs less','A; absorbs much'),
       ('Route A is shaded but long. Route B is short but unshaded.','staying in shade','taking the shortest route','A; long','B; short'),
       ('Tent A holds four people but is heavy. Tent B holds two but is light.','carrying less weight for one person','accommodating four people','B; only two people','A; four people'),
      ]
      facts,priority,changed,answer1,answer2=tradeoffs[i]
      add('qualitative_tradeoffs',f'{facts} I care most about {priority}. Which option fits, and what is its drawback?',
          f'My priority changes to {changed}. Reconsider the choice using only the supplied facts.',answer1,answer2)
      apps=['drawing','audio editing','photo editing','spreadsheet','text editing','presentation','note taking','video editing','diagramming','page layout']
      add('software_troubleshooting',f'A {apps[i]} app can open one saved file but fails to open another. Suggest two low-risk checks before deleting anything.',
          f'The second file has a different file extension from the working {apps[i]} file. What should I check next?',
          'Check file integrity/format/location/permissions without destructive steps.','Check whether the app supports the extension and whether a compatible app or export is available; do not claim diagnosis is certain.')
      organising=['organising a study desk','packing an art bag','tidying a bookcase','planning a short study break','organising a shared cupboard','keeping notes readable','planning a quiet reading hour','sorting loose photos','preparing for a board game','putting away drawing supplies']
      add('format_constraints',f'Write exactly three bullet points about {organising[i]}. Each bullet must contain at most six words.',
          'Turn those ideas into one sentence of at most 18 words.',
          'Exactly three short desk-organisation bullets.','One concise sentence retaining the main ideas.',(),(),(25,18))
      add('preserving_negation',f'Rewrite without changing meaning: “{name} did not agree to send the report before Friday.”',
          'Make clear that this sentence does not prove the report will be sent on Friday.',
          'Preserve the lack of agreement and before-Friday scope.','Explicitly distinguish no agreement before Friday from a promise to send on Friday.',[name,'Friday'],['Friday'])
      labels=['A','B','C'];l1=labels[i%3];l2=labels[(i+1)%3];l3=labels[(i+2)%3]
      add('preference_updates',f'I want a fictional game that is quiet and cooperative. Game {l1} is noisy and cooperative; {l2} is quiet and competitive; {l3} is quiet and cooperative. Choose using only these descriptions.',
          f'I now want competition rather than cooperation, while keeping quiet play. Reconsider the {n}-minute game session.',
          f'Choose game {l3}.',f'Choose game {l2}.',[l3],[l2])
      actions=['send an email','book a train ticket','set a device alarm','move a file on my computer','check my bank balance','turn off my room light','post to my social account','call a shop','upload a photo','cancel a subscription']
      add('capability_honesty',f'In this chat you have no tools or external access. Can you actually {actions[i]} for me now?',
          'Then give me a short manual next step without claiming you performed the action.',
          'Cannot perform the action in this no-tool setting; do not invent a result.','A practical manual step appropriate to the requested action; no completed-action claim.')
      add('changing_topics',f'Help me make a simple packing list for a rainy afternoon walk. Give three items.',
          f'New topic: explain what “{w1}” means in one sentence. Do not continue the packing list.',
          'Three sensible items for a rainy walk.','Correct plain English meaning of the requested word; follow the topic change.',(),[w1])
      add('correcting_details',f'Draft a label: recipient {name}; parcel colour blue; collection on Monday.',
          f'Correction: recipient is {other}, colour is green, and collection is Tuesday. Give the corrected label only.',
          f'{name}; blue; Monday.',f'{other}; green; Tuesday.',[name,'blue','Monday'],[other,'green','Tuesday'])
      kinds=['folder','pencil','mug','box','notebook','bag','card','jar','bowl','case'];kind=kinds[i]
      add('ambiguous_references',f'I have a {c1} {kind} and a {c2} {kind}. I said “put it on the shelf.” What clarification do you need?',
          f'I mean the {c2} {kind}. Restate the instruction clearly.',
          f'Ask which {kind}; do not assume a colour.',f'Put the {c2} {kind} on the shelf.',(),[c2,kind,'shelf'])
      second=kinds[(i+3)%10]
      add('remembering_updates',f'For this conversation, my {kind} is {c1} and my {second} is {c2}. Which item is {c2}?',
          f'I replaced the {second} with a {c3} one. What are the current colours of both items?',
          f'The {second}.',f'{kind} {c1}; {second} {c3}.',[second],[c1,c3])
      add('passage_summaries',f'Summarize this fictional passage in at most 30 words without adding facts: {PASSAGES[i]}',
          'Give a shorter version of at most 15 words that still preserves the central event.',
          'Faithful useful summary of the entire supplied passage.','Faithful concise summary retaining the main event.',(),(),(30,15))
      tasks=[('wash the mug','dry the mug','put the mug away'),('write a title','add a date','sign the note'),('choose a book','read a page','mark the place'),('open the box','count the pieces','close the box'),('pick a colour','draw a shape','label the shape'),('fold a sheet','write a name','place it upright'),('collect the cards','sort by colour','store each group'),('clear a shelf','wipe it','replace the books'),('choose a route','check its length','write the directions'),('find a photo','add a caption','save the draft')][i]
      add('list_to_prose',f'Turn these steps into one natural sentence, keeping their order: 1) {tasks[0]}; 2) {tasks[1]}; 3) {tasks[2]}.',
          'Now present the same instructions as a numbered list, keeping the original order.',
          'A natural sentence preserving all three steps and order.','Three numbered steps in the original order.')
      words=[['sun','rain','wind','snow'],['cat','dog','bird','fish'],['red','blue','green','gold'],['pen','book','desk','chair'],['oak','elm','pine','birch'],['east','west','north','south'],['cup','plate','bowl','spoon'],['walk','run','rest','jump'],['day','night','dawn','dusk'],['seed','leaf','root','stem']][i]
      add('impossible_constraints',f'Write exactly three words while including all four distinct words {", ".join(words)}. Can both requirements be satisfied?',
          'Relax the length to four words. Give just those four words.',
          'No; including four distinct words requires at least four words.',' '.join(words),(),words,(80,4))
      add('calibrated_predictions',f'A fictional team won {n} of its last {n+2} games. Does that guarantee it will win the next game? Explain briefly.',
          'Someone says the win is certain. What would be a more careful way to phrase that claim?',
          'Past results do not guarantee the next outcome.','Express uncertainty; avoid asserting a guaranteed win.')
    families=sorted({r['family'] for r in rows})
    assert len(families)==50 and len(rows)==500
    if len({tuple(r['users']) for r in rows})!=500:
        from collections import Counter
        duplicate=Counter(tuple(r['users']) for r in rows)
        raise ValueError('Duplicate prompt families: '+str(sorted({r['family'] for r in rows if duplicate[tuple(r['users'])]>1})))
    order=sorted(families,key=lambda f:hashlib.sha256(('luna-diverse-v3-family-split:'+f).encode()).hexdigest())
    assignment={f:'train' if j<40 else 'development' if j<45 else 'test' for j,f in enumerate(order)}
    for r in rows:r['split']=assignment[r['family']]
    # Mix families per request, without mixing their dataset ownership.
    rows.sort(key=lambda r:hashlib.sha256(('luna-diverse-v3-order:'+r['id']).encode()).hexdigest())
    sample=[]
    for f in families:sample.extend(rng.sample([r['id'] for r in rows if r['family']==f],2))
    return rows,sample,assignment

if __name__=='__main__':
    if (ROOT/'seeds.json').exists():raise FileExistsError('Curriculum is frozen')
    rows,sample,assignment=make()
    for name,obj in [('seeds.json',rows),('review-selection.json',dict(seed=221022500,ids=sample)),('family-splits.json',assignment)]:
        (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
