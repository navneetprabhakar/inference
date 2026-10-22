"""Read-only independent synthetic counterexamples; no real training payloads."""
import copy,hashlib,importlib.util,json,pathlib
D=pathlib.Path(__file__).resolve().parent;SRC=D.parent/'family-validator-preparation-v1/validate.py'
spec=importlib.util.spec_from_file_location('reviewed_family_validator',SRC);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def record(rid,split='train',stage='M2'):
 axes=['source_document','duplicate_component']
 if stage in ['M5','M6','M7']:axes+=['conversation','template','teacher_seed']
 if stage in ['M6','M7']:axes+=['schema','workflow']
 text='Artificial audit marker '+rid
 return {'record_id':rid,'payload_utf8':text,'payload_sha256':m.sha(text.encode()),'source_id':'artificial-source:'+rid,'source_snapshot_sha256':'a'*64,'stage':stage,'split':split,'role':{'train':'training','development':'development','final':'acceptance','quarantine':'excluded'}[split],'ancestry_status':'known','ancestry_evidence':'Artificial fixture; no real source or task data','upstream_role':'unpartitioned','synthetic_generation':True,'required_family_namespaces':axes,'family_keys':[x+':'+rid for x in axes],'parent_record_ids':[]}
def bundle(records):
 b={'records':records,'receipts':{},'protected_family_keys':[],'protected_source_ids':[]}
 for r in records:
  r.pop('admission_receipt_sha256',None);receipt={'record_binding_sha256':m.sha(m.canonical(r)),'artificial_audit_only':True};h=m.sha(m.canonical(receipt));b['receipts'][h]=receipt;r['admission_receipt_sha256']=h
 return b
cases=[]
def check(name,b,expect='accept',note=''):
 try:result=m.validate(b);outcome='accept'
 except m.Refusal as e:outcome='refuse';result={'reason':str(e)}
 assert outcome==expect,(name,outcome,result)
 cases.append({'name':name,'outcome':outcome,'validator_result':result,'interpretation':note,'bundle':b})
# Explicitly present synthetic ancestor can be disclaimed as teacher-inapplicable.
p=record('synthetic-parent');c=record('human-edited-child',stage='M5');c['parent_record_ids']=[p['record_id']];c['family_keys']+=p['family_keys'];c['synthetic_generation']=False
for axis in ['teacher_seed','template']:
 c['required_family_namespaces'].remove(axis);c['family_keys'].remove(axis+':human-edited-child')
c['not_applicable_family_namespaces']={'teacher_seed':'Human edited derivative; no current model call','template':'Free-form human edit, no template'}
check('known_synthetic_M2_ancestor_with_M5_teacher_inapplicable',bundle([p,c]),note='All parent links and parent synthetic_generation=True are present. Child can still mark teacher ancestry inapplicable because rule checks only child direct-generation flag.')
# Whitespace-only family IDs are accepted although required axes appear populated.
a=record('blank-family',stage='M7');a['family_keys']=[k.split(':')[0]+':   ' for k in a['family_keys']]
check('whitespace_only_family_identifiers',bundle([a]),note='The suffix value is whitespace-only. all(k.split(...)) tests truthiness rather than nonempty value.')
# Known protected key differs only in invisible trailing padding.
a=record('protected-padding');a['family_keys']=['source_document:protected-known ','duplicate_component:a'];b=bundle([a]);b['protected_family_keys']=['source_document:protected-known']
check('protected_family_trailing_whitespace_alias',b,note='Malformed padded identifier evades exact protected-key lookup. A stable-ID canonicalization policy should reject padding, not infer arbitrary semantic aliases.')
a=record('protected-exact');a['family_keys']=['source_document:protected-known','duplicate_component:a'];b=bundle([a]);b['protected_family_keys']=['source_document:protected-known']
check('control_exact_protected_key_refuses',b,'refuse')
# M8 permits a tool/conversation record without later-stage axes.
a=record('deploy-A',stage='M8');b=record('deploy-B','final',stage='M8')
check('M8_base_axes_only_cross_split',bundle([a,b]),note='Stage M8 is allowed yet requires only source/duplicate axes. Operational conversation/tool payloads can omit conversation/template/schema/workflow ancestry; scope applicability needs clarification or enforcement.')
# Honest known parent protection still works; do not report a non-bug.
a=record('heldout-parent','final');a['upstream_role']='heldout';c=record('renamed-child');c['parent_record_ids']=[a['record_id']];c['family_keys']+=a['family_keys']
check('control_renamed_protected_parent_cannot_train',bundle([a,c]),'refuse')
# Scope limitation: semantic rename not declared by supplied ancestry cannot be inferred.
a=record('tool-A',stage='M7');b=record('tool-B','final',stage='M7');check('undeclared_semantic_tool_rename',bundle([a,b]),note='No shared key/identity/parent relationship supplied. This acceptance is a declared ancestry-completeness limitation, NOT reported as an implementation bug.')
# Unicode canonical spellings likewise require a declared stable identity contract.
a=record('unicode');a['family_keys']=['source_document:cafe\u0301','duplicate_component:a'];b=bundle([a]);b['protected_family_keys']=['source_document:caf\u00e9'];check('unicode_noncanonical_identity',b,note='NFC vs decomposed string differs. Requires explicit identity normalization rules; report alongside padding rather than semantic alias inference.')
result={'status':'INDEPENDENT_COUNTEREXAMPLES_EXECUTED_READ_ONLY','reviewed_validator_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'cases':cases,'real_payloads_created':0,'existing_sources_modified':False}
(D/'counterexample-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'cases':len(cases),'accepted':[c['name'] for c in cases if c['outcome']=='accept'],'refused_controls':[c['name'] for c in cases if c['outcome']=='refuse']},indent=2))
