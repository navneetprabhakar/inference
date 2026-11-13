"""Execute reviewed examples and bounded independent parser/state/geometry oracles."""
import ast, collections, contextlib, copy, hashlib, io, itertools, json, re
from pathlib import Path

root = Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-20')
rows = {r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def execute(key, indexes, namespace, main=False):
    namespace['__name__'] = '__main__' if main else 'reviewed_fixture'
    for i in indexes:
        for code in re.findall(r'```python\n(.*?)```',rows[key]['messages'][i]['content'],re.S):
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import,ast.ImportFrom)):
                    names = [n.name for n in node.names] if isinstance(node,ast.Import) else [node.module]
                    assert set(names) <= {'copy','collections'}
                if isinstance(node,ast.Name): assert node.id not in {'open','eval','exec','__import__','input','compile'}
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(tree,'inspected-corpus','exec'),namespace)

parser = {}; execute('b50-log-sections',[6],parser)
parser_checks = 0
for seq in itertools.product(['[a]','[b]','x=1','y=2'],repeat=6):
    expected = {}; current = None; bad = None
    for n,line in enumerate(seq,1):
        if line[0] == '[':
            current = line[1]; expected.setdefault(current,{})
        elif current is None or line[0] in expected[current]:
            bad = n; break
        else: expected[current][line[0]] = line[-1]
    try: actual = parser['parse']('\n'.join(seq))
    except ValueError as exc: assert bad is not None and str(exc).startswith(f'Line {bad}:')
    else: assert bad is None and actual == expected
    parser_checks += 1
assert parser['parse'](' # comment\n[ a ]\nx = abc=def== # literal\nempty =') == {'a':{'x':'abc=def== # literal','empty':''}}
for text,line in [('[broken\nx=1',1),('[ ]',1),('[a]\n =value',2),('[a]\nx=1\n[a]\nx=2',4)]:
    try: parser['parse'](text)
    except ValueError as exc: assert str(exc).startswith(f'Line {line}:')
    else: raise AssertionError('Expected parse error')

buffer = {}; execute('b50-circular-buffer',[6,8],buffer)
original = buffer['Buffer']; execute('b50-circular-buffer',[10],buffer)
buffer_checks = 0
choices = [('append',None),('append','A'),('pop',None),('resize',1),('resize',2),('resize',3)]
for capacity in range(1,4):
    for seq in itertools.product(choices,repeat=5):
        b = buffer['Buffer'](capacity); expected = []; cap = capacity
        for op,value in seq:
            if op == 'append':
                b.append(value); expected = (expected+[value])[-cap:]
            elif op == 'resize':
                b.resize(value); cap = value; expected = expected[-cap:]
            elif expected: assert b.pop() == expected.pop(0)
            else:
                try: b.pop()
                except IndexError: pass
                else: raise AssertionError('Empty pop accepted')
            assert b.snapshot() == expected
            snapshot = b.snapshot(); snapshot.clear(); assert b.snapshot() == expected
        buffer_checks += 1
for invalid in [0,-1,True,1.2]:
    b = buffer['Buffer'](2); b.append('retained')
    try: b.resize(invalid)
    except ValueError: pass
    else: raise AssertionError('Invalid resize accepted')
    assert b.snapshot() == ['retained']

rect = {}; execute('b50-rectangle-intersection',[5,7,9,15],rect,main=True)
pairs = [(a,b) for a in range(-1,2) for b in range(a,2)]
rectangles = [(x0,y0,x1,y1) for (x0,x1),(y0,y1) in itertools.product(pairs,repeat=2)]
geometry_checks = 0
for a,b in itertools.product(rectangles,repeat=2):
    assert rect['intersect'](a,b) == rect['cell_intersection'](a,b)
    geometry_checks += 1

window = {}; execute('b50-monotone-window',[5,7],window)
event_counts = window['counts']; execute('b50-monotone-window',[13],window)
window_checks = 0
for stamps in itertools.combinations_with_replacement(range(4),4):
    for kinds in itertools.product(['query','a','b'],repeat=4):
        ops = [('query',t) if k == 'query' else ('event',t,k) for t,k in zip(stamps,kinds)]
        before = copy.deepcopy(ops)
        for width in range(4):
            expected = []
            for i,op in enumerate(ops):
                expected.append(dict(collections.Counter(x[2] for x in ops[:i+1] if x[0]=='event' and op[1]-width<x[1]<=op[1])))
            assert window['model'](ops,width) == expected == window['history_oracle'](ops,width)
            events = [(op[1],op[2]) for op in ops if op[0]=='event']
            want = dict(collections.Counter(c for t,c in events if events[-1][0]-width<t<=events[-1][0])) if events else {}
            assert event_counts(events,width) == want and ops == before
            window_checks += 1
for ops in [[('query',2),('event',1,'a')],[('event',True,'a')],[('event',1,[])],[('query',1,'extra')]]:
    before = copy.deepcopy(ops)
    for fn in [window['model'],window['history_oracle']]:
        try: fn(ops,2)
        except ValueError: pass
        else: raise AssertionError('Invalid window operation accepted')
    assert ops == before
report = {'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),
          'parser_independent_sequences':parser_checks,'buffer_independent_sequences':buffer_checks,
          'rectangle_cell_oracle_pairs':geometry_checks,'window_independent_sequences':window_checks,
          'supplied_examples':'Executed unchanged, including overflow-excluded geometry example', 'result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
