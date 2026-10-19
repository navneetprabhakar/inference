"""Build expanded exclusions and scan the retained next-corpus ingredients."""
# Creator: Navneet Prabhakar
import json
from collections import Counter
from pathlib import Path
from slm.data.evaluation_exclusions import compile_inventory, EvaluationExclusions
from slm.data.prose_screen import RequestGuard
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.cases import candidate_suite
from slm.eval.tool_cases import tool_cases

ROOT = Path('data/evaluation-exclusions-v2')
PLAN = Path('configs/evaluation-exclusions-build-v2.json')


def read(p): return json.loads(Path(p).read_text())
def lines(p): return [json.loads(s) for s in Path(p).read_text().splitlines()]
def save(p, v): p.write_text(json.dumps(v, indent=2, sort_keys=True) + '\n')


def main():
    plan = read(PLAN)
    if ROOT.exists(): raise FileExistsError('Retain existing exclusion-build evidence')
    for p, h in plan['input_bindings'].items():
        if sha(p) != h: raise ValueError('Pinned input differs: ' + p)
    records = []; legacy = []
    def add(kind, text, origin): records.append(dict(kind=kind, text=text, origin=origin))
    for c in candidate_suite()['cases']:
        for i, m in enumerate(c['messages']):
            if m['role'] == 'user':
                legacy.append(m['content']); add('request', m['content'], c['id'] + '/message/' + str(i))
    for c in tool_cases():
        for i, m in enumerate(c['history']):
            if m['role'] == 'user':
                legacy.append(m['content']); add('request', m['content'], c['scenario_id'] + '/message/' + str(i))
    for p in plan['prior_interviews']:
        for r in lines(p):
            origin = p + '/turn/' + str(r['turn'])
            legacy.append(r['user']); add('request', r['user'], origin + '/user')
            add('generated_response', r['response']['text'], origin + '/assistant')
    prior = read('data/fineweb-prose-screen-v1/plan.json')
    old_guard = RequestGuard(legacy)
    if len(old_guard.requests) != 190 or old_guard.fingerprint != prior['protected_request_fingerprint']:
        raise ValueError('Complete historical request reconstruction differs')
    for c in read('configs/current-model-100-conversations-v1.json')['conversations']:
        for i, t in enumerate(c['turns'], 1):
            add('request', t['user'], 'current-100/' + str(c['id']) + '/' + str(i) + '/user')
    for r in lines('data/current-model-100-conversations-v1/turns.jsonl'):
        stem = 'current-100/' + str(r['conversation']) + '/' + str(r['turn'])
        add('request', r['user'], stem + '/actual-user')
        add('generated_response', r['response']['text'], stem + '/actual-assistant')
    for r in lines('data/conversation-collapse-diagnostic-v1/measurements.jsonl'):
        if r['kind'] == 'same_prompt_generation':
            stem = 'collapse/' + r['branch'] + '/' + str(r['case'])
            add('request', r['user'], stem + '/user')
            add('generated_response', r['response']['text'], stem + '/assistant')
    fixtures = {c['id']: c for c in candidate_suite()['cases']}
    for p in plan['fresh_session_responses']:
        for i, r in enumerate(lines(p)):
            fixture = fixtures[r['case_id']]
            for j, message in enumerate(fixture['messages']):
                if message['role'] == 'user':
                    add('request', message['content'], p + '/row/' + str(i) + '/message/' + str(j))
            add('generated_response', r['response']['text'], p + '/row/' + str(i) + '/assistant')
    inventory = compile_inventory(records, plan['input_bindings'])
    ROOT.mkdir(); save(ROOT / 'plan.json', plan); save(ROOT / 'inventory.json', inventory)
    guard = EvaluationExclusions(ROOT / 'inventory.json', sha(ROOT / 'inventory.json'))
    # Every supplied source record must match its own registered text and kind.
    for record in records:
        matches = guard.matches(record['text'])
        if not any(record['origin'] in m['origins'] and record['kind'] in m['kinds'] for m in matches):
            raise ValueError('Incomplete actual source coverage')
    scans = []; seen = {}; counts = Counter(); blocked = Counter()
    for p in plan['raw_source_rows']:
        for r in lines(p):
            key = r['source_group']
            if digest(r['row']) != r['raw_record_sha256']: raise ValueError('Raw snapshot differs')
            if key in seen:
                if seen[key] != r['raw_record_sha256']: raise ValueError('Conflicting source identity')
                continue
            seen[key] = r['raw_record_sha256']; source = key.split(':', 1)[0]
            result = guard.inspect_record(r['row'])
            scans.append(dict(source_group=key, source=source, **result))
            counts[source] += 1; blocked[source] += int(result['blocked'])
    with (ROOT / 'scan.jsonl').open('x') as stream:
        for r in scans: stream.write(json.dumps(r, sort_keys=True) + '\n')
    for p, h in plan['input_bindings'].items():
        if sha(p) != h: raise ValueError('Input changed while building/scanning')
    report = dict(creator='Navneet Prabhakar', kind='actual-expanded-evaluation-exclusions-v1',
        inventory_sha256=sha(ROOT / 'inventory.json'), plan_sha256=sha(PLAN),
        scan_sha256=sha(ROOT / 'scan.jsonl'), builder_sha256=sha(__file__),
        source_records=len(records), historical_distinct_requests=190,
        distinct_texts=inventory['distinct_texts'], fingerprint=inventory['fingerprint'],
        distinct_requests=sum('request' in r['kinds'] for r in inventory['entries']),
        distinct_generated_replies=sum('generated_response' in r['kinds'] for r in inventory['entries']),
        all_registered_records_self_match=True, actual_records_scanned=len(scans),
        source_counts=dict(counts), blocked_by_source=dict(blocked),
        blocked_records=sum(r['blocked'] for r in scans), training_approved=False,
        scope=inventory['scope'], previous_releases_unchanged=True,
        caveat='No retroactive independence claim: some generated replies reproduce control training text. These are conservative exclusions for future intake. Short canonical oracle labels are not global bans; protected full requests remain registered.')
    save(ROOT / 'report.json', report)
    save(Path('reports/evaluation-exclusions-actual.json'), report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
