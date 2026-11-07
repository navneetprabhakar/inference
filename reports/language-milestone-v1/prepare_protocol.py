"""CPU metadata only. Explicit event/time caps; root reviews resulting pin."""
import argparse,json,pathlib,sys
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R))
from own_base_language_milestone import sha,cost_plan,FOUNDATION_SHA,SERIES,runtime_versions
from tokenizer import load

def main(events,seconds,calendar,output):
 assert type(events)is int and events>0 and 20<seconds<=14400 and calendar>=events*seconds
 f=R/'reports/base-foundation-100m/budget.json';assert sha(f)==FOUNDATION_SHA;foundation=json.loads(f.read_text());dp=pathlib.Path(foundation['diagnostics']);bp=pathlib.Path(foundation['corpus'])/'validation-blocks.json';assert sha(dp)==foundation['diagnostics_sha256'] and sha(bp)==foundation['validation_blocks_sha256'];blocks=json.loads(bp.read_text());blocks=blocks['blocks'] if isinstance(blocks,dict) else blocks
 worst=cost_plan(json.loads(dp.read_text()),load(),blocks);code=['own_base_language_milestone.py','own_base_dev_run.py','base_train.py','gpt2.py','tokenizer.py','checkpoint.py','guards.py','optimizer_ablation_train.py','base_run_control.py','pretrained_base.py','pretrain.py','train.py']
 p=dict(state='reviewed_external_language_milestone',runtime_versions=runtime_versions(),mandatory_ac_power=True,series=SERIES,python=str(pathlib.Path(sys.executable).absolute()),foundation_budget_sha256=FOUNDATION_SHA,length=512,generation_max=48,precision='fp32',code_sha256={n:sha(R/n) for n in code},worst_case=worst,budgets={**{k:worst[k]*events for k in ('attempted_targets','input_positions','attention_elements')},'active_seconds':events*seconds,'calendar_seconds':calendar},per_milestone_seconds=seconds,rss_limit_bytes=18*1024**3,stop_paths=[str(R/'runs/STOP'),str(R/'runs/own-base-foundation-01/STOP')]+[str(R/f'runs/optimizer-ablation-v1-{a}/STOP') for a in ('preserve-095','reset-095','reset-scaled')],planned_events=events,accounting='Reserve full worstcase per milestone before worker spawn; retain charge after crashes or early EOT. Per-forward journal records attempted target/input/attention counts and completion; no automatic retries.',interpretation='External transfer evidence only, no assistant/tool acceptance; root decisions remain separate.')
 output=pathlib.Path(output)
 with output.open('x') as f:json.dump(p,f,indent=2);f.write('\n')
 print(json.dumps(dict(path=str(output.resolve()),sha256=sha(output),worst_case=worst)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--events',type=int,required=True);p.add_argument('--seconds-per-event',type=int,required=True);p.add_argument('--calendar-seconds',type=int,required=True);p.add_argument('--output',required=True);a=p.parse_args();main(a.events,a.seconds_per_event,a.calendar_seconds,a.output)
