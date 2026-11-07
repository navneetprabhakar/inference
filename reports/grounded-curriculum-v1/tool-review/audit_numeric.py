"""Independent descriptive audit; never an admission/semantic PASS receipt."""
import collections
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[3]
NUMBER = re.compile(r'(?<![\w.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')
SCALES = {'mm': Fraction(1, 1000), 'cm': Fraction(1, 100), 'm': 1,
          'km': 1000, 'g': 1, 'kg': 1000, 'ml': 1, 'l': 1000,
          's': 1, 'min': 60, 'h': 3600, 'day': 86400}

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def audit(name):
    directory = ROOT/'data'/name
    dbpath = directory/'candidates.sqlite'
    counts = collections.Counter()
    examples = []
    units = collections.defaultdict(set)
    with sqlite3.connect(f'file:{dbpath}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        assert db.execute('pragma integrity_check').fetchone()[0] == 'ok'
        for row in db.execute('select * from documents order by doc_id'):
            task = json.loads(row['task_json'])
            lesson = json.loads(row['original_lesson_json'])
            answers = [m['text'] for m in lesson['history'] if m['role'] == 'assistant' and 'text' in m]
            assert len(answers) == len(task['turns'])
            counts['lessons'] += 1
            prior = []
            for turn, answer in zip(task['turns'], answers):
                for call in turn['calls']:
                    proposal, observed = call['proposal'], call['observation']
                    a = proposal['arguments']
                    counts['observations'] += 1
                    if proposal['name'] == 'convert':
                        units[row['split']].add((a['from'], a['to']))
                    if observed['source'] == 'offline fixture':
                        if proposal['name'] == 'calculate':
                            x, y = Fraction(str(a['a'])), Fraction(str(a['b']))
                            if a['op'] == 'divide' and y == 0:
                                assert not observed['ok'] and observed['error'] == 'division by zero'
                                counts['verified_zero_errors'] += 1
                                prior.append(observed)
                                continue
                            expected = {'add': lambda: x+y, 'subtract': lambda: x-y,
                                        'multiply': lambda: x*y, 'divide': lambda: x/y}[a['op']]()
                        else:
                            expected = Fraction(str(a['value'])) * SCALES[a['from']] / SCALES[a['to']]
                        assert observed['ok'] and math.isclose(float(expected), observed['data']['result'], rel_tol=1e-12, abs_tol=1e-12)
                        counts['independent_numeric_checks'] += 1
                    else:
                        fixture = turn['policy']['fixture']
                        assert proposal == turn['policy']['fixture_for']
                        assert observed['source'] == 'synthetic recorded fixture'
                        if 'result' in fixture:
                            assert observed['ok'] and observed['data']['result'] == fixture['result']
                        else:
                            assert not observed['ok'] and observed['error'] == fixture['error']
                        counts['verified_explicit_fixture_bindings'] += 1
                    prior.append(observed)
                rule = turn['answer_rule']['kind']
                expected_numbers = None
                if rule == 'last_observation':
                    assert prior[-1]['ok']
                    expected_numbers = [prior[-1]['data']['result']]
                elif rule == 'recall':
                    expected_numbers = [task['parameters']['a'], prior[-1]['data']['result']]
                elif rule == 'recap':
                    expected_numbers = [r['data']['result'] for r in prior]
                elif rule == 'correction':
                    expected_numbers = [task['parameters']['a']+.5, prior[-1]['data']['result']]
                if expected_numbers is not None:
                    got = [Fraction(x.group()) for x in NUMBER.finditer(answer)]
                    expected = [Fraction(str(x)) for x in expected_numbers]
                    counts['numeric_readback_answers'] += 1
                    if got != expected:
                        counts['nonexact_readback_answers'] += 1
                        if len(examples) < 6:
                            examples.append(dict(doc_id=row['doc_id'], answer=answer,
                                                 observed_numbers=expected_numbers))
    return dict(source=name, database_sha256=digest(dbpath),
                manifest_sha256=digest(directory/'candidate-manifest.json'),
                counts=dict(counts), unit_directions={k: sorted(v) for k,v in units.items()},
                nonexact_examples=examples)

if __name__ == '__main__':
    result = dict(state='independent_descriptive_audit_not_admission',
                  method='All retained observations recomputed with independent Fraction operations and conversion factors; all numeric readback strings compared with actual observations. No builder imports. Natural-language/framing verification is separate.',
                  sources=[audit('grounded-tool-candidates-v1'), audit('grounded-session-candidates-v1')])
    out = Path(__file__).with_name('numeric-audit-v1.json')
    with out.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps([x['counts'] for x in result['sources']]))
