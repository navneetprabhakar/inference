from pathlib import Path
import sys,hashlib,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gutenberg-20-structural-unit-preparation-v1'))
import segment
N=0
def check(body,fall=None):
 global N
 prefix='Original café🙂\r\n';suffix='\r\nOriginal footer';raw=(prefix+body+suffix).encode();a=len(prefix.encode());z=a+len(body.encode());env={'start_byte':a,'end_byte':z,'bytes':z-a,'SHA256':hashlib.sha256(body.encode()).hexdigest()};x=segment.discover(raw,env,42)
 if fall is not None:assert x['whole_envelope_fallback']==fall
 assert b''.join(raw[p['start_byte']:p['end_byte']] for p in x['parts'])==raw
 for p in x['parts']:
  assert p['SHA256']==hashlib.sha256(raw[p['start_byte']:p['end_byte']]).hexdigest();assert raw.decode()[p['start_character']:p['end_character']].encode()==raw[p['start_byte']:p['end_byte']]
 assert all(u['semantic_completeness']=='UNASSESSED' for u in x['units']) and x['notes_front_endmatter_or_editorial_removed']==0
 N+=1;return x
check('CHAPTER 1\r\nComplete café prose.[1]\r\nCHAPTER 2\r\nSecond section.\r\nTHE END\r\n[1] Retained explanatory note.\r\n',False)
check('1. Do this.\n2. Do that.\n',True)
check('CHAPTER I\nOne.\nPART II\nCHAPTER II\nTwo.\n',True)
check('CHAPTER I\nOne.\nCHAPTER II\nTwo.\nCHAPTER I\nAgain.\n',True)
x=check('CHAPTER I\nOne.\nCHAPTER II\nTwo.\nTHE END\nExtra print material\nTHE END\n',False);assert x['units'][-1]['end_byte']==x['envelope']['end_byte']
check('CHAPTER IVVX\nOne.\nCHAPTER II\nTwo.\n',True)
x=check('CHAPTER I\nFirst [Footnote 1: A dependent explanatory component].\nCHAPTER II\nSecond.\n',False);assert len(x['note_dependency_hints'])==1 and not x['note_dependency_hints'][0]['definition_extent_or_reference_resolution_proven']
# An apparent heading inside an annotation remains an UNASSESSED candidate,
# never source-independent extraction or a semantic pass. All wrapper bytes kept.
x=check('[Illustration:\nCHAPTER I\nAn illustration description]\nActual prose.\nCHAPTER II\nLater prose.\n',False);assert x['full_inverse_verified'] and x['unit_boundaries_semantically_complete_proven']==False
print(json.dumps({'status':'PASS_INDEPENDENT_SYNTHETIC_ONLY','controls':N,'source_body_reads':0,'unassessed_annotation_context_limitation_retained':True}))
