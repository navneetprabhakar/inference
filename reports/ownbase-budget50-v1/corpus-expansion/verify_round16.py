"""Check inspected sparse, scheduler, and interval-selector examples."""
import ast, copy, hashlib, itertools, json, re
from pathlib import Path

root = Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-16')
rows = {r['id']: r for r in map(json.loads, (root/'candidates.jsonl').read_text().splitlines())}

def execute(key, indexes, namespace):
    for i in indexes:
        for code in re.findall(r'```python\n(.*?)```', rows[key]['messages'][i]['content'], re.S):
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module]
                    assert set(names) <= {'copy', 'collections'}
                if isinstance(node, ast.Name):
                    assert node.id not in {'open', 'eval', 'exec', '__import__', 'input', 'compile'}
            exec(compile(tree, 'inspected-corpus', 'exec'), namespace)

sparse = {}; execute('b50-sparse-transpose', [5, 7, 9, 13], sparse)
sparse_checks = 0
for nr, nc in itertools.product(range(4), repeat=2):
    shape = (nr, nc)
    choices = list(itertools.product(range(nr), range(nc), [-1, 0, 1]))
    for n in range(3):
        for triples in itertools.product(choices, repeat=n):
            dense = [[sum(v for r, c, v in triples if (r, c) == (i, j)) for j in range(nc)] for i in range(nr)]
            got_shape, got = sparse['transpose'](shape, triples)
            expected = [(j, i, dense[i][j]) for i in range(nr) for j in range(nc) if dense[i][j]]
            assert got_shape == (nc, nr) and sorted(got) == sorted(expected)
            rm = list(range(nr))[1:] + list(range(nr))[:1]
            cm = list(reversed(range(nc)))
            got_shape, got = sparse['permute'](shape, triples, rm, cm)
            expected = [(i, j, dense[rm.index(i)][cm.index(j)]) for i in range(nr) for j in range(nc) if dense[rm.index(i)][cm.index(j)]]
            assert got_shape == shape and sorted(got) == sorted(expected)
            sparse_checks += 1

schedule = {}; execute('b50-round-robin', [6, 10], schedule)
original = schedule['run']; execute('b50-round-robin', [12], schedule)
scheduler_checks = 0
for count in range(5):
    for values in itertools.product(range(7), repeat=count):
        jobs = list(zip('ABCD', values)); before = copy.deepcopy(jobs)
        # Each slice is independently indexed by round and original input position.
        expected = [(label, min(2, work - 2*k)) for k in range(4) for label, work in jobs if work > 2*k]
        finished = [label for label, work in jobs if work == 0]
        finished += [label for label, work in sorted(jobs, key=lambda p: ((p[1]+1)//2, 'ABCD'.index(p[0]))) if work > 0]
        assert schedule['run'](jobs) == (expected, finished) and jobs == before
        if all(values): assert original(jobs) == (expected, finished)
        scheduler_checks += 1
for runner in (original, schedule['run']):
    for jobs in [[('A', -1)], [('A', True)], [('A', 1.0)], [('A', 1), ('A', 2)], [None]]:
        before = copy.deepcopy(jobs)
        try: runner(jobs)
        except ValueError: pass
        else: raise AssertionError('invalid scheduler input accepted')
        assert jobs == before

selector = {}; execute('b50-ticket-selector', [6, 8, 10], selector)
selector_checks = 0
for weights in itertools.product(range(4), repeat=4):
    items = list(zip('ABCD', weights)); before = copy.deepcopy(items)
    expanded = [label for label, weight in items for _ in range(weight)]
    for ticket, expected in enumerate(expanded):
        assert selector['select'](items, ticket) == expected
        for label, weight in items:
            if weight == 0:
                assert selector['select']([p for p in items if p[0] != label], ticket) == expected
        selector_checks += 1
    assert items == before

report = {'source_sha256': hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),
          'supplied_tests': 'Executed unchanged for both scheduler policies and all selected implementations',
          'independent_sparse_cases': sparse_checks, 'independent_scheduler_cases': scheduler_checks,
          'independent_selector_tickets': selector_checks, 'result': 'pass'}
(root/'code-verification.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
