"""Check all generated target values against explicit symbolic facts."""
import json,hashlib
from pathlib import Path
from sft_common import ROOT

def main():
    p=ROOT/'data/eight-hour-grounded-v1/batch-001.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()];errors=[]
    for row in rows:
        f=row['family'];d=row['oracle_facts'];a=[m['content'] for m in row['messages'] if m['role']=='assistant'];want=None
        if f=='location_update':want=[f"Drawer {d['initial']}.",f"Locker {d['updated']}."]
        elif f=='numeric_comparison':want=[d['names'][0 if d['a']<d['b'] else 1]+'.',f"{abs(d['a']-d['b'])} g."]
        elif f=='ordered_items':x,y,z=d['order'];want=[z+'.',f'{y}, {z}, {x}.']
        elif f=='stated_rule':want=[f"Yes. The ticket is {d['required']}." if d['actual']==d['required'] else f"No. A {d['required']} ticket is required.",d['required'].capitalize()+'.']
        elif f=='memo_recall':want=[f"No. It says {d['day']}.",d['day']]
        elif f=='uppercase_copy':want=[d['code'].upper(),'No. The digits stayed the same.']
        elif f=='small_arithmetic':want=[f"{d['a']+d['b']} {d['object']}.",f"{d['a']+d['b']-d['subtract']} {d['object']}."]
        elif f=='polite_rewrite':want=[f"Could you please {d['command']}?",'It is a question.']
        elif f=='no_tool_arithmetic':want=[str(d['a']+d['b']),'No.']
        elif f=='missing_tool_argument':
            call=json.loads(a[1].split('<|tool_call|>',1)[1]);wantcall={'name':'calculate','arguments':{'op':'add','a':d['a'],'b':d['b']}}
            if call!=wantcall or a[0]!='What is the other number?' or a[-1]!=f"The result is {d['a']+d['b']}.":errors.append(row['id'])
        elif f=='division_error':
            call=json.loads(a[0].split('<|tool_call|>',1)[1]);wantcall={'name':'calculate','arguments':{'op':'divide','a':d['a'],'b':0}}
            if call!=wantcall or d['b']!=0 or a[1]!='The calculator reports division by zero. A nonzero divisor is required.' or a[2]!='No. Use a nonzero divisor.':errors.append(row['id'])
        elif f=='unavailable_calendar':
            if any('<|tool_call|>' in x for x in a) or 'cannot determine' not in a[0] or 'None of these tools' not in a[1]:errors.append(row['id'])
        else:errors.append(row['id']+':unknown family')
        if want is not None:
            want=[v.replace(' A amber',' An amber').replace(' A orange',' An orange') for v in want]
            if a!=want:errors.append(row['id'])
    result={'records_checked':len(rows),'errors':errors,'records_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scope':'Symbolic oracle consistency for these explicit programmatic templates; not natural-dialogue quality certification.'}
    (p.parent/'oracle-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(errors))
if __name__=='__main__':main()
