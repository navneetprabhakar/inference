"""Persist the completed fixed64 full-text reading; no corpus modification."""
import collections,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;D=ROOT/'data/cosmopedia-intake-v1'
# Decision, completion, learner fit, observed reason. Retain means useful prose candidate only.
notes=[
('hold','truncated','advanced','Ends mid-citation Christie &; medical introduction promises missing sections; no complete lesson.'),
('hold','unfinished_section','advanced','Ends at Scene1 heading without the promised scene analysis; introductory chapter fragment.'),
('hold','truncated','advanced','Ends mid-year in2; course introduction is incomplete.'),
('retain','complete','general','Coherent fictional coffee conversation and resolution; useful natural dialogue within narrative, not assistant/tool format.'),
('retain','complete','intermediate','Coherent earthquake-simulation explanation with limitation statement; hypocenter/finite-difference vocabulary is above young-child label; not independently scientific fact-checked.'),
('hold','truncated','advanced','Ends mid-citation Kuh et al.,2; invented-paper register and promised empirical methods lack supplied evidence.'),
('review','complete','simple','Readable soap-stamp procedure but specialized machine parts and material recommendations are unverified; narrower than generic simple prose.'),
('review','complete','simple','Fluent musical story but blends named real people/university with invented dialogue and jazz transformations; distinguish fiction from biography.'),
('review','complete','general','Coherent historical fiction; Tang/SilkRoad abacus origin detail unverified; not suitable as certified history.'),
('hold','truncated','simple','Cuts off mid-platform name Bet3; betting tutorial also blurs virtual money and real platform operation.'),
('review','complete','simple','Readable curling overview; indoors using frozen ponds is confused phrasing and historical/equipment details unverified; miles-away target is hyperbole.'),
('retain','complete','advanced','Complete thematic literary discussion with coherent paragraphs; generic and abstract rather than child-level, cultural claims not certified.'),
('review','complete','general','Complete refusal/alternatives answer, but trial duration and blanket legal claim unverified; assistant refusal style inside pretraining rather than supplied role frames.'),
('retain','complete','simple','Useful reflective-writing explanation plus concrete fictional sample letter; minor composiion typo, no serious internal logic failure.'),
('hold','truncated','advanced','Unclosed markdown fence and incomplete metrical grid; specialized phonology explanation with suspect syllable/stress mapping.'),
('retain','complete','simple','Coherent question-answer exchanges on rope/macrame with follow-ups; craft advice not independently tested, no actual tool traces.'),
('hold','unfinished_task','simple','Recipe never reaches amounts/mixing/baking; stops after ingredient gathering and asks whether to continue. Large irrelevant locate-your-kitchen scaffolding.'),
('review','complete','simple','Computer-management fable has closure but names Memory/Disky become Memorius/Diskus without explanation; metaphor to literal CPU processes shifts.'),
('review','complete','intermediate','Fluent regional-history overview imports CrossRiverNY convenience-store case without explaining ConnecticutValley link; geographic grounding questionable.'),
('review','complete','simple','Alien dialogue overgeneralizes diverse NativeAmerican traditions and spiritual healing into uniform practices; readable but unsupported cultural/health generalizations.'),
('hold','complete','advanced','Mathematical teaching defects: unsigned physical volume written as determinant, inconsistent3x3entry labels, positive determinant said to preserve oriented volumes rather than orientation.'),
('retain','complete','simple','Coherent hero/diversity/found-family lessons with explicit classroom activities and examples; fictional character details unverified.'),
('review','complete','advanced','Complete pharmacogenomics overview; specialized drug/metabolism statements and clinical practice generalizations need expert validation; high-school label does not make it simple.'),
('retain','complete','intermediate','Coherent coaching scenario with concrete visual-support actions and follow-up feedback; hypothetical data are illustrative, not independent study evidence.'),
('hold','complete','advanced','Patent-litigation lesson has internally reversed party incentive: patentee with oversized favorable award said to seek new trial; legal standards also unverified.'),
('review','complete','advanced','Fluent clinical AOM article with specific guideline/vaccine/biomarker claims and citations not verified; inappropriate as certified medical teaching.'),
('review','complete','simple','Nucleation fable readable but new-particles/palace/temperature metaphors obscure actual phase nucleation; scientific correctness not established by child style.'),
('hold','complete','general','Film-research story argues existence statement misleading because several films exist, a logical error; extra remake attribution unverified and research persona unsupported.'),
('retain','complete','simple','Clear toy-rescue narrative illustrating plan/act/monitor with closure; fantasy elements explicit and not factual defects.'),
('hold','complete','general','Food-preservation instructions forced into Shakespeare gender analogy; universal10minute processing and salt-by-taste recipe lack validated preservation conditions.'),
('retain','complete','advanced','Coherent public-service course recap, but references absent previous chapters; useful expository register only, not standalone evidence of the earlier course.'),
('retain','complete','simple','Coherent recycling/energy-conservation animal fable with clear cause/action/resolution; simplified environmental outcomes are framed as story.'),
('review','complete','advanced','Reasonable structured hazard-identification prose; precise recent-research citations not substantiated and safety expertise not certified.'),
('review','complete','intermediate','Useful essay-writing steps but refers to webpage excerpt not included in text; partly dependent on omitted seed context.'),
('review','complete','simple','Readable nutrition lesson includes exact60percent cravings reduction and broad weight-loss claims without evidence; needs health-content review.'),
('retain','complete','general','Coherent explicitly storylike education-reform/bushfire narrative with closure; invented officeholders acceptable as fiction, not Australian history.'),
('review','complete','simple','Magical divination fable is internally understandable, but ends teaching supernatural guidance and decisions through a spinning top; fantasy does not validate real-world instruction.'),
('retain','complete','advanced','Coherent art-politics survey with chronological progression; generic course recap and historical interpretations are not independently verified.'),
('review','complete','simple','Cover-letter-start task completed but excessive seating/pen boilerplate and nonsensical reverse-instructions for left-handed writers; limited efficiency/value.'),
('review','complete','advanced','Highly specific Indigenous-land and police-statistics claims with suspect cross-jurisdiction attribution; no supplied evidence to certify; advanced prose only.'),
('review','complete','general','Readable hobby story with correct80+160+20 arithmetic, but completion of first jar abruptly implies all3filled and refers to earlier absent formula.'),
('review','complete','advanced','Anthropology overview overgeneralizes obligations and says own-kin marriage after describing affinal relatives; specialist distinctions require review.'),
('hold','complete','simple','Concrete object-description mismatch: string-attached sticks on raised-square board identified as paint palette/brushes; fluent alien framing masks wrong physical grounding.'),
('hold','complete','simple','Teaches incorrect definitions: accuracy=consistent, precision=rightfit/optimal twigsize; malformed Unciness title. Scientific word salad rather than useful simplification.'),
('review','complete','intermediate','Energy lesson mixes conservative ideal with powered experimental apparatus and unmeasured claim of proof; fictional experiment should not establish scientific verification.'),
('hold','complete','simple','Explicit false arithmetic567-254=456; multiple borrowing/place-value explanations contradict displayed equations. Unsuitable mathematical teaching.'),
('retain','complete','simple','Coherent follow-up dialogue linking prior experience and adaptation; naval analogy oddly specific and ensures-success phrasing overconfident, but main discourse/state intact.'),
('retain','complete','intermediate','Coherent media-representation explanation using hypothetical examples and tradeoffs; much more abstract than young-child label.'),
('review','complete','general','Coherent puzzle story and correct10+30x=70=>2, but appends missing-premise exercise claiming facts were in introduction; not fully grounded in its own earlier narrative.'),
('review','complete','simple','Complete calendar tutorial with excessive bodily scaffolding, unsupported exactUI/icon details and missing icon glyphs; not executable verified tool data.'),
('review','complete','advanced','Long specialist genetic-method narrative with detailed studies/citations and sex/chromosome mechanisms not verified; unsuitable as simple-prose priority.'),
('review','complete','advanced','Worked percentage computation approximately3.9 is consistent, but unlikePED responsiveness contrast and flattening interpretation overstate/blur concepts; not certified economics.'),
('review','complete','general','Coherent supplement/insomnia cautionary fiction but causal diagnosis and medication self-experimentation are not evidence-backed medical instruction.'),
('review','complete','general','Literary museum story has closure; accesses historical letter inside exhibit and invokes ancientGlobe stones, blending magical/fictional narrative with questionable real-site detail.'),
('hold','complete','simple','Radical lesson explicitly calls5 the index ofsqrt5, confuses root/radicand operations and offers invalid forced answer forms; child analogy hides mathematics errors.'),
('review','complete','intermediate','Readable poetry overview with unsupported specialized category/history claims and explicit insertYouTubelink placeholder; not complete standalone learning resource.'),
('review','complete','general','Dental-advice tutorial fluent but prescribed intervals/whitening and appearance-as-health claims unverified; not a simple neutral prose priority.'),
('hold','degenerate_truncated','simple','Fibonacci story collapses into massive repeated escaped underscores after malformed Def function; no executable code or narrative completion.'),
('review','complete','intermediate','Fluent composer biography, but dense named-entity list and unverified inferred motives/exactclaims; child label not sufficient for grounding.'),
('review','complete','advanced','Long pseudo-academic history uses specific study attributions and causal institutional claims without evidence; chronology/containment continuity questionable; not factual certification.'),
('hold','complete','simple','American-literature lesson asserts RowlingAmerican citizenship and classifies talking-animalCharlottesWeb as realisticfiction contrary to its own definition; concrete educational misteaching.'),
('retain','complete','intermediate','Coherent tech-policy overview with articulated tradeoffs/examples; dated policy claims need temporal qualification, not current operational advice.'),
('review','complete','simple','Hair tutorial complete but bloated locate/grasp/mirror explanations dominate; practical steps not independently tested, poor concise-language target.'),
('review','complete','advanced','Dense metalloprotein/spectroscopy exposition with specific cofactor/isotope claims not checked; advanced content not validated by polished prose.')]
rows=[json.loads(x) for x in (D/'quality-sample.jsonl').read_text().splitlines()];assert len(rows)==len(notes)==64
records=[]
for i,(r,n) in enumerate(zip(rows,notes)):
 decision,completion,fit,reason=n
 records.append({'sample_index':i,'row_id':r['row_id'],'doc_id':r['doc_id'],'text_sha256':r['text_sha256'],'audience':r['audience'],'format':r['format'],'quartile':r['quartile'],'gpt2_text_tokens':r['gpt2_text_tokens'],'decision':decision,'completion':completion,'learner_fit':fit,'reason':reason,'full_text_read':True,'independent_factual_certification':False})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
counts=dict(collections.Counter(r['decision'] for r in records));result={'state':'manual_fixed64_review_not_admitted','sample_sha256':sha(D/'quality-sample.jsonl'),'sample_manifest_sha256':sha(D/'sample-manifest.json'),'intake_receipt_sha256':sha(D/'receipt.json'),'method':'Read all64 full generated texts, not only snippets; re-read records8and51 after display truncation. No new samples, source edits, exclusion changes or external fact-check certification. Decisions apply to individual observed texts only.','decision_meanings':{'retain':'useful coherent prose candidate; neither factual certification nor admission','review':'readable but uncertain grounding, scope, artifacts or learner-fit; not an automatic exclusion','hold':'visible serious truncation/degeneration/semantic instruction error or unvalidated consequential procedure'},'counts':counts,'completion_counts':dict(collections.Counter(r['completion'] for r in records)),'records':records,'training_admitted':False,'corpus_mutated':False,'new_exclusions_applied':False}
with (HERE/'manual-quality-judgments.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'counts':counts,'completion':result['completion_counts']}))
