import policy,json,hashlib
N=0
def test(s,holds=(),clean=False,signals=()):
 global N
 r=policy.assess(s);got={x['reason'] for x in r['delta_representation_review_holds']};sg={x['reason'] for x in r['delta_review_only_signals']}
 assert set(holds)<=got,(s,got,holds)
 if clean:assert not got,(s,got)
 assert set(signals)<=sg
 assert r['raw_unchanged'] and r['source_SHA256']==r['derivative_SHA256']==hashlib.sha256(s.encode()).hexdigest() and r['omitted_source_bytes']==0
 for f in r['delta_representation_review_holds']+r['delta_review_only_signals']:
  a,b=f['char_start'],f['char_end'];assert s[a:b].encode()==s.encode()[f['byte_start']:f['byte_end']];assert hashlib.sha256(s[a:b].encode()).hexdigest()==f['source_span_SHA256']
 N+=1;return r
# Observed structural classes, synthetic wording; no saved-source pass.
test('Probability\n[latex]P(0\n[latex]x=2[/latex]',holds=['UNBALANCED_LATEX_WRAPPER'])
test('[latex]P(4',holds=['UNBALANCED_LATEX_WRAPPER'])
test('[latex]f(x)=[/latex]',holds=['EMPTY_INTRODUCED_MATH_ENDPOINT'])
test('[latex]P(2.5[/latex]',holds=['EMPTY_INTRODUCED_MATH_ENDPOINT'])
test('The equation has the form:\nwhere a and b are constants.',holds=['EMPTY_INTRODUCED_EQUATION_SLOT'])
test('This formula takes the form:\nwhere c is the intercept.',holds=['EMPTY_INTRODUCED_EQUATION_SLOT'])
test('Section 5.5: Chapter Five Self-Test\nIt is a good idea to test your knowledge after you have completed each chapter. This section presents a Self-Test for Chapter Five. Please complete the test now to assess your learning of the ideas inside this chapter.',holds=['EMPTY_REQUIRED_ASSESSMENT_SLOT'])
test('Self Check: Revenue\nAnswer the question(s) below to see how well you understand the topics covered in the previous section. This short quiz does not count toward your grade in the class, and you can retake it an unlimited number of times.',holds=['EMPTY_REQUIRED_ASSESSMENT_SLOT'])
# Complete math and inequalities, domain notation and plain code examples survive.
for s in ['[latex]P(0<x<2)=0.1[/latex]','[latex]f(x)=1/20[/latex]','[latex]x=2[/latex]','[latex]\\frac{a}{b}[/latex]','The equation has the form:\ny=a+bx\nwhere a and b are constants.','The equation has the form y=a+bx, where a is the intercept.','[latex]\\mathrm{ii^6_5}[/latex]','Use x<=2 and P(0<x<2).','A valid table\n| x | y |\n| 1 | 2 |','`[latex]P(0` is a literal markup example.','```text\n[latex]P(4\n```\nProse survives.','~~~\n[latex]f(x)=\n~~~']:
 test(s,clean=True)
# No item deletion: unknown/real assessment content prevents empty-slot hold.
for s in ['Self-Test\nWhat is 2+2?\nAnswer: 4.','Self Check: Revenue\nAnswer the question(s) below to see how well you understand the topics covered in the previous section.\n1. Find profit at price 3 and cost 2.','Knowledge Check\nRead the linked self-test PDF.','Knowledge Check\nNo questions are required in this optional reflection.','Self-Test\nPlease complete the test now to assess your learning of the ideas inside this chapter.\nThe activity is in the accompanying workbook.','Knowledge Check\nSelect all correct statements: A. x=1 B. x=2','Study Guide\n1. Describe empathy.\n2. Define learning.']:
 test(s,clean=True)
# Media/topic presence is never sufficient to hold.
for s in ['Consider Figure 1; the next paragraph explains the complete result.','A video gives optional examples. The explanation is here.','As you can see from the bolded text in these tables, trust is important.','The numbers that label the points in Figure 1 are ages.','Consider the headshots shown below.','A poem can be a complete authored unit.','Bibliography\nAuthor A. Book (2001).','A chart is not required for this definition.']:
 test(s,clean=True)
test('As you can see from the bolded text in these tables, trust is important.',signals=['NAMED_VISUAL_DEPENDENCY_REVIEW'])
test('Knowledge Check\nWhat is 2+2?',signals=['ASSESSMENT_DEPENDENCY_REVIEW'])
test('Unicode é🙂\n[latex]P(0',holds=['UNBALANCED_LATEX_WRAPPER'])
test('A literal [latex] token is discussed.',clean=True,signals=['AMBIGUOUS_LITERAL_LATEX_TOKEN'])
# Large/deceptive input bound refuses before findings are allocated en masse.
for s in ['Figure 1\n'*6000,'[latex]'*6000,'x'*(policy.base.MAX_BYTES+1)]:
 try:policy.assess(s)
 except ValueError:N+=1
 else:raise AssertionError('bounded refusal expected')
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'source_body_passes':0,'no_quality_or_admission_assignment':True}))
