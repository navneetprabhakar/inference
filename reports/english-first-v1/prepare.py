"""Separate diagnostic packet, not training admission; frozen source left untouched."""
import sys,json,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from development_source import SCENARIOS
from cloud_training.nano_chat_format import encode_conversation,training_example
from cloud_training.nano_quality import validate_suite
from cloud_training.nano_qualification_schedule import restart_branches
from nanochat.tokenizer import RustBPETokenizer
P=Path(__file__).parent;T=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
if (P/'packet-freeze.json').exists():raise SystemExit('Frozen diagnostic packet: create a new version')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=ROOT/'reports/corrective-corpus-v1/train.jsonl'
wanted='apology sign unknown_attachment tone packing uncertain_cause clarify_reference two_options plain_language refuse_invention topic_switch concision limited_summary list_constraint source_bound correction_ack question_missing_input natural_stop locker_assignment appointment_state negation pronoun role_change status_sequence'.split()
train=[json.loads(x) for x in source.read_text().splitlines() if json.loads(x)['id'] in wanted];assert len(train)==24
# Preserve all original text, policies, IDs and provenance in derived diagnostic.
(P/'fit-train.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in train))
sessions=[];dev=[]
for i,(ident,family,turns) in enumerate(SCENARIOS):
 row={'id':'english_dev_'+ident,'family':family,'messages':[],'policies':[],'provenance':{'kind':'interactive_codex_authored','source_group':'english_dev_'+ident,'split':'development','training_admitted':False}}
 specs=[]
 for j,(u,a) in enumerate(turns):
  policy={'permit_calls':(i+j)%2==0,'allowed_names':['calculate','convert'] if (i+j)%2==0 else []}
  row['messages'].extend([{'role':'user','content':u},{'role':'assistant','content':a}]);row['policies'].append(policy)
  specs.append({'user':u,'policy':policy,'reference_answer':a,'expected_calls':[],'reply_budget':192,'rubric':'Judge meaning, not exact wording. Relevant natural English; preserve stated preferences and current state; no invented facts/actions, gratuitous tasks or tools; honor requested scope; clean assistant end. Equivalent useful answers are acceptable. Grade against actual prior model replies when referring back to them.'})
 sessions.append({'id':row['id'],'source_group':row['id'],'category':family,'turns':specs});dev.append(row)
suite={'schema':1,'purpose':'development_only_never_train','required_context_tokens':2048,'sessions':sessions};validate_suite(suite)
(P/'development-suite.json').write_text(json.dumps(suite,ensure_ascii=False,indent=2)+'\n')
(P/'development-reference.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in dev))
review=[];stats={};prompts={}
for split,rows in [('fit_train',train),('development',dev)]:
 mass=collections.Counter();lengths=[];prefixes=0;prompts[split]=set()
 for r in rows:
  enc=encode_conversation(T,r['messages'],policies=r['policies'],context=2048)
  targets=training_example(enc)['assistant_target_count'];mass[r['family']]+=targets;lengths.append(len(enc['ids']))
  users=0
  for k,m in enumerate(r['messages']):
   if m['role']=='user':users+=1;prompts[split].add(' '.join(m['content'].lower().split()))
   else:
    prefix=encode_conversation(T,r['messages'][:k],policies=r['policies'][:users],for_generation=True,context=2048,reply_budget=192)
    assert prefix['ids']==enc['ids'][:len(prefix['ids'])];prefixes+=1
  for span in enc['spans']:
   if span['kind']=='assistant_end':assert all(enc['mask'][span['start']:span['end']])
   if span['kind'] in ['user_prompt','user_start','assistant_start']:assert not any(enc['mask'][span['start']:span['end']])
  review.append({'id':r['id'],'split':split,'turns_reviewed':users,'row_sha256':hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'review':'All references manually read for request alignment, current state, unsupported claims, natural English and completion. Semantic equivalents allowed.','pass':True})
 stats[split]={'sessions':len(rows),'turns':prefixes,'assistant_targets':sum(mass.values()),'target_mass_by_family':dict(mass),'max_framed_tokens':max(lengths),'prefix_checks':prefixes}
assert not prompts['fit_train']&prompts['development']
# Check new prompts against historical train/dev, never load sealed release.
oldprompts=set()
for name in ('train.jsonl','validation.jsonl'):
 for line in (source.parent/name).read_text().splitlines():
  oldprompts.update(' '.join(m['content'].lower().split()) for m in json.loads(line)['messages'] if m['role']=='user')
assert not oldprompts&prompts['development']
result={'status':'diagnostic_data_checked_not_training_admission','source_sha256':sha(source),'source_review_sha256':sha(source.parent/'semantic-review.json'),'context_tokens':2048,'stats':stats,'reviewer':'Codex author plus second semantic pass; not independent reviewer','records':review,'split_checks':{'exact_prompt_overlap':0,'new_scenario_groups':True,'semantic_skill_overlap_expected':True,'release_opened':False},'limits':['Tiny fit packet tests memorization/learnability, not general conversation coverage.','12 author-written dev scenarios are an initial transfer diagnostic, not a release or statistically strong family acceptance set.','Original full training contract still requires tool-call coverage; this English-only packet is deliberately NOT admitted through it.','A separately scoped diagnostic contract/runner is required; existing release gates cannot be relaxed.'],'qualification_branches':restart_branches()}
(P/'data-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(stats,indent=2))
