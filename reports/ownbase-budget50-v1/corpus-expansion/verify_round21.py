"""Check inspected trees, tombstone reducers and code-point group operations."""
import ast, copy, hashlib, itertools, json, re
from pathlib import Path

root = Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-21')
rows = {r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def execute(key, indexes, namespace):
    for i in indexes:
        for code in re.findall(r'```python\n(.*?)```',rows[key]['messages'][i]['content'],re.S):
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names = [n.name for n in node.names] if isinstance(node,ast.Import) else [node.module]
                    assert set(names) <= {'copy','itertools'}
                if isinstance(node,ast.Name): assert node.id not in {'open','exec','eval','__import__','input','compile'}
            exec(compile(tree,'inspected-corpus','exec'),namespace)

outline = {}; execute('b50-outline-tree',[5,7,11],outline)
outline_checks = 0
for depths in itertools.product(range(4),repeat=6):
    text = '\n'.join('  '*d+str(i) for i,d in enumerate(depths))
    valid = depths[0] == 0 and all(b <= a+1 for a,b in zip(depths,depths[1:]))
    try: forest = outline['parse'](text)
    except ValueError: assert not valid
    else:
        assert valid and outline['flatten'](forest) == [(str(i),d) for i,d in enumerate(depths)]
        # Enumerate actual tree paths, then independently check each named index.
        def visit(nodes, prefix=()):
            for i,node in enumerate(nodes):
                path = prefix+(i,)
                assert outline['select_node'](forest,path) is node
                visit(node['children'],path)
        visit(forest)
    outline_checks += 1

reservation = {}; execute('b50-cancelled-reservations',[6,8],reservation)
events = [{'type':'cancel','id':name} for name in 'ab']
events += [{'type':'create','id':name,'quantity':q} for name,q in itertools.product('ab',[1,2])]
reservation_checks = 0
for seq in itertools.product(events,repeat=5):
    before = copy.deepcopy(seq)
    creates = {name:{e['quantity'] for e in seq if e['id']==name and e['type']=='create'} for name in 'ab'}
    conflict = any(len(q)>1 for q in creates.values())
    cancelled = {e['id'] for e in seq if e['type']=='cancel'}
    expected_creates = {name:next(iter(q)) for name,q in creates.items() if q}
    expected = {'creates':expected_creates,'tombstones':cancelled,
                'active':{name:q for name,q in expected_creates.items() if name not in cancelled}}
    try: actual = reservation['reduce_events'](seq)
    except ValueError: assert conflict
    else: assert not conflict and actual == expected
    assert seq == before
    reservation_checks += 1

rle = {}; execute('b50-run-length-offsets',[5,7,9,11],rle)
rle_checks = 0
choices = list(itertools.product(['a',' ','é'],[1,2]))
for count in range(4):
    for groups in itertools.product(choices,repeat=count):
        groups = list(groups); before = copy.deepcopy(groups)
        text = ''.join(ch*n for ch,n in groups)
        assert rle['decode'](groups) == text
        expected_encoding = [(ch,len(list(xs))) for ch,xs in itertools.groupby(text)]
        assert rle['encode'](text) == expected_encoding
        positions = [(i,j) for i,(_,n) in enumerate(groups) for j in range(n)]
        for offset,expected in enumerate(positions): assert rle['locate'](groups,offset) == expected
        for offset in range(len(text)+1):
            left,right = rle['split_at_offset'](groups,offset)
            assert rle['decode'](left) == text[:offset] and rle['decode'](right) == text[offset:]
            normal = rle['split_at_offset'](groups,offset,normalize=True)
            assert normal == ([(ch,len(list(xs))) for ch,xs in itertools.groupby(text[:offset])],
                              [(ch,len(list(xs))) for ch,xs in itertools.groupby(text[offset:])])
            rle_checks += 1
        assert groups == before
report = {'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),
          'outline_depth_sequences':outline_checks,'reservation_event_sequences':reservation_checks,
          'rle_split_boundaries':rle_checks,'supplied_tests':'Executed unchanged','result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
