import json,hashlib,collections
from pathlib import Path
R=Path(__file__).resolve().parents[2];D=R/'data/cosmopedia-explanatory-candidates-v1';O=Path(__file__).parent
# Human-authored judgments after reading all frozen full texts and prompts, not a classifier.
notes='''review|Coherent skepticism prose, but polemical religious seed and uncorroborated institutional/fungal-network specifics are presented with insufficient distance.
retain|Coherent simplified decolonization dialogue; topic follows instruction despite tangential Myanmar seed. Useful prose, not historical certification.
retain|Accessible bookshop and old-book explanation with a concrete activity; no material internal defect observed.
review|Readable alchemy lesson, but chronology and possible success at making gold are misleadingly loose; opera specifics not corroborated.
retain|Coherent Moscow landmark dialogue and budget/respect examples; historical details remain unverified.
hold|Noisy gaming-cheat seed phrase subjective rapid fire is laundered into an invented immigration questioning technique and historical claims.
retain|Crosshatching explanation and steps are coherent and low stakes; pen-pressure effects depend on tool.
hold|Knot dialogue encourages an improvised rope/log river bridge as safe and supplies unreliable anchoring/releasing instructions.
review|Friendship lesson is coherent but repeats unqualified teen mental-health statistics from a blog.
retain|Coherent matchbook collecting prose; publishing analogy is forced but intelligible. Collecting is distinct from smoking promotion.
review|Nonexplicit pornography/brain discussion makes overcertain universal rewiring/addiction claims; trusted-adult boundary is useful.
retain|Accessible transplant-career explanation; useful general prose, not clinically validated instruction.
retain|PLACEHOLDER'''.splitlines()
# Replace explicit indexed entries below; retain every decision rather than infer from categories.
notes=notes[:12]+['hold|Milkweed genomics seed is merged into unsupported claims about cryptobiosis and radiation/dehydration adaptations.']
notes+='''retain|Generational communication examples are coherent; emoji misunderstanding mechanism is thin, but ask-and-clarify lesson is usable.
review|Wine-advertising seed produces promotional child-facing prose and future wine-connoisseur aspiration; weak neutral educational framing.
hold|Timekeeping lesson forces a democracy/dictatorship analogy that teaches an unjustified desirable political midpoint and distracts from measurement.
hold|Entrapment examples conflate lack of knowledge with inducement and state blanket rules about when payment starts a crime.
review|Gambling-SEO seed becomes child-facing casino strategy; contains limits/randomness cautions but poor curriculum fit and promotional emphasis.
review|Readable Russia dialogue attributes a thesis but then endorses a one-sided account too readily; general history is not independently checked.
review|Community-development example promises multiple areas but stops after only some; specific workshops are added without source support despite terminal punctuation.
hold|Reasoning lesson treats liking both chocolate and vanilla as conflict and rectangle-to-e-reader inference as justified; fluent but unsound examples.
review|Slavery/indenture dialogue is coherent but historical origins and legal progress are oversimplified; avoid treating it as authoritative history.
retain|Coherent discipleship-model explanation within an explicitly religious frame; no material internal defect observed.
hold|Lottery lesson mixes 48 and49, gives an incorrect probability formula/numeric result, and contradicts its own percentage/one-in-million comparison.
retain|Invasive-species dialogue gives a coherent caution about introductions with some nuance; simplified ecological claims are not certified.
review|Coherent cooking procedure includes adult help and temperature/rest guidance, but recipe and safety details were not validated; figurative berry description is loose.
hold|Internal arithmetic contradiction: born1926 and died1944 but stated age21; earlier age17 in1943 makes inconsistency especially explicit.
retain|Identity-development dialogue sustains context and supportive followups without invented external actions.
review|Area arithmetic is correct, but curved-ridge approximation is underexplained and nonexistent linked resources are promised; audience drifts to high school.
review|Readable Buddhist emptiness exposition; constellation analogy risks confusing dependent existence with assigned meaning.
review|Library dialogue repeatedly parrots a literal catalog taxonomy and drifts to vendors; understandable but unnatural and weakly topical.
hold|Cactus lesson invents medicinal uses and famous Italian pizza toppings absent from its study-list seed; confident source-grounding drift.
review|Neurocritical-care introduction overclaims expertise and simplifies triage/stroke categories; fluent career prose, not medical validation.
review|US global-leadership dialogue presents geopolitical benefits too uncritically; political interpretation should not be mistaken for neutral fact.
hold|Medallion-guarantee lesson asserts all paperwork, legality and absence of cheating are guaranteed, materially overstating a narrow financial safeguard.
review|Readable Arctic ship explanation with odd causal details and unverified expedition specifics; no clear textual truncation.
retain|BDD awareness dialogue distinguishes perceived flaws and advises professional help; useful general prose, not clinical certification.
review|Named clinician biography extrapolates patient-contact role and conflates transfusion/tissue services beyond the supplied source.
review|Island folklore prose is coherent but presents invented-looking named stories as authentic cultural traditions without support; fiction itself is not the defect.
hold|Search-operator dialogue contradicts itself: agrees not to include minus-Italy, then explains adding it to exclude Italy.
retain|Digital-portfolio explanation is coherent, concrete and includes privacy/organization; introductory boilerplate violates prompt but prose is usable.
review|Surveillance lesson overgeneralizes data selling and ends a political argument with an absolute prediction; useful privacy tips do not certify these claims.
retain|Economic-history dialogue connects law, incentives and historical research coherently; examples are simplified rather than a comprehensive slavery account.
review|Ottoman text is largely a course outline promising later exploration, not fulfilled detailed teaching; demographic specifics unverified.
review|Digital-art lesson becomes NFT promotion, conflating token uniqueness with value and making ownership/safety claims too broadly.
review|Mostly coherent self-esteem dialogue, but infers police worker was not in school from starting at16, which source does not establish.
hold|ICD example invents meanings for code components, including A as acute, and claims one code describes everything wrong with a person.
review|Four Noble Truths explanation is broadly coherent, but maps Right Livelihood to maintaining positive relationships rather than livelihood.
review|Movers lesson is fluent but advertorial and overpromises undamaged transit; disposal heading describes disassembly instead.
review|Vegetarian pho adaptation is readable but asserted Hanoi origin/style and hoisin taste are oversimplified; ingredient quantities absent, recipe not validated.
retain|Change-management dialogue maintains context, offers a complete example and addresses resistance; four-step model is a simplification.
review|Retaining-wall explanation includes drainage/professionals, but carries a named contractor advertisement into the lesson and uses a weak sandcastle analogy.
retain|Dictionary/glossary comparison and student activity are coherent; subject dictionaries complicate the simplified distinction but core task is fulfilled.
review|Historical dialogue turns a theoretical Empire framing into a consensual peaceful world-order story, smoothing away conflict and uncertainty.
retain|Poetry interpretation lesson and activity are coherent and grounded in the interview's perspective; interpretation still requires textual support.
review|Care-transition prose is coherent but categorical nobody-has-overview claim and broadened study implications need qualification; no patient-specific instructions.
retain|Papercraft dialogue is coherent and practical; named older software recommendation remains a time-bound source detail.
hold|Child-targeted lesson directly promotes shopping for and drinking a branded vodka, turning an advertisement into enthusiastic educational advice.
hold|Harness-racing explanation repeatedly describes pacing as opposite legs rather than same-side legs, corrupting the central distinction; betting invitation is also poor child targeting.
retain|Talent-management dialogue sustains useful inclusion/accessibility examples; definition is narrower than the whole discipline but readable.
review|AutoCAD lesson is coherent but time-sensitive free-license claims and dated nearly40years language require context; substantial marketing boilerplate.
review|Ski lesson calls stem christies short quick racing steps and oversimplifies safe progression; technical sport instruction is not verified.
retain|Masonic-ethics dialogue offers coherent everyday honesty/fairness examples without repeating the conspiratorial seed; not a certification of organizational doctrine.
hold|Mediterranean lesson literally says horses were invented and makes absolute causal claims that all listed achievements required sea connections.'''.splitlines()
assert len(notes)==64,len(notes)
rows=[json.loads(x) for x in (D/'quality-sample.jsonl').read_text().splitlines()]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for i,(r,n) in enumerate(zip(rows,notes)):
 decision,reason=n.split('|',1)
 records.append(dict(sample_index=i,row_id=r['row_id'],doc_id=r['doc_id'],quartile=r['quartile'],format=r['format'],audience=r['audience'],text_sha256=r['text_sha256'],prompt_sha256=r['prompt_sha256'],decision=decision,reason=reason,full_text_and_prompt_read=True,external_fact_certification=False))
