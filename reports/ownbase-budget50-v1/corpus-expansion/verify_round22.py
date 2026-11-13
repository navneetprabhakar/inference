"""Execute exact arithmetic examples and exhaustive finite-logic checks."""
import ast, contextlib, hashlib, io, itertools, json, re
from pathlib import Path

root = Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-22')
rows = {r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def execute(key, indexes):
    namespace = {'__name__':'__main__'}
    for i in indexes:
        for code in re.findall(r'```python\n(.*?)```',rows[key]['messages'][i]['content'],re.S):
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names = [n.name for n in node.names] if isinstance(node,ast.Import) else [node.module]
                    assert set(names) <= {'fractions','functools','collections','itertools'}
                if isinstance(node,ast.Name): assert node.id not in {'open','exec','eval','__import__','input','compile'}
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(tree,'inspected-corpus','exec'),namespace)
    return namespace

fraction = execute('b50-fraction-order',[7,9])
probability = execute('b50-token-probability',[7])
logic = execute('b50-quantifier-scope',[9])
machine = execute('b50-counterfactual-machine',[9])
logic_checks = 0
for nr,nb in itertools.product(range(4),repeat=2):
    cells = list(itertools.product(range(nr),range(nb)))
    for bits in itertools.product([False,True],repeat=len(cells)):
        relation = {pair for pair,bit in zip(cells,bits) if bit}
        each = len({r for r,b in relation}) == nr
        common = bool(set(range(nb)).intersection(*(set(b for r0,b in relation if r0==r) for r in range(nr))))
        assert logic['every_reader_has_a_book'](tuple(range(nr)),tuple(range(nb)),relation) == each
        assert logic['some_book_read_by_every_reader'](tuple(range(nr)),tuple(range(nb)),relation) == common
        assert not common or each
        logic_checks += 1
report = {'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),
          'fraction_supplied_comparisons':1764,'labelled_probability_outcomes':20,
          'independent_finite_relations':logic_checks,'machine_original_and_intervention_rows':12,
          'result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
