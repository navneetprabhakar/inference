"""CLI for candidate suite, raw generation, human packets and stage screens."""
import argparse
import json
from pathlib import Path
from slm.eval.cases import candidate_suite
from slm.eval.conversation import write_new,suite_review_packet,evaluate,score,output_review_packet
from slm.eval.stage import assess


def read(path):return json.loads(Path(path).read_text()) if path else None


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('candidates');a.add_argument('--output',required=True);a.add_argument('--review',required=True)
    a=sub.add_parser('run');a.add_argument('--suite',required=True);a.add_argument('--model',required=True);a.add_argument('--tokenizer',required=True)
    a.add_argument('--tokenizer-hash',required=True);a.add_argument('--backend',choices=['mlx','torch'],default='torch');a.add_argument('--device',default='cpu')
    a.add_argument('--max-new-tokens',type=int,default=64);a.add_argument('--embedding',choices=['native-gather-v1','dense-onehot-v1'],default='native-gather-v1');a.add_argument('--output',required=True)
    for cmd in ('score','stage','review-outputs'):
        a=sub.add_parser(cmd);a.add_argument('--suite',required=True);a.add_argument('--results',required=True);a.add_argument('--output',required=True)
        if cmd!='review-outputs':a.add_argument('--suite-review');a.add_argument('--output-review')
        if cmd=='stage':a.add_argument('--policy',required=True);a.add_argument('--baseline');a.add_argument('--baseline-review')
    a=p.parse_args()
    if a.command=='candidates':
        suite=candidate_suite();write_new(a.output,suite);write_new(a.review,suite_review_packet(suite));print(json.dumps({'cases':len(suite['cases']),'status':suite['status']}));return
    suite=read(a.suite)
    if a.command=='run':
        from slm.inference.greedy import GreedyModel
        model=GreedyModel(a.model,a.tokenizer,a.backend,a.device,expected_tokenizer_hash=a.tokenizer_hash,embedding_implementation=a.embedding)
        result=evaluate(suite,model,a.max_new_tokens)
    elif a.command=='review-outputs':result=output_review_packet(suite,read(a.results))
    elif a.command=='score':result=score(suite,read(a.results),suite_review=read(a.suite_review),output_review=read(a.output_review))
    else:result=assess(suite,read(a.results),read(a.policy),suite_review=read(a.suite_review),output_review=read(a.output_review),baseline=read(a.baseline),baseline_review=read(a.baseline_review))
    write_new(a.output,result);print(json.dumps({'output':a.output,'command':a.command,'decision':result.get('decision')}))


if __name__=='__main__':main()
