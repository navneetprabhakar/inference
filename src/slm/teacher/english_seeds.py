"""Own fictional training seeds:20template families,182instances, not182independent skills."""
# Creator: Navneet Prabhakar

NAMES = ['Zoya','Nikhil','Pia','Farah','Kabir','Leela','Omar','Tara','Vihaan','Yasmin']
OBJECTS = ['lantern','notebook','scarf','bottle','folder','basket','badge','pencil','jacket','camera']
DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday','Monday','Tuesday','Wednesday']
STYLES = ['professional','casual','terse','humorous','caveman']
GRAMMAR = [
    ('She walk to the library yesterday.','She walked to the library yesterday.'),
    ('Those chair is empty.','Those chairs are empty.'),
    ('We has finished the painting.','We have finished the painting.'),
    ('He do not own a bicycle.','He does not own a bicycle.'),
    ('The children was playing outside.','The children were playing outside.'),
    ('I have saw that film.','I have seen that film.'),
    ('There is three boxes here.','There are three boxes here.'),
    ('They goes home early.','They go home early.'),
    ('Her brother are a musician.','Her brother is a musician.'),
    ('This shoes belong to me.','These shoes belong to me.'),
]
EXPLANATIONS = [
    ('a shadow','A shadow forms when an opaque object blocks light.'),
    ('an echo','An echo is sound reflected from a surface and heard again.'),
    ('evaporation','Evaporation is the change of liquid into gas at its surface.'),
    ('condensation','Condensation is the change of gas into liquid.'),
    ('melting','Melting is the change of a solid into a liquid.'),
    ('friction','Friction is a force that opposes relative motion between touching surfaces.'),
    ('a magnet','A magnet attracts certain materials, including iron.'),
    ('a thermometer','A thermometer measures temperature.'),
    ('a compass','A compass uses a magnetic needle to indicate direction.'),
    ('a seed','A seed can develop into a plant under suitable conditions.'),
]


