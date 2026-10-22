"""Synthetic planner and actual tiny20-engine controls. Never retained body application."""
import tempfile,json,copy
from pathlib import Path
import segment,engine,custody
N=[]
def test(name,text,predicate):
 b=text.encode();prefix='PG café\n'.encode();raw=prefix+b+b'PG footer';e={'start_byte':len(prefix),'end_byte':len(prefix)+len(b),'bytes':len(b),'SHA256':segment.sha(b)};x=segment.discover(raw,e,1)
 assert b''.join(raw[p['start_byte']:p['end_byte']] for p in x['parts'])==raw
 assert x['parts'][-1]['end_character']==len(raw.decode()) and all(u['semantic_completeness']=='UNASSESSED' for u in x['units'])
 assert x['all_lexical_roles_accounted'] and x['source_bytes_rewritten']==0
 assert predicate(x),name
 N.append(name);return raw,e,x
chap=lambda n,t:f'CHAPTER {n}\n{t}\n'
base=chap('I','First complete café story.')+chap('II','Last complete story.')
test('plain canonical old source inverse',base,lambda x:not x['whole_envelope_fallback'])
test('authored prefix retained explicitreviewunit','An authored opening before chapters.\n'+base,lambda x:any(u['structural_status'].startswith('PREFIX') for u in x['units']))
test('same line uppercase chapter title','CHAPTER ONE. THE HERO\nFirst story.\nCHAPTER TWO. THE RETURN\nLast story.\n',lambda x:not x['whole_envelope_fallback'])
test('lowercase prose reference not unsupported heading',base+'chapter, verse for verse is ordinary prose.\n',lambda x:not x['whole_envelope_fallback'])
test('unresolved lowercase titled heading fallback','CHAPTER I. A mixed title\nFirst\nCHAPTER II.\nSecond\n',lambda x:x['whole_envelope_fallback'])
test('unknown spelling fallback','CHAPTER ELEVENTY\nFirst\n'+base,lambda x:x['whole_envelope_fallback'])
test('bare Roman blankdelimited scopedbody','I\nFirst story.\n\nII\nSecond story.\n',lambda x:not x['whole_envelope_fallback'])
test('bare numeral without blank fallback','Prose\nI\nFirst story.\n\nII\nSecond story.\n',lambda x:x['whole_envelope_fallback'])
test('print year preserved neverchosenbody','MCMVI\n\nI\nFirst story.\n\nII\nSecond story.\n',lambda x:not x['whole_envelope_fallback'] and any(e['resolved_role'].startswith('PREFIX_PRINT_YEAR') for e in x['lexical_role_reconciliation']))
test('Roman pronoun prefix notheading','I. So I was picked up here.\n'+base,lambda x:not x['whole_envelope_fallback'])
test('M Verneuil notheading',base+'M. Verneuil spoke.\n',lambda x:not x['whole_envelope_fallback'])
test('letter labels require retained FROMTOcontext','I\nFROM ALICE TO BOB\nDear Bob, first.\n\nII\nFROM BOB TO ALICE\nDear Alice, reply.\n',lambda x:not x['whole_envelope_fallback'] and all(u.get('boundary_role')=='numbered_letter_candidate' for u in x['units'] if u['structural_status'].startswith('ORDERED')))
test('mixed letter and bare remainsfallback','I\nFROM ALICE TO BOB\nFirst.\n\nII\nPlain second.\n',lambda x:x['whole_envelope_fallback'])
test('explicit dense TOC reconciled allentries','CONTENTS\nCHAPTER I\nCHAPTER II\n\n'+base,lambda x:not x['whole_envelope_fallback'] and len(x['contents_role_candidates'])==1)
test('unanchored duplicate sequence neverpickslast',base+base,lambda x:x['whole_envelope_fallback'])
test('missing chapter fallback',chap('I','First')+chap('III','Third'),lambda x:x['whole_envelope_fallback'])
test('invalid Roman fallback',chap('IIII','Bad')+chap('II','Two'),lambda x:x['whole_envelope_fallback'])
test('mixed number styles fallback',chap('I','First')+chap('2','Second'),lambda x:x['whole_envelope_fallback'])
test('Book scope resets reconciled','BOOK I\nEpigraph one.\n'+base+'BOOK II\nEpigraph two.\n'+base,lambda x:not x['whole_envelope_fallback'] and [u['hierarchy_scope']['number'] for u in x['units'] if u['structural_status'].startswith('ORDERED')]==[1,1,2,2])
test('Volume ordinal scopes reconciled','VOLUME THE FIRST.\n'+base+'END OF THE FIRST VOLUME\nPRINTED BY EXAMPLE\nVOLUME THE SECOND.\n'+base+'END OF THE SECOND VOLUME\nTail.\n',lambda x:not x['whole_envelope_fallback'])
test('scope mismatch fallback','VOLUME I\n'+base+'END OF THE SECOND VOLUME\n',lambda x:x['whole_envelope_fallback'])
test('scope missing numeral fallback','BOOK II\n'+base,lambda x:x['whole_envelope_fallback'])
test('scope repeated fallback','BOOK I\n'+base+'BOOK I\n'+base,lambda x:x['whole_envelope_fallback'])
test('mixed hierarchy types fallback','BOOK I\n'+base+'VOLUME II\n'+base,lambda x:x['whole_envelope_fallback'])
test('scope withoutbody fallback','BOOK I\n'+base+'BOOK II\n',lambda x:x['whole_envelope_fallback'])
test('typed volume lasttail preserved neverdropped',base+'END OF THE FIRST VOLUME\nPRINTED BY EXAMPLE\nNOTES\n[1] Note retained.\n',lambda x:not x['whole_envelope_fallback'] and x['parts'][-2]['role']=='typed_or_unclassified_tail_all_bytes_preserved')
test('notes correction locator typed notbodypoison',base+'THE END\nNOTES\nchapter 8: =bad= replaced by =good=\n',lambda x:not x['whole_envelope_fallback'])
test('ambiguous correction inbody fallback','CHAPTER I\nText\nCHAPTER iii. This is ambiguous.\nCHAPTER II\nText\n',lambda x:x['whole_envelope_fallback'])
test('multiple endings remainfallback',base+'THE END\nTail\nTHE END\n',lambda x:x['whole_envelope_fallback'])
test('no chapters wholework fallback','Christmas day. [Illustration: poem] Original story.',lambda x:x['whole_envelope_fallback'])
test('transcriber braces neverstripped','{Transcribed by Example}\n'+base,lambda x:x['source_bytes_rewritten']==0)
test('empty intervals fallback','CHAPTER I\nCHAPTER II\nText\n',lambda x:x['whole_envelope_fallback'])
r,e,x=test('CRLF Unicode fullinverse',base.replace('\n','\r\n'),lambda x:not x['whole_envelope_fallback'])
test('unconfirmed contents restart cannot selectcleansequence','CONTENTS\nCHAPTER I\nCHAPTER II\nCHAPTER I\nCHAPTER II\n',lambda x:x['whole_envelope_fallback'])
test('dense TOC pagelocators neverbody','CONTENTS\nI. First .... 1\nII. Last .... 8\n',lambda x:x['whole_envelope_fallback'])
test('notes always bind current unitIDs',base+'THE END\nNOTES\n[1] Source note.\n',lambda x:all(set(n['overlapping_unit_IDs'])<=set(u['unit_ID'] for u in x['units']) for n in x['note_dependency_hints']))

