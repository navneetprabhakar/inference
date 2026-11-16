"""Record complete manual reviews separately from scope-only screening."""
import json,hashlib,sys,re,collections
from pathlib import Path
ROOT=Path.cwd();P=Path(__file__).parent;sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'sample.json').read_text())['rows'];f=json.loads((P/'focused-sample.json').read_text())['rows'];h=json.loads((P/'human-focused-sample.json').read_text())['rows']
# Every listed assistant turn was read in full; no automatic semantic grading.
notes={
'B12':['Reject: awkward grammar and grim doll destruction unsuitable for initial friendly curriculum.','Reject: insulting unsupported claims about a real person.','Reject: exaggerated praise and factual assertions; does not repair the source trajectory.'],
'B14':['Hold: long ornate poem is low priority for concise dialogue.','Reject: unnatural wording about pollen growing art.','Pass: asks whether the misspelling means lullaby.'],
'B21':['Pass: requests missing task list.','Reject: invents laundry/store proximity and pickup order without times.','Reject: duplicated numbering and still no feasible time-bound schedule.'],
'B22':['Reject: claims ongoing daily learning and developmental identity.','Reject: offers image inspection unsupported by Own text-only runtime.','Reject: claims image access without an observed image tool result.'],
'F0':['Hold: edit is usable but explanation is excessive.','Reject: wrongly labels The idea is that as a passive construction.','Reject: verbose commentary undermines request for greater concision.'],
'F1':['Hold: fictional antiques persona outside core dialogue.','Hold: expertise claims require factual review.','Reject: vague repeated sales appraisal does not meaningfully resolve the user instruction.'],
'F2':['Pass: corrects who, for a year and affecting; explanation mostly useful though verbose.','Pass: corrects affects, those who have been, and required to retrain.','Pass: supplies a grammatical noun-use example of effects and explains it.'],
'F3':['Hold: fictional police roleplay outside initial curriculum.','Hold: long invented character description.','Hold: theatrical narrative rather than ordinary helpful conversation.'],
'F4':['Reject: embellishes source and implies literal arson rather than preserving ambiguity.','Reject: malformed explanatory sentence beginning Additionally I changed.','Reject: calls having been utilized a past-perfect participle form; misleading grammar lesson.'],
'F5':['Reject: broken quotation and claims to break up text while retaining one sentence.','Reject: falsely treats Over many years as implying ongoing process.','Reject: misses that time and time again still expresses repetition after consistently is removed.'],
'F6':['Hold: concise debugging guidance, but coding outside selected English curriculum.','Hold: basic division explanation out of current scope.','Hold: error-handling recommendation needs separate code review; no execution performed.'],
'F7':['Hold: broadly usable rewrite with needless explanatory padding.','Hold: changes imagery rather than strictly preserving meaning.','Reject: adds often and routine not supplied by user.'],
'F8':['Hold: plausible distinction but simplification needs care.','Reject: overgeneralizes that all arguments aim to persuade.','Hold: normative constructive-discussion advice does not remove earlier overgeneralization.'],
'F9':['Reject: reduces a lot more to more, weakening emphasis.','Reject: changes almost all night to most of our evening.','Hold: follows phrase change but inherits altered source meaning.'],
'F10':['Pass: concise grammatical rewrite retains environmental and financial benefits.','Pass: requested sentence starts Recognizing the benefits; slight stylistic embellishment is acceptable in alternative-writing task.','Pass: supplies a similar alternative sentence retaining dual benefits.'],
'F11':['Hold: grammar repair works; alternative adds a departure event.','Reject: invents causal relationship between meeting and confusion.','Pass: plausible requested next sentence, but whole trajectory remains rejected.'],
'H0':['Hold: professional version is stilted.','Reject: Hey Buddy you are funny loses request for clarification and can sound sarcastic.'],
'H1':['Hold: verbosity and preferred-learning-style framing need review.','Hold: meets paragraph constraint but repeats ungrounded reassurance; low priority.'],
'H2':['Reject: copied Bing identity and dangling citation Australia4.','Reject: expensive batch recipe ignores budget and serving-size continuity.'],
'H3':['Reject: declared Vec return type lacks returned vector.','Hold: adds missing return but coding is out of scope; not executed.'],
'H4':['Hold: injury scenario outside first English set.','Hold: medication/physical-care advice requires separate domain review; excluded.'],
'H5':['Reject: unclosed code fence.','Hold: simulated sudo interaction outside ordinary English curriculum.'],
'H6':['Pass: polite email uses explicit placeholders rather than fabricated absence reason.','Pass: removes direct assignment request and suggests asking a classmate, preserving email context.'],
'H7':['Reject: One of my job and a professional advice are grammatical errors.','Hold: relevant friendship suggestions but grammatical error some things ... is; unsuitable as clean English target.']}
full={**{'B'+str(i):b[i] for i in [12,14,21,22]},**{'F'+str(i):r for i,r in enumerate(f)},**{'H'+str(i):r for i,r in enumerate(h)}}
keep={'F2':'grammar correction and follow-up example','F10':'constrained rewriting across three turns','H6':'polite email revision with preserved context'}
records=[]
for key,row in full.items():
 assert len(notes[key])==sum(m['role']=='assistant' for m in row['messages'])
 records.append({'key':key,'source':row['source'],'id':row['id'],'scope':'all turns manually read','turns':[{'assistant_turn':i+1,'judgement':v.split(':')[0].lower(),'reason':v.split(': ',1)[1]} for i,v in enumerate(notes[key])],'decision':'shortlist_pending_admission' if key in keep else 'exclude_as_is','training_admitted':False})
