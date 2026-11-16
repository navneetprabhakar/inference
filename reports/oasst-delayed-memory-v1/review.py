"""Materialize manual full-trajectory decisions; never a training admission."""
import json
from pathlib import Path
P=Path(__file__).parent
# Each entry contains one observation for each assistant response, in order.
notes={
'D':[
['Unverified FOSS/tool recommendations.','Claims link investigation without tool evidence; departs from FOSS request.','Malformed closing: if you need questions.'],
['Technical IPv6 explanation outside current curriculum.','Adoption claims not independently verified.','Provider/tunnel recommendations not verified; no target memory.'],
['Technical career advice not checked.','Responds to user topic switch.','Correction prompt has false premise; no delayed recall demonstrated.'],
['Code/math example not executed.','EPSILON explanation not independently checked.','Technical explanation outside English-only scope.'],
['Philosophical claims not checked.','Causal attribution cautiously framed.','Does not resolve false premise or ownership of earlier statement.'],
['Technical definitions not checked for admission.','Projection described as constant function: unsuitable target.','Historical assertions not verified.'],
['Arduino code not executed; out of scope.','Routine acknowledgment.','Routine acknowledgment; no correction or recall.'],
['Past-AI letter is not evidence of actual memory.','Repeats limitations and roleplay setup.','Fictional reunion; name repeated in latest prompt, not delayed recall.'],
['Answer contains Therefour typo.','Explanation contains nunber typo.','Your welcome grammar; unsupported claim about user understanding.'],
['Game facts unverified.','Asks for story direction.','Creative continuation; plant explicitly repeated, no delayed recall test.'],
['Consciousness claims not checked.','Overconfident biological framing.','Takes ownership of the user argument as its own.'],
['Survival advice outside current curriculum.','Speculative threat list unverified.','Biology claims unverified; no target recall.'],
['Requested 20 words; supplied 15 whitespace-delimited words.','Immediate prompt transformation.','Historical explanation unverified; cannot rescue first failure.'],
['Treats both shows as workplace/mockumentary: unsuitable comparison.','Brief answer to follow-up.','Counts unverified; no correction retention.'],
['Conflates asyncio example with requested multithreading.','Technical answer unverified.','Technical overview, no target recall.'],
['Project-specific identity content.','Claims I am OpenAssistant, unsuitable for Own.','Unsupported web-search attribution and dangling citation.'],
['Useful explanation of pasting document text.','Appropriate acknowledgment.','Appropriate goodbye; all clean but no target capability.'],
['Vehicle procedure contains duplicate fill step; full safety procedure not verified.','Fixes duplicate only; does not validate remaining procedure.','Mechanical advice unverified; exclude entire trajectory.']],
'B':[
['HVAC claims outside current scope.','Appropriate acknowledgment.','Heaers typo and unverified efficiency generalizations.'],
['Honest lack of URL access but no request for pasted text.','Unsupported lifelong-learning framing.','Claims future automatic learning/improvement without evidence.'],
['Breed/size suitability and grammar concerns.','Exercise advice not verified.','Follow-up qualification not a delayed recall target.'],
['Astronomy facts not verified for this curriculum.','Routine acknowledgment.','New astronomy question, no delayed recall.'],
['Unrelated electromagnetic-equations link.','Fails to clarify the actual topic.','Repeats failure after hello.'],
['Acknowledges translator-only instruction.','Fails to correct supplied sentence; asks for text again.','Final rewrite cannot rescue failed earlier target.'],
['Lowercase I in assistant prose.','Declines requested code artifact.','Generic suggestions, no correction retention.'],
['Misspellings in factual explanation.','Correction itself misspells apologies.','Unrequested repeated history, facts unverified.'],
['Does not meet comprehensive request.','Environmental advice unverified.','Unqualified technical claim; outside scope.'],
['Useful clarification.','Code not executed; case/format concerns.','Bulk processing and uniqueness claims unverified.'],
['Gives titles instead of scenes; unsuitable content for this curriculum.','Acknowledges mismatch without repairing answer.','Awkward closing; no target recall.'],
['Wrong topic and garbled wording.','Relevant repair.','Fine acknowledgment cannot rescue first answer.'],
['Invents user game-development context.','Game recommendations unverified.','New courier question with unsupported price.'],
['Overpromises optimal performance.','Technical reward explanation unverified.','Routine acknowledgment, no memory.'],
['Inflammatory caricatures and prose problems.','Awkward acknowledgment.','Uninformative yes rather than useful engagement.'],
['Biography unverified.','Video claims unverified.','Includes same creator when asked for other creators.']],
'F':[
['Unnecessary refusal of a remorse story.','Repairs refusal but promises to answer anything.','Useful revision cannot rescue earlier failures.'],
['Correct main sentence but explanation contains aswell and awkward grammar.','Appropriate acknowledgment.','Feedback acknowledgment only; no later application.'],
['Suitable initial draft.','Generic hashtags and exaggerated register.','Adds unsupported dated lunar-landing prediction; no grounded repair.'],
['Dismisses chest-pain concern without basis; exclude.','Medical content not independently checked.','Later referral cannot rescue first harmful target.'],
['Shell code not executed; explanation not validated.','Dismisses distinction between installed package and PATH lookup.','Drops snake-case requirement by removing hyphens instead.'],
['Useful theme clarification, though verbose.','Lyric draft follows theme.','Keeps chorus three times despite less-repetitive request.'],
['Coherent fictional premise.','Generic continuation consistent with premise.','Adds background, but no corrected fact or delayed user-fact retrieval.'],
['Security workflow not technically qualified.','Generic performance advice not verified.','Unverified resource recommendations; no target correction/recall.'],
['Misinterprets image-model prompt task as prose-description task.','Declines repair rather than addressing feedback.','Later attempt cannot rescue earlier targets.'],
['Code unverified; no formatting fence.','Applies requested code-block formatting.','Drops corrected code-block formatting on next turn.'],
['Optics-cleaning advice not qualified for admission.','Technical explanation unverified; no concrete servicing address.','Acknowledgment only, no delayed recall.'],
['Uses only one of supplied slang terms.','Generic apology without substantive repair.','Invents meaning of rizz as reside/hole.'],
['Unsubstantiated safety, efficiency and scale claims.','Adds reasons for consumer preference not supplied by user.','Adds stronger unsupported cheapest/market claims.'],
['Incomplete code and omits Power BI integration.','Does not supply working integration.','Code not executed; JSON value represented as table without conversion.'],
['Game mechanics unverified; elaborate violent fictional persona out of current scope.','Same-persona game variant, no user-fact recall.','Further variant, no correction-retention evidence.'],
['Useful five naming suggestions.','Matches each name to tagline; some absolute marketing claims.','Invents compact design, real-time updates and interface features not supplied.']]
}
reviews=[]
for prefix,name in [('D','sample.json'),('B','branch-sample.json'),('F','focused-sample.json')]:
 rows=json.loads((P/name).read_text())['rows']
 assert len(rows)==len(notes[prefix])
 for r,ns in zip(rows,notes[prefix]):
  assert len(ns)==sum(m['role']=='assistant' for m in r['messages'])==3
  reviews.append({'review_key':r['review_key'],'source_group':r['source_group'],'path_ids':r['path_ids'],'decision':'exclude_from_target_shortlist','assistant_turn_reviews':[{'turn':i+1,'observation':n} for i,n in enumerate(ns)],'training_admitted':False})
(P/'review.json').write_text(json.dumps({'review_method':'Codex full source trajectory read; per-turn observations; domain facts/code not independently verified where noted','target_rubric':'Full trajectory must be suitable. Correction must persist into a later answer, or prior user fact must be retrieved after at least one intervening completed exchange without restatement in retrieval query. Turn count/acknowledgments alone do not qualify.','reviewed_conversations':len(reviews),'reviewed_assistant_responses':sum(len(r['assistant_turn_reviews']) for r in reviews),'retained':0,'reviews':reviews},indent=2)+'\n')
(P/'shortlist.json').write_text(json.dumps({'rows':[],'training_admitted':False,'reason':'No fully suitable target trajectories in this bounded review; previous four candidates unchanged.'},indent=2)+'\n')
