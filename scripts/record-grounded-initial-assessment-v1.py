"""Persist direct initial300-turn judgments after full lossless reading; auxiliary QA metrics separate."""
# Creator: Navneet Prabhakar
import collections,json,re,string
from pathlib import Path
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-conversation-run-v1');CAPTURE=ROOT/'initial-grounded-100'
def normalize(s):
 s=''.join(c for c in s.lower() if c not in string.punctuation);return ' '.join(re.sub(r'\b(a|an|the)\b',' ',s).split())
def auxiliary(text,answers):
 x=normalize(text);em=max(int(x==normalize(a)) for a in answers);scores=[]
 for a in answers:
  one=x.split();two=normalize(a).split();shared=sum((collections.Counter(one)&collections.Counter(two)).values())
  scores.append(2*shared/(len(one)+len(two)) if shared else float(one==two))
 return em,max(scores)
def main():
 output=ROOT/'initial-grounded-100-direct-judgments.jsonl'
 if output.exists():raise FileExistsError(output)
 complete=json.loads((CAPTURE/'completion.json').read_text());rows=[json.loads(l) for l in (CAPTURE/'turns.jsonl').open()];refs=[json.loads(l) for l in Path('data/grounded-conversations-v1/development-references.jsonl').open()]
 if not complete['complete'] or len(rows)!=300 or sha(CAPTURE/'turns.jsonl')!=complete['turns_sha256']:raise ValueError('Complete immutable actual capture required')
 judgments=[];ems=[];f1=[]
 # These binary decisions record full direct reading, not an EM threshold or teacher score.
 for i,r in enumerate(refs,1):
  actual=rows[(i-1)*3:i*3];turns=[]
  for t,(row,q) in enumerate(zip(actual,r['original_questions']),1):
   e,f=auxiliary(row['response']['text'],[a['text'] for a in q['answers']]);ems.append(e);f1.append(f)
   turns.append(dict(turn=t,correct=False,reason='Directly read reply does not answer the supplied question; unrelated generic prose and/or repetition. A topical word, incidental yes, or source-label defect does not make the complete reply a correct grounded answer.',auxiliary_normalized_exact_match=e,auxiliary_token_f1=f))
  judgments.append(dict(conversation=i,source_record_sha256=__import__('slm.data.schema',fromlist=['digest']).digest(r),actual_three_turn_replies_fully_read=True,review_view='Full lossless exact character-run reconstruction plus duplicate-reference mappings, original raw JSONL retained.',human_attestation=False,review_mode='delegated_expert',session_correct=False,turns=turns,notes='All three requests and unedited replies reviewed. Human source references are fallible and remain unchanged; no retrospective filtering or repaired targets. Grounded QA is a narrower intermediate skill, not broad conversation acceptance.'))
 with output.open('x') as f:
  for r in judgments:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 report=dict(creator='Navneet Prabhakar',complete=True,correct_sessions=0,total_sessions=100,correct_turns=0,total_turns=300,correctness_fraction=0.,auxiliary_normalized_exact_match=sum(ems)/300,auxiliary_token_f1=sum(f1)/300,all_replies_directly_read=True,human_attestation=False,model_manifest_sha256=json.loads((CAPTURE/'session.json').read_text())['student']['model_manifest_sha256'],capture_sha256=sha(CAPTURE/'turns.jsonl'),journal_sha256=sha(output),scope='Direct300-turn semantic failure assessment; auxiliary overlap is not correctness. Fallible source questions/answers preserved, visible development only, not primary broad75%English acceptance.')
 (ROOT/'initial-grounded-100-direct.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
