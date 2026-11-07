"""Synthetic verifier checks, no dataset reads."""
import importlib.util,pathlib
p=pathlib.Path(__file__).with_name('verify.py');s=importlib.util.spec_from_file_location('separate',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
t=m.Table();text='one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen'
t.put(m.signature(text),2)
assert t.find(m.signature(text.upper()))=={2}
assert t.find(m.signature(text+' nineteen twenty'))=={2}
assert not t.find(m.signature('separate uncommon words do not meet threshold'))
t.put(m.signature('tiny'),4);assert t.find(m.signature('TINY'))=={4};assert not t.find(m.signature('tiny addition'))
assert m.signature('Ａ\n B')[0]==m.signature('a b')[0]
assert len(m.signature(text)[1])==12
try:m.require(False,'synthetic rejection')
except ValueError:pass
else:raise AssertionError('must reject')
print('8 independent-interpreter synthetic checks PASS; no corpus access')
