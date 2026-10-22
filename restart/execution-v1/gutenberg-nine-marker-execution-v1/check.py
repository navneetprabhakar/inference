"""Exact approved boundary transform/inverse controls; no complete derivative run."""
import copy,json
from pathlib import Path
import execute as e
packet=json.loads(e.PACKET.read_text());cases=[]
def test(name,ok):assert ok,name;cases.append(name)
def refuse(fn):
 try:fn()
 except Exception:return True
 return False
for wrapper in packet:
 old=wrapper['exact_wrapper'].encode();operations=[]
 for p in wrapper['precise_presentation_marker_spans_not_authorized_edits']:operations.append({**p,'start_byte':p['start_byte']-wrapper['start_byte'],'end_byte':p['end_byte']-wrapper['start_byte']})
 new,ancestry=e.transform(old,operations);test('exact_internal_preserved_'+str(wrapper['chapter'])+'_'+str(wrapper['start_byte']),new.decode()==wrapper['internal_exact_text'] and len(ancestry)==2)
 bad=copy.deepcopy(operations);bad[0]['SHA256']='0'*64;test('hash_substitution_refused_'+str(wrapper['start_byte']),refuse(lambda:e.transform(old,bad)))
test('unknown_or_unapproved_data_untouched',e.transform(b'/* OTHER keep me */',[])[0]==b'/* OTHER keep me */')
raw=b'abc';op={'start_byte':0,'end_byte':1,'exact_text':'a','SHA256':e.c.sha(b'a')};test('overlap_refused',refuse(lambda:e.transform(raw,[op,op])))
(e.HERE/'checks.json').write_text(json.dumps({'status':'PASS','count':len(cases),'cases':cases,'full_derivative_runs':0},indent=2)+'\n');print(len(cases),'PASS')
