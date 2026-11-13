"""Check the stated distance rule against independent alternating-turn graph search."""
import collections, hashlib, itertools, json
from pathlib import Path

root = Path('runs/ownbase-budget50-v1/corpus-expansion/extensions-17')
adj = {'Gate':['Hall'], 'Hall':['Gate','Vault','Tower'], 'Vault':['Hall'], 'Tower':['Hall']}
distance = {'Gate':2, 'Hall':1, 'Vault':2, 'Tower':0}
checks = 0
for ash, bo, energy, turn in itertools.product(adj, adj, range(7), range(2)):
    pending = collections.deque([(ash, bo, energy, turn)])
    seen = set(pending)
    won = False
    while pending:
        a, b, e, t = pending.popleft()
        if a == b == 'Tower' and e >= 1:
            won = True
            break
        successors = [(a, b, e, 1-t)]  # A legal skipped turn.
        if e:
            successors += [(n,b,e-1,1-t) if t == 0 else (a,n,e-1,1-t)
                           for n in adj[a if t == 0 else b]]
        for state in successors:
            if state not in seen:
                seen.add(state)
                pending.append(state)
    assert won == (energy >= distance[ash]+distance[bo]+1)
    checks += 1
report = {'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),
          'boardgame_independent_graph_search_states':checks, 'result':'pass'}
target = root/'code-verification.json'
if target.exists(): assert json.loads(target.read_text()) == report
else: target.write_text(json.dumps(report, indent=2)+'\n')
print(f'{checks} independent alternating-turn states pass.')
