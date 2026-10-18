"""Independent structured-fact/action oracle and one executable local mock tool."""


def shape(value):
    if isinstance(value,dict):
        return {'type':'object','properties':{k:shape(v) for k,v in value.items()},
            'required':list(value),'additionalProperties':False}
    if isinstance(value,list):
        if not value:raise ValueError('Empty list needs an explicit element schema')
        return {'type':'array','items':shape(value[0])}
    if value is None:return {'type':'null'}
    if type(value) is bool:return {'type':'boolean'}
    if type(value) is int:return {'type':'integer'}
    if isinstance(value,str):return {'type':'string'}
    raise ValueError('Oracle schema supports exact JSON values, no floating money')


def execute_mock(action):
    if action['kind']!='call':return None
    if action['name']!='multiply_amount':raise ValueError('Unsupported local mock tool')
    args=action['arguments']
    if set(args)!={'unit_price_minor','quantity'} or any(type(v) is not int or v<0 for v in args.values()):
        raise ValueError('Invalid mock tool arguments')
    if args['quantity']>10000 or args['unit_price_minor']>10**12:raise ValueError('Mock bounds exceeded')
    return {'total_minor':args['unit_price_minor']*args['quantity']}


def output_schema(scenario):
    example={'reply':'','facts':scenario['facts'],'action':scenario['expected_action'],
        'tool_result':execute_mock(scenario['expected_action']),
        'style':scenario['style'],'content_category':scenario['content_category']}
    return shape(example)


def validate(scenario,candidate):
    action=candidate['action'];result=None;execution=True
    try:result=execute_mock(action)
    except (ValueError,KeyError,TypeError):execution=False
    # Dict equality alone treats True==1. Compare canonical JSON to preserve exact types.
    from slm.data.schema import digest
    return {'structured_facts_match':digest(candidate['facts'])==digest(scenario['facts']),
        'action_arguments_match':digest(action)==digest(scenario['expected_action']),
        'mock_execution_matches':execution and digest(candidate['tool_result'])==digest(result),
        'control_labels_match':candidate['style']==scenario['style'] and candidate['content_category']==scenario['content_category']}


def fixture_scenario(task='tool_trajectory',style='professional'):
    action={'kind':'call','name':'multiply_amount','arguments':{'unit_price_minor':1250,'quantity':2}}
    if task in ('conversation','clarification','correction','style_pair','student_correction'):
        action={'kind':'clarify' if task=='clarification' else 'answer','name':None,'arguments':{}}
    elif task!='tool_trajectory':raise ValueError('Unknown fixture task')
    context=[{'role':'user','content':'Two cups cost 1250 minor currency units each. Confirm the total; do not change quantity.'}]
    facts={'quantity':2,'unit_price_minor':1250,'currency':'fixture_minor_units'}
    if task=='clarification':
        context=[{'role':'user','content':'Cups cost 1250 minor currency units each. What is my total?'}];facts['quantity']=None
    if task=='correction':
        context=[{'role':'user','content':'Three cups at 1250 minor currency units each.'},
            {'role':'assistant','content':'That is 3750 minor currency units.'},
            {'role':'user','content':'Actually, make that two cups; keep the unit price.'}]
    if task=='student_correction':
        context.extend([{'role':'assistant','content':'That is 5000 minor currency units.'},
            {'role':'user','content':'The arithmetic is wrong. Correct it without changing quantity.'}])
    return {'scenario_id':f'fixture-{task}-{style}','family_id':'fixture-order-total-v1','split':'train',
        'task':task,'style':style,'content_category':'sfw','parents':[],
        'context':context,'facts':facts,'expected_action':action}
