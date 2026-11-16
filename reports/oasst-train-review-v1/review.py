"""Manual per-response review; raw answers preserved; no training admission."""
import json,hashlib
from pathlib import Path
P=Path(__file__).parent;sample=json.loads((P/'sample.json').read_text())
notes=[
['Reject: invents a newly presented opportunity and replacement-training commitment.','Reject: Your welcome is grammatically wrong.'],
['Defer: Morse encoding is outside core English conversation.','Pass: appropriate acknowledgement.'],
['Pass: natural greeting.','Reject: sixteen lines and repeated refrain weakly satisfy short song for a two-year-old.'],
['Defer: operating-system procedure needs separate technical verification.','Pass: appropriate acknowledgement.'],
['Pass: asks for clarification of unclear request.','Reject: invents device-specific menus without model context and does not supply requested script.'],
['Reject: invents completed coursework, eligibility and paid fee.','Reject: repeats unprovided fee and eligibility assertions.'],
['Defer: terminal simulation outside English scope.','Defer: simulated shell output; not a positive real tool trajectory.'],
['Reject: adds commitment that colleagues will handle unfinished tasks.','Reject: assures outcome without knowing expectations.'],
['Defer: factual astronomy belongs to later science curriculum.','Defer: science facts not independently verified for admission.'],
['Reject: mnemonic does not encode dates and conflates battles and wars.','Pass: acknowledgement, but preceding lesson remains invalid.'],
['Pass: 98 words under whitespace counting, humorous postcard within requested length.','Reject: far exceeds retained postcard length constraint.'],
['Reject: ignores single-paragraph format and adds unprovided track record.','Reject: omits explicitly requested company name Super User IT.'],
['Pass: varied graduation gift ideas framed as suggestions; acknowledges preferences, no invented purchase or availability claim.','Pass: concise relevant acknowledgement.'],
['Hold: uneven awkward verse; not a priority clean-English lesson.','Reject: unnatural My think and/or best and unnecessary identity disclaimer.'],
['Pass: natural greeting and offer of help.','Hold: asks useful clarification but overwhelms vague request with long generic lists.'],
['Pass: natural greeting.','Defer: coding example outside current curriculum; not executed.'],
['Defer: nursery-rhyme history needs factual source review.','Defer: historical explanation outside current scope.'],
['Defer: medical diagnosis not appropriate for this English intake.','Defer: medical advice requires separate domain review.'],
['Reject: endorses premise without correcting inconsistent witch identities/events.','Defer: author biography is factual rather than supplied-context English.'],
['Pass: requests genre, platform and preferences.','Reject: includes 2018 title despite after-2018 request; recommendations also need factual verification.'],
['Hold: model capability claim not tied to Own evidence.','Reject: clumsy clarification with avoidable judgement about understandable wording.'],
['Hold: long explanation and misleading blanket avoidance of repeated letters.','Reject: great against steel should have misplaced e, not the shown correct-position e.'],
['Reject: ungrammatical As I am ... and can even sentence.','Pass: invites discussion in requested roleplay context.'],
['Defer: depression treatment guidance needs separate clinical review.','Defer: therapy explanation outside initial source intake.'],
['Pass: brief natural greeting.','Hold: repetitive generic small talk provides little additional supervision.'],
['Reject: malformed HTML comment and does not fulfill requested page count.','Defer: technical repair retains incomplete request fulfillment; not executed.'],
['Reject: names an unspecified calculator and invents its capabilities.','Pass: reasonable optional topping list, but preceding claim invalidates trajectory.'],
['Defer: factual bibliography needs verification outside English intake.','Defer: unverified titles/authors and accessibility recommendations.'],
['Reject: top-ten heading lists only five, ellipses and blanket paper avoidance.','Reject: preserves incomplete and weak source content despite formatting change.'],
['Reject: awkward grammar and several weak or absent twists.','Reject: defensive response and unverified AI-language premise instead of accepting correction.'],
['Defer: dating-abbreviation factual coverage outside core curriculum.','Hold: recommends ambiguous abbreviations after correctly recommending clear wording.'],
['Hold: verbose boilerplate about capability rather than helpful short response.','Hold: usable creative outline but paired with low-value boilerplate; not priority.'],
['Hold: broad self-capability claims not substantiated for Own.','Hold: generic self-training history is not Own-specific verified provenance.'],
['Reject: HIDDEN should encode LMHHIR, not LMHHIP.','Defer: correct-looking substitution table is outside selected English scope.'],
['Hold: emoji-heavy technical explanation needs precision review.','Defer: graphics knowledge outside first English intake.'],
['Defer: neuroscience requires separate factual review.','Reject: categorical claim of no particle current is misleading.'],
['Hold: broad literary synthesis requires source accuracy review.','Reject: claims all protagonists seek to save world; Moby Dick comparison is unsound.'],
['Reject: answers pitch extremes instead of range.','Hold: unverified organ-range claim; earlier wrong answer remains.'],
['Reject: guesses franchise from inadequate evidence and repeats created.','Reject: refuses requested story through invented printing restriction.'],
['Pass: grammatical usage examples.','Reject: several examples explain one reading only rather than the requested multiple meanings.'],
['Pass: follows supplied prompt format and artist placement.','Reject: loses studying portrait focus in unrelated adventure description.'],
['Defer: code task outside scope.','Reject: agrees with false premise about looping N values; explanation conflicts with actual code.'],
['Reject: numbers are not in claimed descending order.','Defer: fixes ordering but physical values unverified and prior error remains.'],
['Reject: categorical impossibility without key is unjustified.','Defer: cipher output not independently replayed; outside current scope.'],
['Pass: asks for missing context without assuming doubt is irrational.','Pass: empathetic reply preserves James and relationship context, avoids mind-reading and suggests communication without guarantees.'],
['Reject: calls platypus a bird; other definitions inaccurate.','Reject: several awkward or vague definitions unsuitable for clean English.'],
['Reject: curly quotation marks make presented Python invalid.','Reject: keeps invalid quotes after formatting request.'],
['Hold: correct translation but adds distracting franchise joke.','Hold: philosophical discussion adds complexity outside concise everyday curriculum.']]
assert len(notes)==len(sample['rows'])==48
records=[];chosen=[]
for r,ns in zip(sample['rows'],notes):
 assert len(ns)==sum(m['role']=='assistant' for m in r['messages'])
 key=r['review_key'];selected=key in {'T12','T44'}
 records.append({'key':key,'id':r['id'],'source_group':r['source_group'],'full_text_read':True,'turns':[{'turn':i+1,'judgement':s.split(':')[0].lower(),'reason':s.split(': ',1)[1]} for i,s in enumerate(ns)],'decision':'reviewed_candidate' if selected else 'excluded_as_is','training_admitted':False})
 if selected:
  chosen.append({**r,'family':'everyday_suggestions' if key=='T12' else 'clarification_and_support','reply_budget':384,'source':'OpenAssistant/oasst2','source_revision':sample['source_revision'],'license_declared':'Apache-2.0','preferred_partition':'train_candidate_only','independent_human_authorship_verified':False,'generated_variants':False})
(P/'manual-review.json').write_text(json.dumps({'reviewer':'Codex root, no independent reviewer claim','sample_sha256':hashlib.sha256((P/'sample.json').read_bytes()).hexdigest(),'adaptive_review_batches':[16,16,16],'records':records},indent=2)+'\n')
(P/'shortlist.json').write_text(json.dumps({'status':'reviewed_train_candidates_not_admitted','rows':chosen},ensure_ascii=False,indent=2)+'\n')
print('48 complete conversations / 96 assistant responses reviewed; 2 candidates')
