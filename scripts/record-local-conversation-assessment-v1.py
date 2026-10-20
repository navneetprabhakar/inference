"""Record direct judgments after reading all600 complete captured replies losslessly."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/local-conversation-run-v1')
DEV=[
'Independence/probability requests replaced by comprehensive-experience boilerplate and Section loops.',
'Risk-ratio/difference requests replaced by project/email templates; no requested quantities.',
'Logical conclusions about John and football teams replaced by empty team prose.',
'Lena Grant artist role replaced by letters addressed to John/Alex and signed Sarah.',
'Correlation/significance/linear-fit questions replaced by life prose and Section/point repetitions.',
'Aha-moment editing replaced by dog fragments; no usable revised text.',
'Zero Cool/store role replaced by email and Section headers; no character response.',
'Chapter counts replaced by Tim story and Section repetitions; no book quantities.',
'Data-interpretation/median/range requests replaced by circular computer prose.',
'Weighted averages replaced by repeated second-point text, without quantities or comparison.',
'Corn/ethanol/grain questions replaced by cheese/ingredient loops.',
'Mean/sorting checks replaced by assistance boilerplate and second-point loops.',
'Tennis tournament questions replaced by football/world-team loops.',
'Mean/SD/median/visualization requests replaced by water/point loops.',
'Dice probabilities and outcomes not answered; politeness and unrelated hours/garden text.',
'Space-fleet salute/alert role replaced by formal letters and Section headers.',
'Spending/median/correlation requests replaced by financial/project solicitation boilerplate.',
'Pizza/nearest-location requests replaced by address placeholders and email text.',
'Card probabilities replaced by Sarah/team summaries; no numerical answer.',
'Slope questions replaced by tautological second-point loops.',
'Integer/whole-number/notation requests replaced by repeated point text.',
'Composed/recursive/polynomial function tasks replaced by repeated points, without calculations.',
'Grammar/conciseness requests replaced by letters to address placeholders.',
'Heart-rate median/mode questions replaced by repeated point text.',
'Function value/derivative interpretation requests replaced by repeated point text.',
'Company-culture editing replaced by project/Section boilerplate; no supplied-text revision.',
'Card probability and cube arrangement requests replaced by computer loops.',
'Secret-agent role/observations replaced by project letters and Section headers.',
'Sommelier/wine/course role replaced by unrelated friend/project letters.',
'Bat/ball arithmetic replaced by balloons/more-expensive loops without requested answer.',
'Function example and yes/no checks not answered; circular definition/boilerplate.',
'Fairy-godmother role not followed; purported continuation is another unrelated letter.',
'Expectation calculations replaced by repeated second-point prose.',
'Company-policy/affect edits replaced by generic letters and Section text.',
'Paris tour-operator identity/home/specialism not answered; circular city-of-France prose.',
'Dice probabilities and explanations replaced by second-point repetition.',
'Ice-wizard name/action/scene replaced by sun prose and repeated TION fragments.',
'Geometric sequence/series tasks replaced by repeated point text.',
'Jerry/arcade dialogue replaced by formal project letters; no in-scene answer.',
'Water density questions replaced by world/history/cultural-significance text.',
'Student-major percentages/counts replaced by Sarah/project summaries.',
'Nature-wizard identity/home/teacher replaced by sun/park prose.',
'Variable definition/type/central tendency replaced by circular data-analysis statements.',
'Software classifications/examples/BIOS questions replaced by company/project boilerplate.',
'Layoff edit and active-voice explanation replaced by team/park loops.',
'Event probabilities and quiz-average method replaced by people-in-body loops.',
'Modular arithmetic replaced by Earth/capital assertions.',
'Snail explanation replaced by sun/park repetition; no solution.',
'Editing-process/goals requests replaced by project/Section templates.',
'Movie survey insight/percentage/caution requests replaced by circular film prose.',
'COVID paragraph edit and concise formal rewrite replaced by first-time/Sarah loops.',
'Remainder checks replaced by city/capital statements.',
'Information-criteria edit and academic-format questions replaced by project templates.',
'Movie paragraph edits/meaning discussion replaced by book/project/Section templates.',
'Coin combinations replaced by dog descriptions; no relevant denominations.',
'Density/volume/box questions replaced by ball lists.',
'Experimental variables/control/correlation questions replaced by city/history prose.',
'Chef sentence edits and voice benefits replaced by local-community text.',
'Whose/who grammar, one-period constraint and supplied correction not followed.',
'Imaginary-number operations/definition replaced by generic assistance/project prose.',
'Dice probability/decimal/odds requests replaced by letters/placeholders/sections.',
'Function composition/recursion/dice requests replaced by repeated points.',
'Age mean/median/range comparison replaced by city repetition.',
'Theseus definition/views requests replaced by Section/preferences/email boilerplate.',
'Math-activity dialogue replaced by language-creation templates, no proposed math task.',
'Brain mass/cerebrum/corpus-callosum questions replaced by light-energy loops.',
'Unit sales/percentage/distribution questions replaced by business/financial solicitation.',
'Research-agreement/paragraph continuation replaced by environment/project text.',
'Grakk/smuggling favor role replaced by Sarah/project letters.',
'Survey sample/population/proportion requests replaced by planet/team repetitions.',
'Combined means/rate-of-change requests replaced by team/weather solicitation.',
'Arithmetic-sequence type/notation requests replaced by repeated point prose.',
'Tower climb/time/break requests replaced by Sam/ball story fragments.',
'Dice combinations/probabilities replaced by people-count tautologies.',
'Derivatives/equation requests replaced by repeated second-point prose.',
'Harvard employee edit/commas/conciseness requests replaced by letters/headers.',
'Machine-usage weighted averages replaced by people/point repetitions.',
'Logical implications about As/Bs replaced by new-home advice.',
'Anecdotal-evidence/snail/coin requests replaced by language-creation text.',
'Melbourne family/work commute role replaced by generic home/park tips.',
'Police/motorist role replaced by sun/email/project responses.',
'Class naming/PascalCase/camelCase requests replaced by interface/project boilerplate.',
'Mr. Whiskers case replaced by Sarah/friend letters; one-message formatting alone does not satisfy contextual assistance.',
'Coin probability/sum verification replaced by repeated point text.',
'Fibonacci/Binet/golden-ratio requests replaced by repeated points.',
'SD/proportion/normal-rule questions replaced by circular data prose.',
'Guitar salesperson role replaced by Section headers and generic assistance.',
'Philosophy introduction edits replaced by generic concept/Section text.',
'Five-month electricity table/total/average requests replaced by bullet/point repetition.',
'ANOVA name/method/assumption requests replaced by project/security text.',
'SD/coefficient-of-variation formulas replaced by point repetition.',
'Expense/data percentage changes not calculated; company/financial phrases only.',
'Retired-operative dialogue/brief revision replaced by unrelated letters.',
'Bat/ball and coin requests replaced by generic ball/park prose.',
'Object permanence/separation questions replaced by circular function/data prose.',
'Polynomial remainders/roots replaced by Earth/capital statements.',
'Coast Guard distress/rescue dialogue replaced by city/Section letters.',
'Sentence meanings/concise rewrites replaced by Sue/student fragments.',
'Forest-wizard name/mortality/hut questions replaced by sun/beach loops.',
'Age-group mean/median/mode requests replaced by football-team text.'
]
REG={
'greeting_memory':'No requested named greeting, corrected-name-only reply or recall; letters/placeholders/Sara replace the answers.',
'arithmetic':'No requested coin quantity or exact digit; unrelated flower/garden/Section text replaces calculations.',
'extraction':'No requested supplied color, updated owner or object-only reply; blue/green/Sarah/story fragments replace extraction.',
'english_editing':'No requested grammar correction, explanation or exact copy; unrelated letters/stories replace source sentences.',
'professional_style':'Generic formal letters do not preserve the requested item or deadline and fail the one-sentence/shortening requests.',
'caveman_style':'Requested quantity/item/day are lost; unrelated letters and soft-dog lists replace each style transformation.',
'casual_conversation':'No friendly activity question, casual single-sentence reply or Sunday-only recall; formal project letters dominate.',
'basic_knowledge':'No requested basic fact, shorter answer or exact supplied answer; sun/park/Section loops remain.',
'simulated_tool_json':'No requested tool JSON, corrected city or supplied27-degree result; location/park prose is not a tool call.',
'mature_language_and_register':'No requested scenario-specific frustration or concise empathetic rewrite; unrelated adjective lists/letters replace the task.'}
def main():
 if len(DEV)!=100:raise ValueError('All explicit development judgments required')
 integrity=json.loads(Path('reports/local-conversation-run-v1-integrity.json').read_text());rubric=json.loads(Path('configs/current-model-100-conversations-v1.json').read_text())['rubric'];summary={}
 for name in ['development-100','regression-100']:
  target=ROOT/(name+'-direct-judgments.jsonl')
  if target.exists():raise FileExistsError('Preserve direct review journal')
  rows=[json.loads(l) for l in (ROOT/name/'turns.jsonl').open()];judgments=[]
  assert len(rows)==300 and sha(ROOT/name/'turns.jsonl')==integrity['protocols'][name]['turns_sha256']
  for i in range(100):
   rr=rows[i*3:i*3+3];assert [(r['conversation'],r['turn']) for r in rr]==[(i+1,t) for t in [1,2,3]]
   reason=DEV[i] if name=='development-100' else REG[rr[0]['category']]
   judgments.append(dict(conversation=i+1,turn_success=[False,False,False],dimensions=dict(understanding=0,relevance=0,instruction_following=0,context_and_corrections=0,coherence=1),reason=reason,coherence_reason='Some grammatical clauses, but repetition, contradictions or unrelated fragments dominate; this residual coherence credit is not task correctness.',raw_conversation_sha256=digest(rr),full_text_read=True,human_attestation=False,review_mode='direct_expert',review_rendering='Every raw reply read using lossless exact-character repeat runs and text-equal duplicate mappings; no truncation or teacher answer substitution.'))
  with target.open('x') as f:
   for r in judgments:f.write(json.dumps(r,sort_keys=True)+'\n')
  categories={}
  for c in sorted({r['category'] for r in rows}):categories[c]=dict(conversations=sum(rows[i*3]['category']==c for i in range(100)),successful_turns=0,successful_conversations=0)
  report=dict(creator='Navneet Prabhakar',complete=True,protocol=name,model_manifest_sha256=integrity['protocols'][name]['model_manifest_sha256'],successful_conversations=0,conversations=100,successful_turns=0,turns=300,correct_turn_fraction=0.0,mean_score_out_of_100=5.0,rubric=rubric,task_correctness_not_coherence_score=True,categories=categories,judgments=judgments,raw_turns_sha256=sha(ROOT/name/'turns.jsonl'),direct_journal_sha256=sha(target),human_attestation=False,review_mode='direct_expert',production_accepted=False,model_promoted=False,protocol_limitation=('Source-heldout diagnostic includes substantial maths/factual reasoning and noisy/implicit followups; not the primary75%core-English acceptance benchmark. Mechanical one-response/no-period compliance without contextual task fulfilment does not count as correct.' if name=='development-100' else 'Same repeated visible regression suite as paired baseline; not a fresh final test.'))
  out=Path('reports/local-conversation-'+name+'-direct-v1.json');out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');assert out.stat().st_size<100*1024
  summary[name]={k:v for k,v in report.items() if k in ['successful_conversations','conversations','successful_turns','turns','correct_turn_fraction','mean_score_out_of_100']}
 Path('reports/local-conversation-correctness-v1.json').write_text(json.dumps(dict(creator='Navneet Prabhakar',complete=True,models=summary,actual_new_gradient_positions=270359,cumulative_recovery_physical_positions=1776439,retention_passed=False,conversation_target_met=False,model_promoted=False,no_gcp=True,teacher_calls=0),indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
