"""Broader supervised data and counterfactual result targets for the follow-on candidate."""
import hashlib
import json
import random
from pathlib import Path

from broad_teaching import examples as broad
from compositional_teaching import examples as compositions
from scaled_teaching import examples as scaled
from tokenizer import EOT
from tool_teaching import examples as tools, display
from tool_teaching_varied import examples as varied_tools


def additional_pools(tok,seed,original,chat_row,copy_row):
    # Only assemble train histories that cleared the separate set-custodian audits.
    path=Path("reports/working-chat")
    extra=set(json.loads((path/"followon-excluded-histories.json").read_text()))
    broad_denied=set(json.loads((path/"broad-excluded-histories.json").read_text()))
    varied_denied=set(json.loads((path/'varied-tool-excluded-histories.json').read_text()))
    for name,make,deny in [('broad',broad,broad_denied),('scaled',scaled,extra),('compositional',compositions,extra),('varied_tool',varied_tools,varied_denied)]:
        original[name]=[]
        for h in make(seed):
            key=hashlib.sha256(json.dumps(h,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if key not in deny:
                original[name].append(chat_row(tok,h))
    # Reuse audited requests, preserving all argument signatures. Only the numerical
    # fixture changes. Post-tool supervision is isolated from the earlier action loss.
    deny=set(json.loads((path/'excluded-histories.json').read_text()))
    rng=random.Random(seed+91)
    reporting=[]
    standalone=[]
    for history in tools(seed):
        key=hashlib.sha256(json.dumps(history,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if key in deny or len(history)<4 or history[2].get('role')!='tool' or 'result' not in history[2]['result']:
            continue
        value=rng.choice([rng.randrange(-99,100),rng.randrange(100,10000),rng.randint(-160,160)/4,rng.randint(0,1999)/10])
        actual=display(value)
        record=dict(history[2]['result'], result=value)
        prefix=history[:2]+[dict(role='tool',result=record)]
        # The full context is identical to inference. Only final assistant body contributes.
        row,labels=chat_row(tok,prefix+[dict(role='assistant',text=actual)])
        last_frame=len(tok.encode(json.dumps({'text':actual},separators=(',',':'))).ids)+1
        labels[:-last_frame]=[-100]*(len(labels)-last_frame)
        reporting.append((row,labels))
        sentence=f"The {record['name']} tool returned {actual}."
        standalone.append(copy_row(tok,sentence,actual,False))
        standalone.append(copy_row(tok,sentence,actual,True))
    original['reporting']=reporting
    original['numeric']=standalone
    return {'copy':.025,'chat':.085,'natural':.055,'tool':.07,'varied_tool':.11,'scaled':.13,'broad':.035,
            'compositional':.38,'reporting':.075,'numeric':.035}