test('legacy long title hint cannot vanish',chap('I','First.')+'CHAPTER III. '+('TITLE '*40)+'\n'+chap('II','Second.'),lambda x:x['whole_envelope_fallback'] and x['unmatched_legacy_hints_explicitly_accounted']==1)
test('legacy standalone CHAPTER inbody remainsunknown',chap('I','First.')+'CHAPTER\nMore prose.\n'+chap('II','Second.'),lambda x:x['whole_envelope_fallback'])
test('legacy standalone CHAPTER TOCheader explicitlypreserved','CONTENTS\nCHAPTER\nCHAPTER I\nCHAPTER II\n\n'+base,lambda x:not x['whole_envelope_fallback'] and any(e.get('legacy_hint_retained') and e['resolved_role']=='EXPLICIT_DENSE_CONTENTS_PRESERVED' for e in x['lexical_role_reconciliation']))
test('unknown body structuralheading remainsfallback',chap('I','First.')+'EPILOGUE\nExtra authored content.\n'+chap('II','Second.'),lambda x:x['whole_envelope_fallback'])
test('legacy prefix structure preserved without proseclearance','LIST OF ILLUSTRATIONS\nSome entries retained.\n'+base,lambda x:not x['whole_envelope_fallback'] and any(e['resolved_role']=='PREFIX_STRUCTURAL_CONTEXT_PRESERVED_UNRESOLVED' for e in x['lexical_role_reconciliation']))

test('legacy byte160 hint Unicode endpoint remainsfulloriginalrole',chap('I','First.')+'CHAPTER III. '+('É'*200)+'\n'+chap('II','Second.'),lambda x:x['whole_envelope_fallback'] and all(e.get('source_end_character',0)>=e.get('source_start_character',0) for e in x['lexical_role_reconciliation']))
# Actual new engine across20 synthetic sources, preserving complete outcome ledger.
with tempfile.TemporaryDirectory() as z:
 root=Path(z);out=root/'out';out.mkdir();rows=[];files=[];envs=[]
 for i in range(20):
  p=root/f'{i}.txt';p.write_bytes(r);rows.append({'ordinal':i,'ebook_ID':i+1});files.append({'path':p.name,'bytes':len(r),'SHA256':segment.sha(r),'dev_ino_size_mtime_ns_ctime_ns':custody.identity(p.stat())});envs.append(e)
 p={'source_output':str(root),'records':rows,'source_files':files,'envelopes':envs,'expected_selected_raw_bytes':20*len(r),'expected_selected_envelope_bytes':20*e['bytes'],'related_work_overlay':{'SHA256':'synthetic'},'prior_v1_output':'synthetic'}
 result=engine.run(p,out,lambda *a:None);assert result['stats']['books']==20 and result['stats']['chapter_candidate_units']==40;assert len((out/'records.jsonl').read_text().splitlines())==20;N.append('actual new20synthetic sourceengine allrows no sourceapplication')
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(N),'names':N,'retained_source_applications':0},indent=2))
