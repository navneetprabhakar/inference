import sys,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'hansard-question-group-preparation-v1';sys.path.insert(0,str(P));import core
cases=[]
def check(name,s,fn):
 parts=core.segment(s);assert ''.join(p['raw_text'] for p in parts)==s;pos=0
 for p in parts:
  raw=p['raw_text'].encode();assert p['UTF8_start']==pos and p['UTF8_end']==pos+len(raw) and hashlib.sha256(raw).hexdigest()==p['raw_SHA256'];pos+=len(raw);assert 'UNCLEARED' in p['new_group_eligibility']
 assert pos==len(s.encode());fn(parts);cases.append(name)
def groups(p):return [x for x in p if x['kind']=='QUESTION_ANSWER_GROUP']
def need(v):
 if not v:raise AssertionError('expectation')
check('three different attributed questions remain with ONE joint answer; next answer-led transition splits', 'Health: Care\n\nLord Ash: To ask why.\n\nBaroness Birch: To ask when.\n\nLord Cedar asked Her Majesty when.\n\nLord Fir: Three answers — αβ.\n\nHealth: Next\n\nLord Ash: To ask what.\n\nLord Fir: This is complete.\n',lambda p:need([(x['question_turns'],x['answer_turns']) for x in groups(p)]==[(3,1),(1,1)]))
check('unknown orphan and ambiguous header remain exact separate held components', 'Unattributed αβ fragment\n\nUnclear heading\n\nLord Ash: To ask why.\n\nLord Fir: Explained.\n',lambda p:need(any(x['kind']=='HELD_ORPHAN_PREFIX' for x in p) and any(x['kind']=='HELD_AMBIGUOUS_HEADING_OWNERSHIP' for x in p)))
check('attachment/table references retain whole supported explanation without automatic hold','Lord Ash: To ask why.\n\nLord Fir: The method works because the valve closes. Supporting figures are in the attached Excel file.\nYear\tCount\n2020\t4\n',lambda p:need(not groups(p)[0]['holds'] and len(groups(p)[0]['context_flags'])==2))
check('multiple supported answer speakers retained and explicitly held for review','Lord Ash: To ask why.\n\nLord Fir: One explanation.\n\nBaroness Birch: Additional explanation.\n',lambda p:need('MULTIPLE_ANSWER_SPEAKERS_REVIEW' in groups(p)[0]['holds']))
check('unanswered final question remains explicit hold, never omitted','Lord Ash: To ask why.\n\nLord Fir: Explained.\n\nLord Ash: To ask when.\n',lambda p:need(len(groups(p))==2 and 'QUESTION_WITHOUT_SUPPORTED_ANSWER' in groups(p)[1]['holds']))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(cases),'cases':cases,'retained_source_reads':0},indent=2))
