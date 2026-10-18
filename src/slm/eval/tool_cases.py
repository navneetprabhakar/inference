"""Seven protected synthetic local-tool scenarios, not a reviewed capability suite."""
from copy import deepcopy


def tool_cases():
    values=[
        ('arithmetic','For a synthetic order, multiply 1250 minor units per cup by 2 cups.',
         {'kind':'call','id':'c1','name':'arithmetic','arguments':{'operation':'multiply','left':1250,'right':2}},
         {'value':2500},{'total_minor':2500},'The synthetic total is 2500 minor units.'),
        ('catalog_search','Search the synthetic catalog for headphones at most 7000 minor units, excluding Acorn. Return at most 3.',
         {'kind':'call','id':'c1','name':'catalog_search','arguments':{'query':'headphones','max_price_minor':7000,'excluded_brands':['Acorn'],'limit':3}},
         None,{'product_ids':['P002']},'P002 meets the synthetic catalog constraints.'),
        ('product_lookup','Look up synthetic product P001 and report its fixture price.',
         {'kind':'call','id':'c1','name':'product_lookup','arguments':{'product_id':'P001'}},None,
         {'product_id':'P001','fixture_price_minor':4500},'P001 has a fixture price of 4500 minor units.'),
        ('product_compare','Compare fixture products P001 and P002, in that order. Which has the lower fixture price?',
         {'kind':'call','id':'c1','name':'product_compare','arguments':{'product_ids':['P001','P002']}},None,
         {'lower_fixture_price_product_id':'P001'},'P001 has the lower synthetic fixture price.'),
        ('document_lookup','Read fixture document D001 and report its returns window and receipt requirement.',
         {'kind':'call','id':'c1','name':'document_lookup','arguments':{'document_id':'D001'}},None,
         {'return_days':14,'receipt_required':True},'The fixture allows returns within 14 days with a receipt.'),
        ('no_tool','The supplied color is blue. Repeat it without calling a tool.',{'kind':'answer','text':'Blue.','facts':{'color':'blue'}},None,{'color':'blue'},'Blue.'),
        ('clarification','Each synthetic ticket costs 1250 minor units. Find the total, but do not guess the quantity.',
         {'kind':'clarify','question':'How many tickets?','missing':['quantity']},None,None,None)]
    def product(id,title,brand,price):
        return {'product_id':id,'title':title,'brand':brand,'category':'audio','fixture_price_minor':price,
            'currency':'fixture_minor_units','source':'synthetic_catalog_v1'}
    # Independent explicit fixtures, never obtained by executing the tool under test.
    p1=product('P001','Quiet headphones','Acorn',4500);p2=product('P002','Travel headphones','Birch',6500)
    expected_data={'arithmetic':{'value':2500},'catalog_search':{'products':[p2]},'product_lookup':{'product':p1},
        'product_compare':{'products':[p1,p2]},'document_lookup':{'document_id':'D001',
            'body':'Fixture returns window: 14 days with a receipt.','source':'synthetic_documents_v1'}}
    cases=[]
    for name,prompt,action,result,facts,text in values:
        final=deepcopy(action) if action['kind']!='call' else {'kind':'answer','text':text,'facts':facts}
        cases.append({'scenario_id':'eval-tools-v1/'+name,'family_id':'eval-tools-v1/'+name,'split':'test','scope':'Unreviewed synthetic executable control',
            'history':[{'role':'user','content':prompt}],'expected_action':action,'expected_tool_data':deepcopy(expected_data.get(name)),'expected_final':final})
    return cases
