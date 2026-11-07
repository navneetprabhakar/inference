"""Tiny synthetic CPU checks only; no corpus access."""
import importlib.util,pathlib
p=pathlib.Path(__file__).with_name('build.py');s=importlib.util.spec_from_file_location('packing',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a='alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon'
o=m.Overlap();o.add(m.features(a),7)
assert o.matches(m.features('  '+a.upper()+'  '))=={7}
assert not o.matches(m.features('violet tulip bird river fork cloud red apple green pear'))
assert o.matches(m.features(a+' extra ending'))=={7}
assert m.features('Ａ  B')[0]==m.features('a b')[0]
o.add(m.features('short'),9);assert o.matches(m.features('SHORT'))=={9}
assert not o.matches(m.features('short extra'))
assert m.seed('Here is an extract from a webpage:\n"A seed."\n\nWrite a lesson.')=='A seed.'
assert m.seed('Other prompt')=='Other prompt'
print('8 synthetic overlap/normalization/seed checks PASS; no corpus access')
