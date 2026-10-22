import json
from pathlib import Path
from bs4 import BeautifulSoup
from dom_renderer import render_block_text,render_html
CASES=[
('split_word','<p>Onl<span>in</span>e in<span>formation</span>.</p>','Online information.'),
('inline_link','<p>a<a href="x">dja</a>cent</p>','adjacent'),
('punctuation','<p>Hello<a href="x">,</a> world<span>!</span></p>','Hello, world!'),
('source_spaces','<p>one <b>two</b> three</p>','one two three'),
('leading_space_in_link','<p>one<a href="x"> two</a></p>','one two'),
('trailing_space_in_link','<p><a href="x">one </a>two</p>','one two'),
('space_in_empty_span','<p>one<span> </span>two</p>','one two'),
('empty_inline','<p>one<span></span>two</p>','onetwo'),
('source_wrap','<p>one\n\t<b>two</b>\r\nthree</p>','one two three'),
('br','<p>one<br>two<br/>three</p>','one\ntwo\nthree'),
('repeated_br','<p>one<br><br>two</p>','one\n\ntwo'),
('br_trim','<p>one <br> two</p>','one\ntwo'),
('nested_blocks','<blockquote><p>first</p><p>second</p></blockquote>','first\n\nsecond'),
('list_boundaries','<li>first<ul><li>child1</li><li>child2</li></ul>last</li>','first\n\nchild1\nchild2\n\nlast'),
('pre','<pre>  a  b\n    c\n</pre>','  a  b\n    c\n'),
('pre_inline_tokens','<pre><span>let</span> <b>x</b> = 1;\n<span>print</span>(x)</pre>','let x = 1;\nprint(x)'),
('pre_inline_word','<pre>val<span>ue</span> = 3</pre>','value = 3'),
('inline_code','<p>path/<code>file</code>.txt</p>','path/file.txt'),
('entities','<p>A&amp;B&nbsp;C</p>','A&B\u00a0C'),
('unicode_combining','<p>caf<span>e\u0301</span></p>','cafe\u0301'),
('comments','<p>co<!-- annotation -->herent</p>','coherent'),
('script','<p>one<script>bad()</script>two</p>','onetwo'),
('math_hold','<p>x=<math><mi>y</mi></math>.</p>','x=[MATH REQUIRES REVIEW].'),
('table_hold','<table><tr><td>a</td><td>b</td></tr></table>','[TABLE REQUIRES REVIEW]'),
('superscript','<p>x<sup>2</sup> and H<sub>2</sub>O</p>','x2 and H2O'),
('no_guessed_spaces','<p>red<span>blue</span></p>','redblue')]
results=[]
for name,html,expected in CASES:
 soup=BeautifulSoup(html,'lxml');node=(soup.body or soup).find()
 got=render_block_text(node);assert got==expected,(name,repr(got),repr(expected));results.append(name)
r=render_html('<p>first</p><p>second</p>');assert [x['text'] for x in r['blocks']]==['first','second'] and r['text']=='first\n\nsecond';results.append('paragraphs_remain_distinct')
r=render_html('<p>x<math><mi>y</mi></math></p><table><tr><td>a</td></tr></table>');assert set(r['holds'])=={'math_requires_lossless_representation','table_structure_requires_review'};results.append('math_table_holds')
assert r['original_html']=='<p>x<math><mi>y</mi></math></p><table><tr><td>a</td></tr></table>';results.append('original_html_preserved')
r=render_html('<p>x<sup>2</sup> and H<sub>2</sub>O</p>');assert 'inline_script_format_requires_review' in r['holds'];results.append('sup_sub_format_held')
out={'status':'PASS_SYNTHETIC_RENDERING_ONLY','checks':len(results),'cases':results,'training_admitted':False}
Path(__file__).with_name('synthetic-result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
