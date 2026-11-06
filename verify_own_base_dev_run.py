"""Tiny CPU/subprocess controls only; no candidate/checkpoint/corpus/GPU reads."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import torch
from own_base_dev_run import ROOT,CORPORA,CAPS,RUNTIME,Budget,Journal,RunnerStop,bounded_greedy,supervise,validate_spec,make_ticket,consume_ticket,atomic,persist_emergency_turn,incomplete_terminal,RESERVED_BYTES,EMERGENCY_BYTES
from tokenizer import EOT


def caps():
    return dict(wall_seconds=30,heartbeat_seconds=5,termination_grace_seconds=1,max_frames=10,
        max_reserved_generation_tokens=2560,max_reserved_input_positions=3000000,
        max_reserved_attention_cells=3000000000,max_actual_generated_tokens=2560,
        max_rss_bytes=512*1024**2,max_swap_growth_bytes=1024**2,min_free_disk_bytes=20*1024**3,
        max_output_bytes=10*1024**2,max_thermal_state=1)

class Guard:
    def __init__(self):self.checks=0
    def check(self):self.checks+=1

class TinyDecoder(torch.nn.Module):
    def __init__(self,ids):super().__init__();self.weight=torch.nn.Parameter(torch.zeros(1));self.ids=ids;self.index=0
    def forward(self,row):
        logits=torch.full((1,row.shape[1],EOT+1),-10.,device='cpu')
        logits[0,-1,self.ids[self.index]]=10.;self.index+=1;return logits


def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);checks=[]
    spec=dict(schema=1,device='mps',dtype='float32',candidate=dict(manifest=str(ROOT/'own-base-candidates/future/manifest.json'),manifest_sha256='a'*64),
        corpora=[dict(id=name,file_sha256='a'*64,canonical_sha256='b'*64,receipt_sha256='c'*64,freeze_sha256='d'*64,sessions=sessions,turns=turns) for name,_path,sessions,turns in CORPORA],
        runtime_sha256={p:'e'*64 for p in RUNTIME},budgets=caps(),output=str(ROOT/'runs/own-base-dev-fixture-never-created'),
        stop_paths=[str(ROOT/'runs/STOP'),str(ROOT/'runs/own-base-foundation-01/STOP'),str(ROOT/'runs/own-base-dev-fixture-never-created/STOP')])
    assert validate_spec(spec)==spec and not Path(spec['output']).exists()
    mutations=[]
    for key,value in [('device','cpu'),('dtype','bfloat16'),('output',str(ROOT/'runs/nested/own-base-dev-x'))]:
        bad=deepcopy(spec);bad[key]=value;mutations.append(bad)
    bad=deepcopy(spec);bad['budgets'].pop('max_frames');mutations.append(bad)
    bad=deepcopy(spec);bad['budgets']['min_free_disk_bytes']=1;mutations.append(bad)
    bad=deepcopy(spec);bad['corpora'][0]['sessions']=421;mutations.append(bad)
    bad=deepcopy(spec);bad['stop_paths']=[];mutations.append(bad)
    bad=deepcopy(spec);bad['runtime_sha256'].pop('own_base_chat.py');mutations.append(bad)
    for bad in mutations:
        try:validate_spec(bad)
        except ValueError:pass
        else:raise AssertionError('invalid explicit spec accepted')
    checks.append('mandatory explicit spec and eight device/budget/pin/denominator/STOP refusals')
    with tempfile.TemporaryDirectory() as temp:
        directory=Path(temp)
        log=Journal(directory/'events.jsonl',1000000);budget=Budget(caps(),log);guard=Guard()
        prefix=[10,20,30];model=TinyDecoder([41,42,EOT])
        output=bounded_greedy(model,prefix,256,guard,budget)
        from evaluate import greedy
        assert output==greedy(TinyDecoder([41,42,EOT]),prefix,256,Guard())==[41,42,EOT]
        assert budget.counts['reserved_generation_tokens']==256 and budget.counts['actual_generated_tokens']==3
        assert budget.counts['reserved_input_positions']==sum(3+i for i in range(256))
        assert budget.counts['reserved_attention_cells']==sum((3+i)**2 for i in range(256))
        assert budget.counts['actual_input_positions']==3+4+5 and budget.pending is None
        log.close();events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        assert events[0]['event']=='frame_reserved' and events[-1]['event']=='frame_completed'
        checks.append('actual tiny CPU decoder parity and durable full-frame reservation without early-EOT refunds')
        log=Journal(directory/'caps.jsonl',1000000);small=caps();small['max_reserved_generation_tokens']=255
        budget=Budget(small,log);model=TinyDecoder([EOT])
        try:bounded_greedy(model,prefix,256,Guard(),budget)
        except RunnerStop:pass
        else:raise AssertionError('unreserved forward executed')
        assert model.index==0 and budget.counts['frames']==0;log.close()
        limited=directory/'limited';limited.mkdir();small_log=Journal(limited/'events.jsonl',10)
        try:small_log.emit('event_too_large',text='bounded')
        except RunnerStop:pass
        else:raise AssertionError('journal byte cap ignored')
        small_log.close();assert (limited/'events.jsonl').stat().st_size==0
        try:atomic(limited/'too-large.json',dict(value='too large'),max_total_bytes=10)
        except RunnerStop:pass
        else:raise AssertionError('atomic artifact cap ignored')
        assert not (limited/'too-large.json').exists() and not (limited/'too-large.json.tmp').exists()
        checks.append('journal and atomic temporary output budgets refuse before writing')
        # Exhaust the ordinary allocation immediately after a real broker call.
        # The authoritative effects exist even though Chat did not receive them.
        from own_base_chat import Chat
        from tools import FixtureSession
        from tokenizer import load
        tok=load();emergency_dir=directory/'emergency';emergency_dir.mkdir()
        total=3*1024**2
        (emergency_dir/'full-journal.jsonl').write_bytes(b'x'*(total-RESERVED_BYTES))
        class ExhaustAfterCall(FixtureSession):
            def propose(self,*args,**kwargs):
                super().propose(*args,**kwargs)
                raise RunnerStop('synthetic journal output exhausted immediately after actual call')
        actual_call={'call':{'name':'calculate','arguments':{'op':'multiply','a':7,'b':8}}}
        def generate(prefix,budget):return tok.encode(json.dumps(actual_call)).ids+[EOT]
        chat=Chat(None,tok,Guard(),generate=generate);chat.session=ExhaustAfterCall()
        try:chat.turn('Multiply seven by eight.')
        except RunnerStop as error:
            emergency=persist_emergency_turn(emergency_dir,chat,error,total)
            terminal=incomplete_terminal(emergency_dir,error,{},None,total)
        else:raise AssertionError('synthetic recording failure swallowed')
        assert emergency['authoritative_session_trace'][0]['data']['result']==56
        assert emergency['authoritative_session_decisions'][0]['dispatched'] is True
        assert emergency['current_turn_record']['result']['answer'] is None
        assert terminal['state']=='incomplete' and terminal['emergency_receipt'] and terminal['aggregate_score'] is None
        assert sum(p.stat().st_size for p in emergency_dir.iterdir())<=total
        # Oversized user/frame evidence is explicitly omitted; actual records stay.
        oversized=directory/'oversized-emergency';oversized.mkdir()
        chat.turn_records[-1]['user']='x'*(EMERGENCY_BYTES+1)
        payload=persist_emergency_turn(oversized,chat,RunnerStop('oversized evidence'),total)
        assert payload['current_turn_record'] is None and payload['omitted']
        assert payload['authoritative_session_trace'][0]['call_id']=='c1'
        assert payload['authoritative_session_trace'][0]['data']['result']==56
        assert (oversized/'emergency-turn.json').stat().st_size<=EMERGENCY_BYTES
        checks.append('exhaustion after real tool execution saves emergency result/decision and incomplete terminal; oversized frame omissions explicit')
        checks.append('budget refusal occurs before any model forward')
        log=Journal(directory/'interrupt.jsonl',1000000);budget=Budget(caps(),log)
        class Broken(TinyDecoder):
            def forward(self,row):raise RuntimeError('synthetic CPU decoder error')
        try:bounded_greedy(Broken([]),prefix,256,Guard(),budget)
        except RuntimeError:pass
        else:raise AssertionError('decoder infrastructure error swallowed')
        assert budget.counts['reserved_generation_tokens']==256 and budget.pending is not None
        assert budget.counts['actual_generated_tokens']==0;log.close()
        checks.append('interrupted forward retains reserved cost and unknown pending frame')
        log=Journal(directory/'multi.jsonl',1000000);budget=Budget(caps(),log)
        for _ in range(4):bounded_greedy(TinyDecoder([EOT]),prefix,256,Guard(),budget)
        assert budget.counts['frames']==4;log.close()
        checks.append('no implicit three-frame cap added')
        ok=directory/'ok';ok.mkdir()
        result=supervise(lambda fd:[sys.executable,'-c','print("synthetic worker complete")'],ok,ticket=make_ticket(5),heartbeat_seconds=3,grace_seconds=.1,max_rss_bytes=512*1024**2)
        assert result['exit_code']==0 and result['watchdog_reason'] is None
        hung=directory/'hung';hung.mkdir()
        code='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("durable-start",flush=True); time.sleep(30)'
        result=supervise(lambda fd:[sys.executable,'-c',code],hung,ticket=make_ticket(3),heartbeat_seconds=.3,grace_seconds=.1,max_rss_bytes=512*1024**2)
        assert result['exit_code']!=0 and 'heartbeat' in result['watchdog_reason'] and result['hard_stop_inflight_state']
        assert 'durable-start' in (hung/'worker.stdout').read_text()
        rss=directory/'rss';rss.mkdir()
        result=supervise(lambda fd:[sys.executable,'-c','import time; time.sleep(10)'],rss,ticket=make_ticket(3),heartbeat_seconds=2,grace_seconds=.1,max_rss_bytes=1)
        assert 'RSS' in result['watchdog_reason']
        stop=directory/'stop';stop.mkdir()
        def stopped(pid,available):raise RunnerStop('synthetic STOP')
        result=supervise(lambda fd:[sys.executable,'-c','import time; time.sleep(10)'],stop,ticket=make_ticket(3),heartbeat_seconds=2,grace_seconds=.1,max_rss_bytes=512*1024**2,check=stopped)
        assert result['watchdog_reason']=='synthetic STOP'
        hard=directory/'hard';hard.mkdir()
        # Isolate termination timing from ps startup jitter; RSS monitoring is
        # exercised against a real process in the separate cap test above.
        with patch('own_base_dev_run.group_rss',return_value=1):
            result=supervise(lambda fd:[sys.executable,'-c',code],hard,ticket=make_ticket(.7),heartbeat_seconds=10,grace_seconds=.2,max_rss_bytes=512*1024**2)
        assert 'wall deadline' in result['watchdog_reason'] and result['within_deadline'] and result['seconds']<.7
        ticket_dir=directory/'ticket';ticket_dir.mkdir()
        command=lambda fd:[sys.executable,'-c',f'from own_base_dev_run import consume_ticket; print(consume_ticket({fd})["nonce"])']
        ticket=make_ticket(4)
        result=supervise(command,ticket_dir,ticket=ticket,heartbeat_seconds=3,grace_seconds=.2,max_rss_bytes=512*1024**2)
        assert result['exit_code']==0 and ticket['nonce'] in (ticket_dir/'worker.stdout').read_text()
        invalid_ticket_dir=directory/'invalid-ticket';invalid_ticket_dir.mkdir()
        bad_ticket=make_ticket(4);bad_ticket['watchdog_pid']=0
        result=supervise(command,invalid_ticket_dir,ticket=bad_ticket,heartbeat_seconds=3,grace_seconds=.2,max_rss_bytes=512*1024**2)
        assert result['exit_code']!=0
        try:consume_ticket(None)
        except RunnerStop:pass
        else:raise AssertionError('worker without inherited pipe accepted')
        checks.append('single original hard deadline includes TERM/KILL/reap and valid/invalid watchdog pipe tickets')
        checks.append('foreground subprocess success/heartbeat kill/RSS cap/STOP with partial evidence retained')
    print(json.dumps(dict(state='passed',checks=checks,production_candidate_loaded=False,corpus_read=False,gpu_operations=False,activation_spec_created=False),indent=2))

if __name__=='__main__':main()
