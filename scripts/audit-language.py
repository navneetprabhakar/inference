#!/usr/bin/env python3
"""Real random-student negative controls; no model training or teacher calls."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from collections import Counter
import argparse
import json
from pathlib import Path
import tempfile
import numpy as np
from slm.common.config import Config,initialize
from slm.common.checkpoint import save
from slm.common.tokenizer import train_core
from slm.inference.greedy import GreedyModel
from slm.data.tokenized import sha
from slm.data.schema import digest
from slm.eval.cases import candidate_suite
from slm.eval.conversation import write_new,suite_review_packet,evaluate,score,output_review_packet
from slm.eval.stage import assess
from slm.eval.portability import memory_snapshot


def run(output,artifacts,backend='mlx',full=False):
    output=Path(output);artifacts=Path(artifacts)
    if output.exists() or artifacts.exists():raise FileExistsError('Fresh output and artifact destinations required')
    artifacts.mkdir(parents=True)
    suite=candidate_suite()
    if full:
        suite=deepcopy(suite);suite['suite_id']='english-stratified-ten-candidates-v1'
        suite['cases']=suite['cases'][::50];suite['scope']='Ten cases, one per template family, professional control only; not the complete candidate suite'
    policy=json.loads(Path('configs/stage-screen-proposal-v1.json').read_text())
    review=suite_review_packet(suite);write_new(artifacts/'suite.json',suite);write_new(artifacts/'suite-review.json',review)
    rng=np.random.default_rng(1701)
    # Tokenizer text is independent opaque random words, never evaluation messages/references.
    words=[''.join(rng.choice(list('abcdefghijklmnopqrstuvwxyz'),12)) for _ in range(24000 if full else 1000)]
    config=Config(**json.loads(Path('configs/target-81m.json').read_text())) if full else None
    bpe=train_core([' '.join(words)]*2,config.vocab_size if full else 512,min_frequency=1)
    if full and bpe.vocab_size!=config.vocab_size:raise ValueError('Synthetic tokenizer missed full-size vocabulary')
    config=config or Config(vocab_size=bpe.vocab_size,max_seq_len=512)
    with tempfile.TemporaryDirectory(prefix='slm-language-negative-') as temp:
        root=Path(temp);bpe.save(root/'tokenizer',{'scope':'Independent synthetic mechanics tokenizer, not a production candidate'})
        save(root/'model',config,initialize(config,1703))
        model=GreedyModel(root/'model',root/'tokenizer',backend,expected_tokenizer_hash=sha(root/'tokenizer/manifest.json'))
        results=evaluate(suite,model,8 if full else 32)
        write_new(artifacts/'results.json',results);write_new(artifacts/'output-review.json',output_review_packet(suite,results))
        scored=score(suite,results);decision=assess(suite,results,policy)
        write_new(artifacts/'score.json',scored);write_new(artifacts/'stage.json',decision)
        if scored['overall']['exact_passes']!=0 or decision['decision']=='screen_passed':raise AssertionError('Random negative control unexpectedly passed; inspect before acceptance')
        report={'synthetic_only':True,'random_student':True,'neural_training_updates':0,'teacher_calls':0,'parameters':config.parameter_count,
            'suite_hash':digest(suite),'suite_cases':len(suite['cases']),'suite_reviews_approved':0,'human_output_grades':0,
            'identity':results['identity'],'max_new_tokens':results['max_new_tokens'],'overall':scored['overall'],
            'slices':scored['slices'],'styles':scored['styles'],'reference_loss':scored['reference_loss'],'latency':scored['latency'],
            'decision':decision['decision'],'failed_checks':decision['failed_checks'],'missing_evidence':decision['missing_evidence'],
            'raw_stop_reasons':dict(Counter(r['response']['stop_reason'] if r['response'] else 'generation_error' for r in results['records'])),
            'production_accepted':False,'memory':memory_snapshot(backend,'cpu'),'model_and_tokenizer_temporary_removed':True,
            'artifact_sha256':{str(p):sha(p) for p in sorted(artifacts.iterdir())},
            'scope':'Evaluator negative-control mechanics, not student capability or a trained-checkpoint baseline. Candidate reviews and stage policy remain pending.'}
    write_new(output,report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--artifacts',required=True)
    p.add_argument('--backend',choices=['torch','mlx'],default='mlx');p.add_argument('--full',action='store_true')
    a=p.parse_args();r=run(a.output,a.artifacts,a.backend,a.full)
    print(json.dumps({'cases':r['suite_cases'],'parameters':r['parameters'],'exact_passes':r['overall']['exact_passes'],
        'reference_scored':r['reference_loss']['scored_cases'],'decision':r['decision']},indent=2))


if __name__=='__main__':main()
