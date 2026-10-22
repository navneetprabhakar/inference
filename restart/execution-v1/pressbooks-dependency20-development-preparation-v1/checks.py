import select_core as c,json,copy,hashlib,zlib
N=[]
def receipt(reason):return {'structural':{'prior_v2':{'prior_v1':{'reasons':[],'context_only_diagnostics':[{'reason':reason}]},'delta_representation_review_holds':[],'delta_review_only_signals':[]},'delta_representation_review_holds':[],'pending_dependency_queue':[]},'component_ancestry_review':{'flags':[]}}
r={'language_pass':1,'explicit_known_hold':0,'generic_mask':0,'queue_mask':1}
for reason,k in [('SOURCE_MATH_MARKUP_PRESERVED','A_MATH_ONLY'),('FIGURE_REFERENCE_CONTEXT','B_FIGURE_ONLY')]:assert c.stratum(r,receipt(reason))==k;N.append(k)
for reason in ['NAMED_VISUAL_DEPENDENCY_REVIEW','NAMED_MEDIA_COMPARISON_OR_REQUIRED_CONTEXT_REVIEW','INTRODUCED_EMPTY_MATH_AFTER_LATEX_REMOVAL','EMPTY_ASSESSMENT']:
 assert c.stratum(r,receipt(reason)) is None;N.append('required_or_unknown_'+reason)
x=receipt('FIGURE_REFERENCE_CONTEXT');x['structural']['pending_dependency_queue']=[{'reason':'POSSIBLE_COMPONENT_HEADING'}];assert c.stratum(r,x) is None;N.append('mixed_dependency_not_figureonly')
x=receipt('SOURCE_MATH_MARKUP_PRESERVED');x['component_ancestry_review']['flags']=[{'kind':'NC'}];assert c.stratum(r,x) is None;N.append('component_notice_separate_exclusion')
for key,value in [('language_pass',0),('explicit_known_hold',1),('generic_mask',1),('queue_mask',5)]:assert c.stratum({**r,key:value},receipt('SOURCE_MATH_MARKUP_PRESERVED')) is None;N.append(key+'_refusal')
rows=[{'text_SHA256':hashlib.sha256((k+str(i)).encode()).hexdigest(),'stratum':k} for k in c.SETS for i in range(12)];a=c.select(rows);assert len(a)==20 and c.select(list(reversed(rows)))==a;N.append('deterministic_order_invariant_twostratum10')
try:c.select(rows+[rows[0]])
except ValueError:N.append('duplicate_hash_refusal')
else:raise AssertionError()
try:c.select(rows[:9])
except ValueError:N.append('small_population_no_replacements')
else:raise AssertionError()
raw=json.dumps(receipt('SOURCE_MATH_MARKUP_PRESERVED')).encode();p=zlib.compress(raw);assert c.decode(p,hashlib.sha256(p).digest(),hashlib.sha256(raw).digest(),len(raw));N.append('lossless_receipt_hash_roundtrip')
try:c.decode(p+b'extra',hashlib.sha256(p+b'extra').digest(),hashlib.sha256(raw).digest(),len(raw))
except ValueError:N.append('compressed_trailing_refusal')
else:raise AssertionError()
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(N),'names':N,'actual_draws':0,'body_reads':0},indent=2))
