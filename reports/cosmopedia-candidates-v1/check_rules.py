"""Fixed prospective positive/negative fixtures, no real source scan."""
from rules import structural_reasons,seed_relation,seed_shingles
CASES=[
 ('complete prose','A seed grows. Rain helps it. ',[]),
 ('complete quotation','She asked, “Can you help?”',[]),
 ('bold sentence','**The end.**',[]),
 ('completed list','First:\n- Bring paper.\n- Write clearly.',[]),
 ('closed code followed sentence','```python\nx=1\n```\nThe example is complete.',[]),
 ('ordinary exercise blanks','Try these exercises: x + 1 = ____.',[]),
 ('fantasy allowed','The dragon flew to a talking tree.',[]),
 ('fact error not detected','Two plus two is five.',[]),
 ('inline backticks','Use `print` to display text.',[]),
 ('long dash prose','The sign says -- stop here.',[]),
 ('unfinished sentence','The teacher explained the',['missing_terminal_sentence_punctuation']),
 ('unfinished heading','A complete paragraph.\n## Next section',['terminal_heading','missing_terminal_sentence_punctuation']),
 ('unclosed fence','An example:\n```python\nx=1',['unclosed_fenced_block','missing_terminal_sentence_punctuation']),
 ('wrong closing fence','```python\nx=1\n~~~\nThe end.',['unclosed_fenced_block']),
 ('symbol degeneration','A lesson. '+('\\_ '*40),['long_symbol_run','missing_terminal_sentence_punctuation']),
 ('insert media','Listen here [Insert link to video here].',['unresolved_insert_placeholder']),
 ('ordinary brackets','The result [shown above] is correct.',[]),
 ('unfinished handoff','Please let me know if you would like me to continue.',['explicit_unfinished_marker']),
 ('continue numbered','Continue to Step 2...',['explicit_unfinished_marker']),
 ('empty','',['empty_text']),
]
for name,text,expected in CASES:assert structural_reasons(text)==sorted(expected),(name,structural_reasons(text),expected)
p='Here is an extract from a webpage:\n"A long seed quoted here."\n\nWrite a lesson.'
assert seed_relation(p)==('a long seed quoted here.','quoted_web_seed')
assert seed_relation('Write a lesson about trees.')[1]=='full_prompt_exact_only'
assert seed_shingles('too short','quoted_web_seed')==[]
assert len(seed_shingles(' '.join('word'+str(i) for i in range(40)),'quoted_web_seed'))==36
print('PASS20 structural fixtures +4 seed extraction/shingle checks; no corpus scan')