counts=dict(collections.Counter(r['decision'] for r in records))
result=dict(state='manual_quality_review_only_not_admitted',method='All64 frozen complete texts and prompts read; finite human judgment, no new sample or classifier.',pins={str(p.relative_to(R)):sha(p) for p in [D/'quality-sample.jsonl',D/'sample-manifest.json',D/'receipt.json',O/'policy.json']},counts=counts,records=records,limitations=['Balanced format/length sample is not a population defect-rate estimate.','Retain means useful language-learning example without a material observed defect, not verified facts or approval.','Review is not an exclusion. Hold is a recommendation to root, not a corpus mutation.','Terminal punctuation does not establish semantic completion, correctness, neutrality or instruction compliance.','Synthetic Alice/Bob text is not assistant-role supervision or verified tool execution.'])
(O/'manual-quality-judgments.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Fresh64 explanatory-candidate quality review','',f'All64 full texts and prompts read: {counts}. No corpus edits, exclusions, admission or resampling.','', 'The projection improves structural consistency, but substantial semantic teaching defects remain. Concrete failures include lottery arithmetic, contradictory biography ages, reversed search-negation guidance, fabricated code-component meanings, topic-splicing from noisy seeds, and horses described as invented. Fluent accessible prose is not a sufficient quality test.','', 'The retained examples provide useful descriptive language, contextual questions and short explanatory transitions. Many textbooks still ignore their no-title/no-introduction prompt. This matters for using these as instruction pairs; it does not by itself invalidate text-only pretraining. Alice/Bob conversations remain scripted exposition, not evidence of task fulfillment or tool grounding.','', 'Do not extrapolate sample fractions to149434 documents: selection deliberately balances length quartiles and formats. No external factual certification was performed. Review-rated examples must not be automatically excluded; fantasy, religion, politics and medical topics are not automatic defects. Holds identify concrete contradiction, unsound teaching or strong audience mismatch. Root decides any finite exclusion and next diagnostic.','', '|Index|Row|Decision|Reason|','|---|---|---|---|']
lines += [f"|{r['sample_index']}|{r['row_id']}|{r['decision']}|{r['reason']}|" for r in records]
(O/'QUALITY-REVIEW.md').write_text('\n'.join(lines)+'\n');print(counts)
