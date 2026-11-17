import datetime,hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent;raw=D/'raw/exposed_fit-00000000.json';j=json.loads(raw.read_text())
reasons={
'apology':'Invalid unfinished frame; repeats the request and generic thanks instead of a clean brief apology.',
'sign':'Invalid frame and repeated claims of not understanding; no usable garden-gate sign.',
'unknown_attachment':'Invalid frame; unrelated repeated discussion of generating a tool list rather than requesting the missing document.',
'tone':'Invalid frame; repetitive unrelated server clarification, not a kinder rewrite.',
'packing':'Invalid frame; repeated dog-related uncertainty, not two rainy-walk items.',
'uncertain_cause':'Invalid frame; repeats the asserted cause and invents a disconnected printer instead of expressing uncertainty.',
'clarify_reference':'Invalid frame; invents a code/website task and repeats it rather than asking for the missing text.',
'two_options':'Invalid frame; repeated uncertainty about children, no two quiet activities.',
'plain_language':'A relevant backup definition appears, but repeats many times and never completes a valid frame; one-sentence constraint fails.',
'refuse_invention':'Invalid frame; fabricates an unlabeled customer testimonial and repeats the request.',
'topic_switch':'Invalid frame; repeats I am a kite rather than providing a short story title.',
'concision':'Invalid frame; a long repetitive software-specific explanation violates the one-sentence request.',
'limited_summary':'Invalid unfinished frame; repeats the two supplied facts rather than a bounded summary.',
'list_constraint':'Invalid frame; repetitive shape tautology, not three comma-separated shapes.',
'source_bound':'Invalid frame; repeats the question without explaining that nine was not supplied.',
'correction_ack':'Invalid frame; repeats uncertainty about delayed instead of making the requested correction.',
'question_missing_input':'Invalid frame; invents unrelated server advice despite no designs being supplied.',
'natural_stop':'Invalid frame; invents a student identity and repeats an unrelated theory-of-computation narrative.',
'locker_assignment':'Invalid frame; repeats supplied assignments and questions instead of a clean answer naming Kiran.',
'appointment_state':'Invalid frame; adds an unsupported date and repeats a contradictory no-class statement.',
'negation':'Invalid frame; repeatedly invents Jason instead of answering letters.',
'pronoun':'Lata is initially named correctly, but the response loops through the prompt and never completes a valid action.',
'role_change':'Invalid frame; answers Yusuf taking notes rather than Pia presenting and repeats the roles.',
'status_sequence':'Invalid frame; loops through the supplied transition instead of stating the current on state.'}
assert len(j['records'])==72 and len(reasons)==24
records=[]
for r in j['records']:
 assert r['result']['status']=='error' and not r['result']['broker_trace']
 if r['turn']==0:
  assert r['result']['error_code']=='invalid_model_action';reason=reasons[r['session']]
 else:
  assert r['result']['error_code']=='session_blocked' and not r['decoded_actions'];reason='Follow-up blocked after the invalid opening action; no answer was generated. Counted as failure in the full denominator.'
 records.append({'session':r['session'],'turn':r['turn'],'pass':False,'reason':reason})
out={'reviewer':'Codex; full same-agent per-turn review, not independent release review','reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'checkpoint_manifest_sha256':j['checkpoint_manifest_sha256'],'records':records}
p=D/'reviews/exposed_fit-00000000.review.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n')
print('Reviewed all 72 baseline records: 24 invalid opening actions, 48 blocked follow-ups; zero passes.')
