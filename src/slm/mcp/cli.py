"""Configured application MCP discovery and student turns over bounded stdio."""
import argparse
import json
from pathlib import Path
from slm.eval.conversation import write_new
from slm.mcp.registry import MCPRegistry


def configuration(path):
    path=Path(path);raw=path.read_bytes()
    if len(raw)>32768:raise ValueError('Bounded MCP configuration required')
    config=json.loads(raw)
    if not isinstance(config,dict) or config.get('transport')!='stdio':raise ValueError('Explicit stdio configuration required')
    config.pop('transport')
    if not set(config)<={'command','namespace','selected','cwd','env','timeout','mode','max_tools','max_pages','max_discovery_bytes','transport_limits'}:
        raise ValueError('Unknown MCP host configuration fields')
    if 'cwd' in config:
        root=Path(config['cwd']);config['cwd']=str(root if root.is_absolute() else path.resolve().parent/root)
    return config


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('discover');a.add_argument('--config',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('run');a.add_argument('--config',required=True);a.add_argument('--output',required=True)
    a.add_argument('--model',required=True);a.add_argument('--tokenizer',required=True);a.add_argument('--tokenizer-hash',required=True)
    a.add_argument('--history',required=True);a.add_argument('--backend',choices=['mlx','torch'],default='torch');a.add_argument('--device',default='cpu')
    a.add_argument('--max-calls',type=int,default=1);a.add_argument('--max-steps',type=int,default=2);a.add_argument('--max-new-tokens',type=int,default=128)
    a.add_argument('--max-result-bytes',type=int,default=2048)
    a=p.parse_args()
    if Path(a.output).exists():raise FileExistsError(a.output)
    config=configuration(a.config)
    if a.command=='run':
        from slm.inference.tools import ToolModel
        model=ToolModel(a.model,a.tokenizer,a.backend,a.device,expected_tokenizer_hash=a.tokenizer_hash)
        history=json.loads(Path(a.history).read_text())
    registry=MCPRegistry(**config)
    with registry:
        if a.command=='discover':report={'registry_hash':registry.fingerprint,'tools':registry.discover()}
        else:
            from slm.inference.tools import run_turn
            report=run_turn(model,history,registry,max_calls=a.max_calls,max_steps=a.max_steps,max_new_tokens=a.max_new_tokens,max_result_bytes=a.max_result_bytes)
    report['mcp_audit']=registry.audit();write_new(a.output,report)
    print(json.dumps({'output':a.output,'status':report.get('status'),'mcp_submissions':registry.metrics['tool_requests_submitted']}))


if __name__=='__main__':main()
