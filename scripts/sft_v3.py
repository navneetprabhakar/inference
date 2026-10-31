"""V3 data contracts and case-local executable fixtures; no network or trainer."""
import hashlib,json,re
import numpy as np
from sft_common import *
DESCRIPTIONS={'calculate':'Apply the chosen arithmetic operation to a then b.','convert':'Convert a length between units.','get_weather':'Fetch weather for the specified city.','lookup_item':'Fetch price and stock by exact product ID.','search_notes':'Find the saved note for a query.'}
ERROR_ANSWERS={'division by zero':'Division by zero is undefined. Please provide a nonzero divisor.','not found':'No matching item was found. Please check the identifier.','timeout':'The tool timed out. Please try again later.','empty result':'No matching notes were found. Please try another query.','invalid unit':'That unit is unsupported. Please use m, km, or cm.'}
SLOT_ANSWERS={
 'a':['What is the first number?','Please provide the first operand.'],
 'b':['What is the second number?','Please provide the second operand.'],
 'op':['Which operation should I use?','Should I add, subtract, multiply, or divide?'],
 'value':['What length should I convert?','Please provide the measurement value.'],
 'from_unit':['What is the original unit?','Which unit is the measurement in?'],
 'to_unit':['Which target unit should I use?','What unit should I convert to?'],
 'city':['Which city should I check?','Please specify the city.'],
 'item_id':['What is the item ID?','Please provide the product identifier.'],
 'query':['What should I search for?','Please provide the search query.']}
def msg(role,content):return {'role':role,'content':content}
def h(x):return hashlib.sha256(x.encode()).hexdigest()
def schema_prompt(aliases,names=None):
 names=names or list(SCHEMAS)
 schemas={aliases.get(n,n):{'description':DESCRIPTIONS[n],'arguments':SCHEMAS[n]} for n in names}
 return 'Answer briefly. Use tools only when needed; ask for missing arguments. Use returned values exactly. Tools: '+json.dumps(schemas,separators=(',',':'))+'. Calls: '+CALL+' then JSON with name and arguments.'
def canonical_call(rec,call):
 return {'name':rec.get('aliases',{}).get(call['name'],call['name']),'arguments':call['arguments']}
def valid_call(rec,call):
 canonical=canonical_call(rec,call)
 if call['name'] not in rec.get('available_tools',list(SCHEMAS)):raise ValueError('Tool not offered')
 execute(canonical)
 return canonical

def run_fixture(rec,call,step):
 canonical=valid_call(rec,call)
 # Fixture output can vary independently of the request; only matching requests
 # receive that case's recorded external result. Wrong calls never receive gold.
 if step<len(rec.get('calls',[])) and call==rec['calls'][step]:return rec['results'][step]
 return execute(canonical)

def answer_for(rec,call,result):
 if 'error' in result:return ERROR_ANSWERS[result['error']]
 return result_answer(canonical_call(rec,call),result)
def encode_record(tok,rec):
 if rec.get('objective')=='causal_lm':
  ids=np.array(rec['tokens'],np.int32);assert ids.shape==(513,)
  return ids,np.ones(512,np.float32),513
 encoded=encode_episode(tok,rec['episode'])
 if encoded is not None and rec.get('objective')=='final_assistant_only':
  ids,mask,n=encoded;mask=mask.copy();prefix=len(tok.encode(render(rec['episode'][:-1])).ids);mask[:prefix]=0
  return ids,mask,n
 return encoded
def exact_answer(text,reference):return ' '.join(text.casefold().split())==' '.join(reference.casefold().split())
def accepted_answer(text,rec):return any(exact_answer(text,x) for x in rec.get('accepted_answers',[rec['expected_answer']]))
def numbers(text):return re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?!\w)',text)
def compare_call(rec,pred,expected):
 try:valid_call(rec,pred);valid=True
 except (ValueError,TypeError,KeyError,ZeroDivisionError):valid=False
 fields={k:type(pred.get('arguments',{})) is dict and k in pred['arguments'] and type(pred['arguments'][k]) is not bool and pred['arguments'][k]==v for k,v in expected['arguments'].items()}
 return {'schema_valid':valid,'name_exact':pred.get('name')==expected['name'],'argument_exact':fields,'call_exact':valid and pred==expected}