def case(family, variant):
    n, obj, day = NAMES[variant], OBJECTS[variant], DAYS[variant]
    next_day = DAYS[(variant+2)%len(DAYS)]
    style = STYLES[variant%len(STYLES)]
    task, action = 'conversation', 'answer'
    context = []; facts = {}
    def user(text): context.append(dict(role='user',content=text))
    def assistant(text): context.append(dict(role='assistant',content=text))
    if family == 0:
        style = 'casual'; user('I just moved to a new neighbourhood and feel out of place. Please acknowledge that feeling without giving me a long list of advice.')
        facts = dict(situation='new neighbourhood', feeling='out of place', requested_response='acknowledgment, not a list')
    elif family == 1:
        style = 'professional'; task = 'clarification'; action = 'clarify'
        user('Please help me confirm the planning meeting. I know it is in the west room, but I have not been told the time. Ask for the missing detail politely.')
        facts = dict(known_location='west room', missing_detail='meeting time')
    elif family == 2:
        style = 'terse'; wrong, gold = GRAMMAR[variant]
        user('Fix the grammar and give just the corrected sentence: '+wrong)
        facts = dict(expected_reply=gold)
    elif family == 3:
        style = 'terse'; location = ['attic','drawer','cupboard','shelf','garage','hallway','cabinet','locker','studio','porch'][variant]
        user(f'The {obj} is stored in the {location}. Which storage location is specified? Give its single-word label without explanation.')
        facts = dict(item=obj, expected_reply=location)
    elif family == 4:
        task = 'correction'; user(f'The rehearsal is on {day}.'); assistant(f'The rehearsal is scheduled for {day}.')
        user(f'Update that: the rehearsal has been moved to {next_day}. Confirm the new day briefly.')
        facts = dict(event='rehearsal', superseded_day=day, current_day=next_day)
    elif family == 5:
        user(f'{n} finished the poster. The invitations are still waiting for approval. Summarise what is done and what remains blocked in one sentence.')
        facts = dict(completed='poster', blocked='invitations', blocker='approval')
    elif family == 6:
        user(f'Rephrase this while preserving its meaning: {n} cannot join the walk, but would like a copy of the photographs.')
        facts = dict(person=n, cannot_attend='walk', requested='copy of photographs')
    elif family == 7:
        style = 'professional'; user(f'A colleague suggests distributing the {obj} design before the required review is complete. Disagree politely and propose waiting for the review.')
        facts = dict(item=obj, review_complete=False, requested_action='wait for required review')
    elif family == 8:
        style = 'casual'; user(f'Make this sound friendly and casual: I regret to inform you that I will arrive ten minutes after our agreed time, {n}.')
        facts = dict(recipient=n, arrival_delay_minutes=10)
    elif family == 9:
        style = 'caveman'; user(f'Use caveman style without changing this instruction: Put {variant+2} empty boxes beside the door. Do not move the full boxes.')
        facts = dict(empty_boxes_to_move=variant+2, destination='beside the door', full_boxes_must_not_move=True)
    elif family == 10:
        style = 'humorous'; user(f'I carried a {obj} all morning and left it at home just before I needed it. Give me one gentle playful remark, not a lecture.')
        facts = dict(forgotten_item=obj, tone='gentle, not insulting')
    elif family == 11:
        user(f'Write a short apology to {n}: I borrowed their {obj}, promised to return it yesterday, and will bring it back this evening. Do not invent an excuse.')
        facts = dict(recipient=n, borrowed_item=obj, return_time='this evening', excuse_supplied=False)
    elif family == 12:
        task = 'clarification'; action = 'clarify'
        user(f'{n} asked me to collect the {obj} at six. The pickup place is missing. Ask just for that place.')
        facts = dict(person=n, item=obj, known_time='six', missing_detail='pickup place')
    elif family == 13:
        task = 'correction'; style = 'terse'
        other = NAMES[(variant+1)%10]
        user(f'The {obj} belongs to {n}.'); assistant(f'{n} owns the {obj}.')
        user(f'That ownership information is outdated: {other} now owns it. Identify its current owner with only their name.')
        facts = dict(item=obj, previous_owner=n, expected_reply=other)
    elif family == 14:
        style = 'casual'; topic, supplied = EXPLANATIONS[variant]
        user(f'Explain {topic} in simple everyday English using only this supplied information: {supplied}')
        facts = dict(topic=topic, supplied_information=supplied)
    elif family == 15:
        style = 'terse'; first, second = obj, OBJECTS[(variant+3)%10]
        user(f'From this inventory, return the first two item labels separated by a comma and a space, with no other text: {first}; {second}; rope.')
        facts = dict(expected_reply=f'{first}, {second}')
    elif family == 16:
        style = 'professional'; user(f'Write a brief update: {n} completed the first draft; proofreading remains; the delivery date is {day}. Keep all three facts.')
        facts = dict(owner=n, completed='first draft', remaining='proofreading', delivery_day=day)
    elif family == 17:
        style = 'terse'; gold = f'{variant+3} chairs'
        user(f'There are {variant+5} chairs in a room and two are occupied. State the number of unoccupied chairs as a number followed by the word chairs.')
        facts = dict(total_chairs=variant+5, occupied_chairs=2, expected_reply=gold)
    elif family == 18:
        user(f'Tell me in caveman style that the {obj} delivery will arrive on {day}.')
        assistant(f'{obj.capitalize()} come {day}.')
        user('Switch back to normal English and restate that delivery information in one complete sentence.')
        style = 'professional'; facts = dict(item=obj, arrival_day=day, requested_style='normal English')
    elif family == 19:
        style = 'casual'; user(f'I practised my presentation, but stumbled during the real thing. I feel disappointed. Respond kindly without claiming it was perfect or making promises about the next attempt, {n}.')
        facts = dict(event='presentation', outcome='stumbled', feeling='disappointed', perfection_not_established=True)
    else: raise ValueError('Unregistered English seed family')
    return dict(scenario_id=f'english-f{family:02d}-v{variant:02d}', family_id=f'english-context-family-{family:02d}-v1',
                split='train', task=task, style=style, content_category='sfw', parents=[], context=context,
                facts=facts, expected_action=dict(kind=action,name=None,arguments={}))


def batches():
    return [[case(f,v) for v in (range(1) if f<2 else range(10))] for f in range(20)]
