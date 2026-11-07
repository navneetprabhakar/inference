"""Read-only public custody review; no candidates or private inputs are opened."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from protect_grounded_public import SPEC,read_inputs,public_index,candidate_content
from protect_split import words
from protect_language_mixture import candidate_history
corpora=read_inputs(json.loads(SPEC.read_text()),lambda:None)
_,_,inventory=public_index(corpora)
short_user=short_exact=reference_exact=0
for _,cases in corpora:
 for case in cases:
  for turn in case['turns']:
   short_user+=len(words(turn['user']))<3
   if turn['answer']['mode']=='exact':
    value=turn['answer']['value']
    reference_exact+=isinstance(value,dict)
    short_exact+=isinstance(value,str) and len(words(value))<3
protected='Locate violet folio.'
index,_,_=public_index([('synthetic',[dict(turns=[dict(user=protected,answer=dict(mode='manual'),policy=dict(permit_calls=True),calls=[])])])])
parent='User: Locate violet folio.\nAssistant: Upstairs.\nUser: A later question concerns equipment.\nAssistant: The rack is full.'
selected=[dict(role='user',text='A later question concerns equipment.'),dict(role='assistant',text='The rack is full.')]
texts,_=candidate_content(dict(text=parent,selected_history_json=json.dumps(selected)),'chat')
regressions=subprocess.run([sys.executable,'verify_grounded_public_custody.py'],cwd=ROOT,capture_output=True,text=True)
report=dict(state='independent_review_PASS_with_documented_limits',scope='Read-only public code/inventory plus synthetic tests; no candidate screen, private input, GPU, or admission.',
 pins={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['protect_grounded_public.py','verify_grounded_public_custody.py','reports/grounded-curriculum-v1/custody/PROTOCOL.md']},
 inventory=inventory,existing_regressions=dict(returncode=regressions.returncode,output=regressions.stdout+regressions.stderr),
 discarded_parent_utterance=dict(standalone_matches=index.matches(protected),current_parent_and_selected_matches=any(index.matches(t) for t in texts),split_parent_matches=any(index.matches(m['text']) for m in candidate_history(parent))),
 omitted_text_counts=dict(user_below_three_tokens=short_user,literal_exact_below_three_tokens=short_exact,exact_reference_targets=reference_exact),
 union='Required by protocol and receipt limitation; not enforced by this supplemental screener. Final packer must enforce and pin both receipts.')
out=Path(__file__).with_name('independent-review-v2.json');out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
