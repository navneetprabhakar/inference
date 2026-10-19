#!/usr/bin/env python3
"""Record a small actual-student development baseline after the fixed NLL score."""
# Creator: Navneet Prabhakar
from pathlib import Path
import json
from slm.inference.greedy import GreedyModel
from slm.data.tokenized import sha


def main():
    root = Path('data/context-research-run-v1')
    report = json.loads((root/'report.json').read_text())
    run = json.loads((root/'run.json').read_text())
    nll = json.loads(Path('reports/milestone-forty-two-heldout-smoke.json').read_text())
    if (report['status'] != 'data_exhausted_before_target' or nll['run_report_sha256'] != sha(root/'report.json')
        or nll['plan_hash'] != run['plan_hash']):
        raise ValueError('Complete run and previously recorded fixed NLL comparison required')
    spec = json.loads((root/'spec.json').read_text())
    model = Path(report['latest_checkpoint'])/'state/model'
    if nll['model_manifest_sha256'] != sha(model/'manifest.json'):
        raise ValueError('Development checkpoint differs from the scored checkpoint')
    case_path = Path('configs/foundation-development-probes-v1.json')
    cases = json.loads(case_path.read_text())
    out = Path('reports/milestone-forty-two-development-probes.json')
    if out.exists():
        raise FileExistsError(out)
    student = GreedyModel(model, spec['tokenizer'], 'mlx', 'default',
        expected_tokenizer_hash=run['logical_plan']['tokenizer_hash'],
        embedding_implementation=spec['recipe']['embedding_implementation'])
    rows = []
    for case in cases['cases']:
        result = student.generate(case['messages'], cases['max_new_tokens'])
        exact_text = result['text'].strip() == case['expected_exact']
        normal_stop = result['stop_reason'] in ('message_end', 'eos')
        rows.append(dict(id=case['id'], expected_exact=case['expected_exact'],
                         exact_text_passed=exact_text, terminated_normally=normal_stop,
                         exact_passed=exact_text and normal_stop, **result))
    result = dict(version=1, creator='Navneet Prabhakar', scope=cases['scope'],
                  protocol_sha256=sha(case_path), script_sha256=sha(__file__), student=student.identity,
                  run_report_sha256=sha(root/'report.json'), cases=rows,
                  exact_passes=sum(r['exact_passed'] for r in rows), denominator=len(rows),
                  new_training_updates=0, teacher_calls=0, production_accepted=False,
                  limitations=cases['limitations'])
    with out.open('x') as f:
        f.write(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)+'\n')
    print(json.dumps({'exact_passes':result['exact_passes'], 'denominator':len(rows)}))


if __name__ == '__main__':
    main()
