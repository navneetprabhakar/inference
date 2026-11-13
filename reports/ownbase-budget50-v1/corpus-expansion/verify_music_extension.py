"""Check the reviewed worksheet validator against a declarative prefix oracle."""
import ast, copy, hashlib, io, itertools, json, re, unittest
from pathlib import Path

root = Path('runs/ownbase-budget50-v1/corpus-expansion/extensions-19')
row = json.loads((root/'candidates.jsonl').read_text())
namespace = {'__name__':'reviewed_fixture'}
for code in re.findall(r'```python\n(.*?)```', row['messages'][-1]['content'], re.S):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): assert [n.name for n in node.names] == ['unittest']
        if isinstance(node, ast.ImportFrom): raise AssertionError('Unexpected import')
        if isinstance(node, ast.Name): assert node.id not in {'open','exec','eval','__import__','input','compile'}
    exec(compile(tree, 'inspected-worksheet', 'exec'), namespace)
result = unittest.TextTestRunner(stream=io.StringIO()).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(namespace['WorksheetCheckerTests']))
assert result.wasSuccessful() and result.testsRun == 6
checks = 0
for symbols in itertools.product('X–~', repeat=8):
    bars = [list(symbols[:4]), list(symbols[4:])]
    before = copy.deepcopy(bars)
    expected = [(b+1,p+1) for b,bar in enumerate(bars) for p,s in enumerate(bar)
                if s == '~' and not ''.join(bar[:p]).rstrip('~').endswith('X')]
    assert namespace['invalid_holds'](bars) == expected and bars == before
    checks += 1
report = {'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),
          'supplied_unittests':result.testsRun, 'independent_two_bar_sequences':checks, 'result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