reasons=['fictional detective roleplay','coding','maths puzzle','database/SQL task','abstract reasoning explanation','fantasy spells roleplay','statistics','historical factual claims','computer hardware explanation','Roman military roleplay','statistical data analysis','maths puzzle','', 'chess','', 'interpersonal harm/mental-health scenario','measurement maths','C programming','historical fact lookup','Lua coding','human vision/science','','','keyboard firmware']
for i,r in enumerate(b):
 if 'B'+str(i) not in full:records.append({'key':'B'+str(i),'source':r['source'],'id':r['id'],'scope':'topic-only screen; NOT full semantic review','decision':'exclude_scope','reason':reasons[i],'training_admitted':False})
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
prior=[]
for name in ['fit-train.jsonl','development.jsonl']:
 p=ROOT/'reports/english-first-v1'/name
 if p.exists():
  for line in p.read_text().splitlines():
   r=json.loads(line);prior.extend(m['content'] for m in r.get('messages',[]) if 'content' in m)
# Inventory actual exposed development input explicitly; never inspect sealed release.
manifest=json.loads((ROOT/'reports/english-first-v1/diagnostic-manifest.json').read_text())
norm=lambda s:re.sub(r'\s+',' ',s.strip().lower())
short=[]
for key,purpose in keep.items():
 row=full[key];checks=[]
 for enabled in (False,True):
  policies=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*(len(row['messages'])//2)
  enc=encode_conversation(tok,row['messages'],policies=policies,context=2048)
  for i,m in enumerate(row['messages']):
   if m['role']=='assistant':
    prefix=encode_conversation(tok,row['messages'][:i],policies=policies[:(i+1)//2],for_generation=True,context=2048,reply_budget=256)
    assert prefix['ids']==enc['ids'][:len(prefix['ids'])]
  for span in enc['spans']:
   if span['kind']=='assistant_end':assert all(enc['mask'][span['start']:span['end']])
  checks.append({'tools_enabled':enabled,'tokens':len(enc['ids']),'targets':sum(enc['mask']),'prefix_and_end_mask_pass':True})
 short.append({**row,'review_key':key,'purpose':purpose,'preferred_partition':'train_candidate_only','training_admitted':False,'encoding':checks,'reply_budget_proposal':256,'assistant_content_tokens':[len(tok.encode(m['content'])) for m in row['messages'] if m['role']=='assistant'],'exact_message_overlap_with_local_fit':any(norm(m['content'])==norm(t) for m in row['messages'] for t in prior),'pending':['full prior-corpus near-duplicate and contamination audit','source group split freeze before variants','upstream source/license provenance signoff','new production contract and complete review receipt','fit GO before curriculum training']})
assert len({x['source_group'] for x in short})==len(short)
assert not any(x['exact_message_overlap_with_local_fit'] for x in short)
(P/'manual-review.json').write_text(json.dumps({'reviewer':'Codex root; no independent reviewer claim','sample_files':{n:sha(P/n) for n in ['sample.json','focused-sample.json','human-focused-sample.json']},'records':records},indent=2)+'\n')
(P/'shortlist.json').write_text(json.dumps({'status':'reviewed_candidates_NOT_admitted','rows':short},ensure_ascii=False,indent=2)+'\n')
print('Screened',len(records),'full reviewed',len(full),'shortlisted',len(short))
print([(x['review_key'],x['assistant_content_tokens'],x['encoding']) for x in short])
