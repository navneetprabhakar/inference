"""Independent synthetic policy review; no corpus reads."""
from pathlib import Path
import importlib.util,json
p=Path(__file__).resolve().parent.parent/'pressbooks-structural-repair-preparation-v2/policy.py'
s=importlib.util.spec_from_file_location('independent_structural',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
checks=[]
def check(n,t,holds,signals=None):
 r=m.assess(t);actual={x['reason'] for x in r['delta_representation_review_holds']};assert actual==set(holds),(n,actual)
 assert r['raw_unchanged'] and r['omitted_source_bytes']==0 and not r['major_corruption_or_quality_verdict_assigned']
 for x in r['delta_representation_review_holds']+r['delta_review_only_signals']:
  import hashlib
  assert t[x['char_start']:x['char_end']].encode()==t.encode()[x['byte_start']:x['byte_end']]
  assert hashlib.sha256(t.encode()[x['byte_start']:x['byte_end']]).hexdigest()==x['source_span_SHA256']
 if signals is not None:assert {x['reason'] for x in r['delta_review_only_signals']}==set(signals)
 checks.append(n)
check('missing_RHS_hold','é [latex]y = [/latex]',['EMPTY_INTRODUCED_MATH_ENDPOINT'])
check('intact_math_not_held','[latex]y = 2x+3[/latex]',[])
check('code_literal_preserved','```text\n[latex]y =\n```',[])
check('empty_required_assessment_hold','Self-Test\nPlease complete the test now to assess your learning of the ideas inside this chapter.',['EMPTY_REQUIRED_ASSESSMENT_SLOT'])
check('actual_question_prevents_empty_assessment','Self-Test\nPlease complete the test now to assess your learning of the ideas inside this chapter.\n1. Why does rain fall?',[])
check('visual_dependency_not_absence_claim','Consider the headshots below.',[],['NAMED_VISUAL_DEPENDENCY_REVIEW'])
check('unmarked_clean_prose_no_hold','This short chapter explains how readers compare two arguments.',[],[])
print(json.dumps({'status':'PASS','independent_controls':len(checks),'controls':checks,'source_body_reads':0},indent=2))
