"""Full-path manual review; preserve original answers and rejected denominators."""
import json,hashlib
from pathlib import Path
P=Path(__file__).parent
sets={n:json.loads((P/n).read_text()) for n in ['sample.json','focused-sample.json','writing-sample.json']}
C=[
['Defer: environmental advice outside targeted correction lesson.','Defer: battery safety details need domain verification.'],
['Reject: wrong Open Assistant identity for Own.','Hold: recursive joke, no useful correction/state lesson.'],
['Defer: factual science not this intake.','Reject: ordinary hilltop visible-curvature claim unreliable.'],
['Reject: conflates denoising diffusion with repeatedly applying the image autoencoder.','Reject: simplifies to output description without explaining operation.'],
['Defer: horticultural treatment needs verification.','Reject: endorses blanket safety claims in user-provided treatment advice.'],
['Pass: correctly resolves secret riddle.','Hold: keyboard riddle is not correction or memory coverage.'],
['Defer: maths outside current curriculum.','Reject: endorses false blanket distinction that algebra cannot describe motion.'],
['Defer: calculus outside current scope.','Reject: rap says find their derivatives, conflicting with integration of dv.'],
['Defer: historical assertions unverified.','Reject: multiple spelling and grammar errors.'],
['Hold: broad social suggestions; limited correction/state value.','Hold: relevant but awkward wording and no concrete memory update.'],
['Defer: missing-person scenario needs separate safety review.','Reject: vague delay before reporting can undermine urgent help.'],
['Defer: business strategy outside current lesson goals.','Defer: generic financial recommendations, not grounded state update.'],
['Reject: calls variance sum of all deviations, omitting squares and normalization in explanation.','Defer: population/sample distinction unresolved; maths deferred.'],
['Defer: historical factual summary requires sourcing.','Reject: introduces grammatical errors as simplification.'],
['Reject: invents new career-path motivation.','Reject: requested separate Steve paragraph not supplied; retains invented motivation.'],
['Hold: addresses discrimination but not target correction/memory.','Hold: qualified distinction useful, but outside selected everyday skills.'],
['Defer: film-history sourcing not verified.','Defer: factual recommendations outside targeted grounded lesson.'],
['Defer: nutrition estimates unverified.','Defer: nutrition comparisons outside English-first curriculum.'],
['Reject: overstates chaotic randomness and impossibility in three-body explanation.','Pass: acknowledges orbit/rotation terminology correction; earlier error blocks full path.'],
['Reject: conflates UTF8 representation with Unicode code point and assumes uppercase sharp S.','Hold: source citation does not resolve initial ambiguous symbol request.'],
['Pass: coherent requested fictional reunion scene.','Reject: 134/200 words is 67%, not requested 60%; no rounding policy was predeclared.'],
['Hold: basic sandwich instructions, verbose.','Reject: repeated sandwhich misspelling and awkward grammar.'],
['Hold: generic film review with unverified factual/production claims.','Pass: retrieves actor name and obeys name-only constraint; full path not cleared.'],
['Pass: asks which Brian.','Reject: adds unverified current residential whereabouts unnecessary to identity clarification.']]
M=[
['Hold: casual lottery pick, no target lesson.','Reject: supplies number as least-likely without evidence.','Reject: changes number and contradicts earlier choice with unsupported probability claims.'],
['Hold: grammar errors in speculative immortality discussion.','Defer: book/movie fit unverified.'],
['Defer: geopolitical claims outside intake.','Reject: accepts stale ongoing-Afghanistan claim in user addition.'],
['Pass: requests missing notes.','Reject: adds underfitting outside notes and gives non-exclusive answer options.'],
['Reject: broad unsupported historical generalizations.','Hold: uncertainty acknowledged but poor earlier answer invalidates path.'],
['Reject: says sets cannot be modified, then describes mutation.','Defer: code not executed; earlier contradiction remains.'],
['Reject: unsupported game features and malformed trailing parenthesis.','Defer: recommendations and mods require verification.'],
['Reject: invents extensive research and significant progress.','Reject: changes audience but retains unprovided progress claims.'],
['Reject: dismissive nonsensical label and ungrounded comparison.','Reject: severe grammar errors and speculative factual claims.'],
['Reject: overgeneralizes hardware suitability and ease.','Reject: misleading requirement for programming and mismatched text model recommendation.'],
['Hold: coherent image prompt but outside target skill.','Hold: unsupported prompt-quality recipe, no demonstrated memory lesson.'],
['Defer: pregnancy guidance requires dedicated clinical review.','Defer: medical claims not verified here; no admission.'],
['Hold: resists implausible premise, but factual science outside intake.','Defer: literature claims need verification; not a clean everyday correction.'],
['Defer: history not independently sourced for admission.','Defer: historical continuation not targeted memory lesson.'],
['Reject: presents supernatural framework as established fact.','Reject: elaborates unsupported supernatural claims without attribution as belief.'],
['Defer: trading/financial advice outside English intake.','Defer: stale regulatory generalization; not admitted.']]
W=[
['Pass: follows DM prefix, sets scene and asks name/class/motivation.','Hold: retains character facts, but lengthy fantasy roleplay outside ordinary-English focus.'],
['Reject: invents research, attached quote and available budget.','Hold: user-requested excuse does not repair first-turn invention.'],
['Defer: technical code task outside scope.','Reject: removes interval even though original sends immediately; accepts false premise.'],
['Reject: unsupported Robot Framework keywords.','Reject: abandons request with generic capability disclaimer.'],
['Defer: Ruby program not executed.','Defer: simplistic CSV handling requires separate code review.'],
['Pass: offers relevant creative names as suggestions, without claiming uniqueness.','Pass: incorporates energy emphasis while retaining crop/bio/agriculture theme.'],
['Pass: warm thank-you note retains Jacob, gift card, favourite cafe and birthday; superlative is stylistic.','Pass: preserves Jacob/birthday/gift, adds Beanz and feeling recognized/appreciated, removes best superlative.'],
['Defer: book-summary/reception claims not verified.','Reject: out limitations typo and removed criticism coverage.'],
['Reject: substantially below requested 1000 words.','Reject: falsely claims thousand words and repeats unverified history.'],
['Reject: treats Tomcat as full Java EE implementation.','Reject: incoherent rhymes and animal lovers corncob ending.'],
['Defer: weapons history outside English task.','Defer: unverified firearms comparisons, not admitted.'],
['Hold: treats resignation reason as mandatory rather than optional.','Reject: overrides explicit refusal to train replacement with handover commitment.'],
['Hold: plausible classification, but sentence alone is ambiguous.','Hold: acknowledgement only, no correction/memory value.'],
['Reject: late-night scenario becomes all day and adds irrelevant boys comparison.','Reject: misses day-after-tomorrow detail and repeats awkward wording.'],
['Hold: invents extensive personal family history.','Defer: crisis response requires dedicated safety/current-resource review; excluded.'],
['Reject: claimed eight lines contradicted by function; empty map unsafe.','Reject: retains unsafe empty-map dereference and exceeds length limit.']]
records=[];chosen=[]
for filename,notes in zip(sets,[C,M,W]):
 rows=sets[filename]['rows'];assert len(rows)==len(notes)
 for row,ns in zip(rows,notes):
  assert len(ns)==sum(m['role']=='assistant' for m in row['messages'])
  keep=row['review_key'] in {'W5','W6'}
  records.append({'key':row['review_key'],'id':row['id'],'source_group':row['source_group'],'full_text_read':True,'turns':[{'turn':i+1,'judgement':n.split(':')[0].lower(),'reason':n.split(': ',1)[1]} for i,n in enumerate(ns)],'decision':'reviewed_candidate' if keep else 'excluded_as_is','training_admitted':False})
  if keep:chosen.append({**row,'source':'OpenAssistant/oasst2','source_revision':sets[filename]['source_revision'],'license_declared':'Apache-2.0','reply_budget':384,'family':'preference_refinement' if row['review_key']=='W5' else 'correction_with_entity_retention','preferred_partition':'train_candidate_only','independent_human_authorship_verified':False})
assert len({r['source_group'] for r in records})==56
(P/'manual-review.json').write_text(json.dumps({'reviewer':'Codex root; no independent semantic review claim','sample_hashes':{n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in sets},'adaptive_batches':[24,16,16],'records':records},indent=2)+'\n')
(P/'shortlist.json').write_text(json.dumps({'status':'reviewed_train_candidates_not_admitted','rows':chosen},indent=2,ensure_ascii=False)+'\n')
print(len(records),sum(len(r['turns']) for r in records),'responses; selected',[(r['review_key'],r['encoding']) for r in chosen])
