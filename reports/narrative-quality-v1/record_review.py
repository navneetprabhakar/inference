"""Record fixed human-read judgments after all32fulltexts were inspected."""
import collections,hashlib,json,pathlib
P=pathlib.Path(__file__).resolve().parent
DECISIONS=[
('retain','Complete lost-and-found story with consistent cat/dog roles; unexplained relocation is a mild plot convenience, not a factual instruction.'),
('retain','Clear question, explanation and parallel action; anthropomorphic flea/dog treated as fiction, not zoological teaching.'),
('retain','Brief coherent threat/escape/consequence narrative with complete ending; no graphic detail or procedural harm.'),
('review','Readable sharing story, but concluding both are no longer jealous attributes jealousy to Lily without prior support; magical library is figurative.'),
('retain','Coherent lost-toy/help/search/resolution; late remembered location is convenient but compatible with preceding search.'),
('retain','Consistent weekly meeting chronology and friendship arc; repeated speak/persistent vocabulary is formulaic but intelligible.'),
('retain','Coherent shared leaf/box action and ending. Deafness does not preclude speech; no contradiction inferred from Max speaking.'),
('retain','Complete locked-box/key/toy resolution; convenient discovery still preserves causal sequence and object identity.'),
('review','Grammatical full ending, but fall, house fire and sunset are weakly connected episodes; emergency service mention is sensible, not instructional certification.'),
('hold','Sharp-nail subplot is abandoned after explicit warning is ignored; ending returns to toy cat without resolving unsafe object or narrative tension.'),
('review','Hugging episode then unrelated magic-bear/cake wish; explicitly magical event is valid fiction, but the final moral poorly integrates it.'),
('hold','Farmer reverses wool to smooth it: core repair verb has no coherent action meaning; lexical misuse sits at causal resolution.'),
('hold','Wise owl advises lost bird to fly in any direction and guarantees eventual homefinding; story generalizes this unsupported navigation rule and never actually resolves return home. Fiction framing does not make the explicit practical moral reliable.'),
('hold','Mail-to-ceiling premise and return snowflake lack a coherent established rule; malformed wondered what his letter would come back. Magical label alone does not repair sentence/causal gaps.'),
('review','Complete apology arc, but fight-with-rock/deaf-rock joke is strained and the disability moral is broader than the actual interaction. No endorsement of mockery.'),
('review','Complete toy-care arc, but spoiled red ball from rain is an odd unexplained property claim; repeated spoiled and generic moral show forced vocabulary.'),
('retain','Simple consistent cleanup sequence and dialogue; complete ending, ordinary repetition only.'),
('review','Dead bug as toy-home narrative uses cell awkwardly for a small box and has an unusual sentimental moral; not a factual resurrection claim or medical instruction.'),
('review','Television splits without an explained cause; buying replacement resolves plot, but careful handling as prevention is unsupported by narrative.'),
('hold','Dizziness supposedly explains an uncovered file and a blanket resolves it; grammatical surface masks disconnected object/task meanings and an incoherent causal premise.'),
('hold','Explicitly defines intelligent as beauty that seems self-aware; semantic word-definition error, beyond ordinary sunset personification.'),
('retain','Coherent spicy-food discomfort and adult help with complete ending; ordinary fictional scene, not assessed or promoted as medical guidance.'),
('hold','Bunny begins printing in a dark forest spot without equipment or established magic; congratulatory ending substitutes for a mechanism or specified task outcome.'),
('retain','Anthropomorphic injury/help attempt thwarted by bird; sad ending is explicit closure, not automatically an incomplete plot. No cure claim.'),
('review','Coherent gift scene but repeated tight friends stretches idiomatic tight with into unnatural adjective use; vocabulary-conditioning artifact.'),
('retain','Explicit magic-flower device consistently resolves fictional singing problem; magical change not evaluated as real-world mechanism.'),
('retain','Consistent wrapped-object movement, reveal and adopted puppy ending; unusual setup remains coherent fiction.'),
('retain','Simple market generosity narrative with stable roles and complete resolution; farm/milk opening is loosely connected but compatible.'),
('review','Complete rescue ending, but stick stuck then rope tied to pole and magic words create poorly explained physical action. Not suitable as literal retrieval instructions.'),
('review','After drawing on new paper, dialogue calls it empty; local object-state inconsistency despite otherwise clear replacement/resolution.'),
('retain','Clear conflict, loss and mutual apology with complete ending; talking ducks are fictional. Bread-feeding scene is not certified wildlife-care guidance.'),
('retain','Clear approach/warning/retreat sequence with parent discouraging contact with a fearful dog; attributed dog thoughts are anthropomorphic fiction, not reliable canine-behavior advice.')]
rows=[json.loads(x) for x in (P/'sample.jsonl').read_text().splitlines()];manifest=json.loads((P/'manifest.json').read_text());assert len(rows)==len(DECISIONS)==32;assert hashlib.sha256((P/'sample.jsonl').read_bytes()).hexdigest()==manifest['sample_sha256']
judgments=[]
for i,(row,(decision,reason)) in enumerate(zip(rows,DECISIONS)):
 judgments.append(dict(sample_index=i,doc_id=row['doc_id'],split=row['split'],quartile=row['quartile'],tokens=row['tokens'],decision=decision,reason=reason,complete_sentence_ending=True,instruction_tool_suitability='Narrative next-token prose only; no verified tool-use or assistant instruction supervision.',external_fact_checking=False))
result=dict(state='manual_review_complete_not_admitted',reviewer='post_ablation_research',review_design='Single unblinded assistant review of32deterministic fresh full stories; content-independent split/quartile selection fixed before reading.',manifest_sha256=hashlib.sha256((P/'manifest.json').read_bytes()).hexdigest(),sample_sha256=manifest['sample_sha256'],counts=dict(collections.Counter(x['decision'] for x in judgments)),by_split={s:dict(collections.Counter(x['decision'] for x in judgments if x['split']==s)) for s in ['train','validation']},judgments=judgments,corpus_modified=False,excluded_ids_applied=False,training_admitted=False,limitations=['Small subjective stratified sample is not a population defect estimate or certification.','Retain means no material issue identified for fictional narrative learning, not verified factual or assistant/tool instruction suitability.','All32end with syntactically complete sentences, but7held documents contain semantic/causal/word-definition failures; sentence completion is insufficient.','No code/system-prompt leakage, raw HTML, navigation text or tool traces observed; formulaic openings/names/morals are prevalent.','No independent external factual verification; fiction and practical teaching claims distinguished explicitly.','Root decides any exclusions/admission; no changes to frozen candidate or validation membership.'])
with (P/'judgments.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'counts':result['counts'],'by_split':result['by_split']}))
